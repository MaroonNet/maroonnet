"""Build real FeatureStacks (3DEP elevation + OSM/NHD lines) and cache them on disk.

``StackBuilder`` is a stack provider: ``builder(case, window) -> FeatureStack``,
the signature the evaluation runner and HybridModel expect. Built stacks are
saved as one compressed .npz per window, so each window is downloaded and
rasterized once.

Layers built: dem, trail_mask, road_mask, stream_mask. watershed_id and
landcover are not built yet; models skip missing layers.

Region stacks: ``StackBuilder.region(bbox)`` builds one large stack for an
operating area (e.g. the mission region's tile bbox at 10 m) and saves it under
``cache_dir/regions``. Any later window on the same grid inside it is cropped
from memory instead of being built, so a prediction for a new point takes
seconds rather than a fresh download and rasterization.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from spm.geodata import dem, lines
from spm.geodata.grid import Window, utm_epsg
from spm.geodata.stack import FeatureStack
from spm.schema import Case


def window_for(case: Case, side_m: float, res: float) -> Window | None:
    """Window centred on the IPP, or on the find for find-only cases."""
    centre = case.ipp or case.find
    if centre is None:
        return None
    return Window.around(centre.lon, centre.lat, side_m=side_m, res=res)


class StackBuilder:
    """Stack provider over one or more regions' line files.

    ``lines_gpkg``: trails, roads (and streams, if ``streams_gpkg`` is not given),
    e.g. one ``lines.extract`` output per region. ``streams_gpkg``: stream files
    (e.g. ``lines.extract_nhd``) that replace the streams in ``lines_gpkg``.
    Each window uses only the files whose extent overlaps it; those file names
    are the stack's ``source`` and part of the cache check, so adding another
    region's files does not invalidate stacks already built elsewhere.
    """

    def __init__(
        self,
        lines_gpkg: Path | Sequence[Path],
        tile_dir: Path | None = None,
        cache_dir: Path | None = None,
        streams_gpkg: Path | Sequence[Path] | None = None,
    ):
        self.line_files = _paths(lines_gpkg)
        self.stream_files = _paths(streams_gpkg) if streams_gpkg is not None else []
        self.tile_dir = tile_dir
        self.cache_dir = cache_dir
        self._bounds = {p: lines.file_bounds(p) for p in self.line_files + self.stream_files}
        self._regions: list[FeatureStack] = []
        if cache_dir is not None:
            for path in sorted(Path(cache_dir, "regions").glob("*.npz")):
                self._regions.append(_load_stack(path))

    def _overlapping(self, files: list[Path], window: Window) -> list[Path]:
        lon0, lat0, lon1, lat1 = dem.window_lonlat_bounds(window)
        return [
            p
            for p in files
            if not (
                self._bounds[p][2] < lon0
                or self._bounds[p][0] > lon1
                or self._bounds[p][3] < lat0
                or self._bounds[p][1] > lat1
            )
        ]

    def sources(self, window: Window) -> tuple[dict[str, list[Path]], str]:
        """(line files per class, source string) for a window."""
        lf = self._overlapping(self.line_files, window)
        sf = self._overlapping(self.stream_files, window)
        per_class = {cls: lf for cls in lines.CLASSES}
        source = f"{dem.SOURCE}+lines:{'+'.join(p.name for p in lf)}"
        if sf:
            per_class["stream"] = sf
            source += f"+streams:{'+'.join(p.name for p in sf)}"
        return per_class, source

    def _cache_path(self, window: Window) -> Path | None:
        if self.cache_dir is None:
            return None
        return Path(self.cache_dir) / _stack_name(window)

    # ---------- region stacks ----------
    def region(self, bbox_lonlat: tuple[float, float, float, float], res: float) -> FeatureStack:
        """Build (or load) the stack covering a lon/lat box at ``res``, saved for cropping."""
        lon0, lat0, lon1, lat1 = bbox_lonlat
        epsg = utm_epsg((lon0 + lon1) / 2, (lat0 + lat1) / 2)
        probe = Window(epsg, 0.0, 0.0, res, 1)
        xs, ys = zip(
            *[probe.project(lo, la) for lo in (lon0, lon1) for la in (lat0, lat1)], strict=True
        )
        x0 = math.floor(min(xs) / res) * res
        y0 = math.ceil(max(ys) / res) * res
        n = int(math.ceil(max(max(xs) - x0, y0 - min(ys)) / res))
        window = Window(epsg, x0, y0, res, n)
        path = Path(self.cache_dir, "regions", _stack_name(window)) if self.cache_dir else None
        _, source = self.sources(window)
        if path is not None and path.exists():
            stack = _load_stack(path)
            if stack.source == source:
                self._add_region(stack)
                return stack
        stack = self.build(window)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(path, _source=np.array(stack.source), **stack.layers)
        self._add_region(stack)
        return stack

    def _add_region(self, stack: FeatureStack) -> None:
        self._regions = [r for r in self._regions if r.window != stack.window] + [stack]

    def crop(self, window: Window) -> FeatureStack | None:
        """The window cut from a loaded region stack, or None.

        The window must sit on the region's grid; its cells may be whole multiples of
        the region's (a 20 m window on a 10 m region): elevation is block-averaged and
        a line mask stays set if any sub-cell had the line.
        """
        for reg in self._regions:
            rw = reg.window
            if rw.epsg != window.epsg or window.res < rw.res:
                continue
            k = window.res / rw.res
            if abs(k - round(k)) > 1e-9:
                continue
            k = int(round(k))
            c0 = (window.x0 - rw.x0) / rw.res
            r0 = (rw.y0 - window.y0) / rw.res
            if abs(c0 - round(c0)) > 1e-6 or abs(r0 - round(r0)) > 1e-6:
                continue  # not on the region's grid
            c0, r0 = int(round(c0)), int(round(r0))
            span = window.n * k
            if c0 < 0 or r0 < 0 or c0 + span > rw.n or r0 + span > rw.n:
                continue
            _, source = self.sources(window)
            if reg.source != source:
                continue
            layers = {}
            for name, v in reg.layers.items():
                piece = v[r0 : r0 + span, c0 : c0 + span]
                if k > 1:
                    blocks = piece.reshape(window.n, k, window.n, k)
                    if piece.dtype == bool:
                        piece = blocks.any(axis=(1, 3))
                    else:
                        with np.errstate(invalid="ignore"):
                            piece = np.nanmean(blocks, axis=(1, 3)).astype(v.dtype)
                layers[name] = piece
            return FeatureStack(window=window, layers=layers, source=source)
        return None

    def build(self, window: Window) -> FeatureStack:
        per_class, source = self.sources(window)
        layers = {"dem": dem.read_dem(window, self.tile_dir)}
        layers.update(lines.masks(per_class, window))
        return FeatureStack(window=window, layers=layers, source=source)

    def __call__(self, case: Case | None, window: Window) -> FeatureStack:
        cropped = self.crop(window)
        if cropped is not None:
            return cropped
        path = self._cache_path(window)
        if path is not None and path.exists():
            _, source = self.sources(window)
            with np.load(path) as z:
                if str(z["_source"]) == source:
                    layers = {k: z[k] for k in z.files if k != "_source"}
                    return FeatureStack(window=window, layers=layers, source=source)
        stack = self.build(window)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(path, _source=np.array(stack.source), **stack.layers)
        return stack


def _stack_name(w: Window) -> str:
    return f"{w.epsg}_{w.x0:.0f}_{w.y0:.0f}_{w.res:g}_{w.n}.npz"


def _load_stack(path: Path) -> FeatureStack:
    """A stack saved by this module; the window is parsed from the file name."""
    epsg, x0, y0, res, n = path.stem.split("_")
    window = Window(int(epsg), float(x0), float(y0), float(res), int(n))
    with np.load(path) as z:
        layers = {k: z[k] for k in z.files if k != "_source"}
        source = str(z["_source"])
    return FeatureStack(window=window, layers=layers, source=source)


def _paths(p: Path | Sequence[Path]) -> list[Path]:
    return [Path(p)] if isinstance(p, (str, Path)) else [Path(x) for x in p]
