"""Write a Prediction out: GeoTIFF for GIS and (P)MP, PNGs for people.

Planners read probability as cumulative mass, the way Koester's 25/50/75/95%
rings are read, so every output carries ``mass_rank``: for each cell, the share
of the in-window probability held by cells at least as likely as that cell.
The region where mass_rank <= 0.5 is the smallest area holding half the mass.
Raw density spans several orders of magnitude and colours badly.

Outputs
    write_geotiff      3 float32 bands: probability, mass_rank, flag (1 = out of range);
                       tags carry p_outside, model name/version and the band levels
    write_heatmap_png  report figure: mass bands, trails/roads from the stack, IPP
    write_web_overlay  RGBA PNG in Web Mercator plus a JSON with its corner
                       coordinates, for a MapLibre/Leaflet image source
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform

from spm.schema import Case, Prediction

LEVELS = (0.25, 0.50, 0.75, 0.95)
# One colour per level, hot to cold: dark red is the ground to search first. The ramp is
# ordered by lightness (ColorBrewer OrRd), so it still reads in greyscale and for most
# colour-blind viewers. The last band usually covers most of the map, so it is kept light.
BAND_RGBA = (
    (179, 0, 0, 185),
    (227, 74, 51, 150),
    (252, 141, 89, 115),
    (253, 204, 138, 60),
)
BAND_NAMES = ("search 1st", "search 2nd", "search 3rd", "search 4th")


def mass_rank(prob: np.ndarray) -> np.ndarray:
    """Share of in-window mass in cells at least as probable as each cell (ties share a rank)."""
    flat = prob.ravel()
    order = np.argsort(-flat, kind="stable")
    sorted_p = flat[order]
    cum = np.cumsum(sorted_p)
    # ties: every cell of equal probability gets the cumulative mass through its whole tie group
    starts = np.flatnonzero(np.r_[True, sorted_p[1:] != sorted_p[:-1]])
    group = np.cumsum(np.r_[True, sorted_p[1:] != sorted_p[:-1]]) - 1
    group_end = np.maximum.reduceat(cum, starts)
    out = np.empty_like(flat)
    out[order] = group_end[group]
    return out.reshape(prob.shape)


def mass_bands(rank: np.ndarray, levels=LEVELS) -> np.ndarray:
    """0 = beyond the last level; k = inside level k (1-based) but not level k-1."""
    bands = np.zeros(rank.shape, dtype=np.uint8)
    for k, lev in reversed(list(enumerate(levels, start=1))):
        bands[rank <= lev] = k
    return bands


def write_geotiff(
    pred: Prediction, path: Path, levels=LEVELS, ipp: tuple[float, float] | None = None
) -> Path:
    """``ipp`` (lon, lat) is tagged so ``spm update`` can redraw the marker later."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rank = mass_rank(pred.prob)
    flags = np.zeros(pred.window.shape, np.float32) if pred.flags is None else pred.flags
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=pred.window.n,
        height=pred.window.n,
        count=3,
        dtype="float32",
        crs=f"EPSG:{pred.window.epsg}",
        transform=Affine(*pred.window.affine()),
        compress="deflate",
    ) as dst:
        dst.write(pred.prob.astype(np.float32), 1)
        dst.write(rank.astype(np.float32), 2)
        dst.write(flags.astype(np.float32), 3)
        dst.set_band_description(1, "probability")
        dst.set_band_description(2, "mass_rank")
        dst.set_band_description(3, "out_of_range")
        dst.update_tags(
            p_outside=f"{pred.p_outside:.6f}",
            model=pred.model,
            model_version=pred.model_version,
            levels=",".join(str(v) for v in levels),
            note="student prototype; not certified for life-safety use",
            **({"ipp": f"{ipp[0]:.6f},{ipp[1]:.6f}"} if ipp else {}),
        )
    return path


