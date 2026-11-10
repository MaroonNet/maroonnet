"""Elevation from USGS 3DEP 1/3 arc-second (~10 m) tiles, resampled onto a Window.

3DEP publishes 1 x 1 degree Cloud Optimized GeoTIFFs named by their north-west
corner, e.g. ``USGS_13_n45w075.tif`` covers 44-45 N, 75-74 W. Values are
bare-earth elevation in metres (NAVD88), on NAD83 geographic coordinates.

Tiles are read straight from the USGS bucket (GDAL fetches only the blocks a
window needs) unless a local copy exists in ``tile_dir``. Field use has no
network, so pre-download the tiles for the operating area with ``fetch_tiles``.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from rasterio.errors import RasterioIOError
from rasterio.warp import Resampling, reproject, transform_bounds

from spm.download import fetch
from spm.geodata.grid import Window

log = logging.getLogger(__name__)

BASE_URL = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current"
SOURCE = "usgs-3dep-13"


def tile_name(lat_top: int, lon_left: int) -> str:
    """3DEP tile name for the tile whose north-west corner is (lat_top, lon_left)."""
    ns = "n" if lat_top >= 0 else "s"
    ew = "w" if lon_left < 0 else "e"
    return f"{ns}{abs(lat_top):02d}{ew}{abs(lon_left):03d}"


def tiles_for_bounds(lon_min: float, lat_min: float, lon_max: float, lat_max: float) -> list[str]:
    """Names of every tile that touches a lon/lat box."""
    names = []
    for lat_top in range(math.floor(lat_min) + 1, math.ceil(lat_max) + 1):
        for lon_left in range(math.floor(lon_min), math.ceil(lon_max)):
            names.append(tile_name(lat_top, lon_left))
    return names


def tile_url(name: str) -> str:
    return f"{BASE_URL}/{name}/USGS_13_{name}.tif"


def tile_path(name: str, tile_dir: Path | None) -> str:
    """Local tile if it has been downloaded, otherwise the remote COG."""
    if tile_dir is not None:
        local = Path(tile_dir) / f"USGS_13_{name}.tif"
        if local.exists():
            return str(local)
        log.warning(
            "tile %s is not in %s; reading it over the network (spm fetch-dem downloads it)",
            name,
            tile_dir,
        )
    return "/vsicurl/" + tile_url(name)


def window_lonlat_bounds(window: Window) -> tuple[float, float, float, float]:
    """(lon_min, lat_min, lon_max, lat_max) enclosing the window."""
    return transform_bounds(f"EPSG:{window.epsg}", "EPSG:4326", *window.bounds, densify_pts=21)


def fetch_tiles(names: list[str], tile_dir: Path) -> list[Path]:
    """Download whole tiles into ``tile_dir`` for offline use (skips tiles already present)."""
    tile_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for name in names:
        out.append(fetch(tile_url(name), tile_dir / f"USGS_13_{name}.tif"))
    return out


def read_dem(window: Window, tile_dir: Path | None = None, sources: list[str] | None = None):
    """Elevation (m, float32) on the window grid; NaN where no tile has data.

    ``sources`` overrides the tile lookup (paths or GDAL URLs), mainly for tests.
    Resampling is bilinear, as elevation is continuous.
    """
    if sources is None:
        names = tiles_for_bounds(*window_lonlat_bounds(window))
        sources = [tile_path(n, tile_dir) for n in names]
    out = np.full(window.shape, np.nan, dtype=np.float32)
    transform = Affine(*window.affine())
    for src_path in sources:
        part = np.full(window.shape, np.nan, dtype=np.float32)
        try:
            src = rasterio.open(src_path)
        except RasterioIOError as err:
            if not src_path.startswith("/vsicurl/"):
                raise
            if "404" in str(err):
                log.info("no 3DEP tile at %s (open water or outside coverage)", src_path)
            else:
                log.warning(
                    "could not read %s (%s): offline? elevation is missing there; "
                    "run spm fetch-dem before going into the field",
                    src_path,
                    str(err).splitlines()[0][:120],
                )
            continue
        with src:
            reproject(
                source=rasterio.band(src, 1),
                destination=part,
                src_nodata=src.nodata,
                dst_transform=transform,
                dst_crs=f"EPSG:{window.epsg}",
                dst_nodata=np.nan,
                resampling=Resampling.bilinear,
            )
        fill = np.isnan(out) & ~np.isnan(part)
        out[fill] = part[fill]
    return out


def coverage(dem_values: np.ndarray) -> float:
    """Fraction of cells with elevation data."""
    return float(np.isfinite(dem_values).mean()) if dem_values.size else 0.0