def write_heatmap_png(
    pred: Prediction,
    path: Path,
    case: Case | None = None,
    stack=None,
    levels=LEVELS,
    title: str | None = None,
) -> Path:
    """Report figure: cumulative-mass bands, linear features from the stack, the IPP."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    w = pred.window
    extent = (w.x0, w.x0 + w.n * w.res, w.y0 - w.n * w.res, w.y0)
    bands = mass_bands(mass_rank(pred.prob), levels)
    cmap = ListedColormap([(0, 0, 0, 0)] + [tuple(c / 255 for c in rgba) for rgba in BAND_RGBA])

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.set_facecolor("#f2f2f2")
    ax.imshow(bands, cmap=cmap, vmin=0, vmax=len(levels), extent=extent, interpolation="nearest")
    if stack is not None:
        sw = stack.window
        s_extent = (sw.x0, sw.x0 + sw.n * sw.res, sw.y0 - sw.n * sw.res, sw.y0)
        for layer, colour in (("road_mask", "#555555"), ("trail_mask", "#8b4513")):
            if stack.has(layer):
                m = np.ma.masked_where(~stack[layer], np.ones(sw.shape))
                ax.imshow(
                    m, cmap=ListedColormap([colour]), extent=s_extent, interpolation="nearest"
                )
    if pred.flags is not None and pred.flags.any():
        ax.contourf(
            np.flipud(pred.flags.astype(float)),
            levels=[0.5, 1.5],
            colors="none",
            hatches=["//"],
            extent=extent,
        )
    if case is not None and case.ipp is not None:
        ax.plot(*w.project(case.ipp.lon, case.ipp.lat), "k^", ms=10, label="IPP")
        if case.find is not None:
            ax.plot(*w.project(case.find.lon, case.find.lat), "r*", ms=12, label="find")
    for k, lev in enumerate(levels):
        # cumulative, densest first: band k is the smallest area holding `lev` of the probability
        label = BAND_NAMES[k] if k < len(BAND_NAMES) else f"search {k + 1}"
        label += " (most likely ground)" if k == 0 else ""
        if lev >= 1.0 - pred.p_outside:  # this zone is not closed inside the window
            label += " (runs off the map)"
        ax.plot([], [], "s", color=tuple(c / 255 for c in BAND_RGBA[k][:3]), label=label)
    ax.plot([], [], "-", color="#8b4513", label="trail")
    ax.plot([], [], "-", color="#555555", label="road")
    ax.legend(loc="lower left", fontsize=8, framealpha=0.9)
    ax.set_title(
        title
        or f"{pred.model} v{pred.model_version} | chance they are beyond this map: "
        f"{pred.p_outside:.0%} | prototype, not for life-safety use",
        fontsize=9,
    )
    ax.set_xlabel(f"UTM EPSG:{w.epsg} (m)")
    ax.set_aspect("equal")
    fig.tight_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def write_web_overlay(pred: Prediction, png_path: Path, json_path: Path, levels=LEVELS) -> Path:
    """RGBA PNG in Web Mercator + JSON corner coordinates (lon, lat) for a map image source."""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib.image import imsave

    w = pred.window
    src_crs, dst_crs = f"EPSG:{w.epsg}", "EPSG:3857"
    src_transform = Affine(*w.affine())
    dst_transform, width, height = calculate_default_transform(
        src_crs, dst_crs, w.n, w.n, *w.bounds
    )
    bands = mass_bands(mass_rank(pred.prob), levels)
    out = np.zeros((height, width), dtype=np.uint8)
    reproject(
        bands,
        out,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        src_nodata=0,
        dst_nodata=0,
        resampling=Resampling.nearest,
    )
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    for k, colour in enumerate(BAND_RGBA[: len(levels)], start=1):
        rgba[out == k] = colour
    png_path, json_path = Path(png_path), Path(json_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    imsave(png_path, rgba)

    xmin, ymax = dst_transform.c, dst_transform.f
    xmax, ymin = xmin + dst_transform.a * width, ymax + dst_transform.e * height
    xs, ys = transform(dst_crs, "EPSG:4326", [xmin, xmax, xmax, xmin], [ymax, ymax, ymin, ymin])
    json_path.write_text(
        json.dumps(
            {
                "image": png_path.name,
                "coordinates": [[x, y] for x, y in zip(xs, ys, strict=True)],
                "corner_order": "top-left, top-right, bottom-right, bottom-left",
                "levels": list(levels),
                "p_outside": pred.p_outside,
                "model": pred.model,
                "model_version": pred.model_version,
                "note": "student prototype; not certified for life-safety use",
            },
            indent=2,
        )
        + "\n"
    )
    return png_path


def write_band(path: Path, window, values: np.ndarray, name: str, **tags) -> Path:
    """One float32 band on the window grid (e.g. travel hours), with optional tags."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=window.n,
        height=window.n,
        count=1,
        dtype="float32",
        crs=f"EPSG:{window.epsg}",
        transform=Affine(*window.affine()),
        compress="deflate",
    ) as dst:
        dst.write(values.astype(np.float32), 1)
        dst.set_band_description(1, name)
        dst.update_tags(**{k: str(v) for k, v in tags.items()})
    return path


def read_geotiff(path: Path) -> tuple[Prediction, tuple[float, float] | None]:
    """Read a prediction written by ``write_geotiff``; also its IPP (lon, lat) if tagged."""
    from spm.geodata.grid import Window

    with rasterio.open(path) as src:
        if src.width != src.height:
            raise ValueError("prediction rasters are square windows")
        t = src.transform
        if abs(t.a + t.e) > 1e-9 or t.b or t.d:
            raise ValueError("prediction rasters are north-up with square cells")
        window = Window(epsg=src.crs.to_epsg(), x0=t.c, y0=t.f, res=t.a, n=src.width)
        tags = src.tags()
        prob = src.read(1).astype(float)
        flags = src.read(3).astype(bool) if src.count >= 3 else None
    ipp = tags.get("ipp")
    pred = Prediction(
        prob=prob,
        window=window,
        model=tags.get("model", "unknown"),
        model_version=tags.get("model_version", "0"),
        p_outside=float(tags.get("p_outside", 0.0)),
        flags=flags,
    )
    return pred, (tuple(float(v) for v in ipp.split(",")) if ipp else None)
