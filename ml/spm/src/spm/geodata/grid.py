"""The canonical grid: one place that decides CRS, origin and cell size.

Every raster in SPM (model output, terrain layers, the scorer's view of a case)
lives on a ``Window``: a square block of cells in a projected CRS, in metres.

Rules that keep layers aligned:
  * CRS is the UTM zone of the window centre (WGS84 / UTM, EPSG:326xx north,
    EPSG:327xx south). Colorado is zone 13N, EPSG:32613.
  * The window origin is snapped to a multiple of the cell size, so two
    windows with the same CRS and resolution always share cell boundaries,
    and terrain stacks built later line up cell for cell.
  * Arrays are indexed [row, col]; row 0 is the northern edge.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from pyproj import Transformer

# MapScore's published protocol: a 25 km x 25 km box centred on the IPP.
MAPSCORE_SIDE_M = 25_000.0


def utm_epsg(lon: float, lat: float) -> int:
    """EPSG code of the WGS84 UTM zone containing (lon, lat)."""
    zone = int(math.floor((lon + 180.0) / 6.0)) % 60 + 1
    return (32600 if lat >= 0 else 32700) + zone


@lru_cache(maxsize=64)
def _to_proj(epsg: int) -> Transformer:
    return Transformer.from_crs(4326, epsg, always_xy=True)


@lru_cache(maxsize=64)
def _to_geo(epsg: int) -> Transformer:
    return Transformer.from_crs(epsg, 4326, always_xy=True)


@dataclass(frozen=True)
class Window:
    """A square block of cells in a projected CRS.

    x0, y0 are the projected coordinates (metres) of the window's upper-left
    corner; ``res`` is the cell side in metres; ``n`` is cells per side.
    """

    epsg: int
    x0: float
    y0: float
    res: float
    n: int

    # ---------- construction ----------
    @classmethod
    def around(
        cls,
        lon: float,
        lat: float,
        side_m: float = MAPSCORE_SIDE_M,
        res: float = 25.0,
        epsg: int | None = None,
    ) -> Window:
        """Window of about ``side_m`` per side centred on (lon, lat), origin snapped to ``res``."""
        epsg = epsg or utm_epsg(lon, lat)
        cx, cy = _to_proj(epsg).transform(lon, lat)
        n = int(round(side_m / res))
        if n % 2 == 0:
            n += 1  # odd count so the centre falls inside a single cell
        half = n * res / 2.0
        x0 = math.floor((cx - half) / res) * res
        y0 = math.ceil((cy + half) / res) * res
        return cls(epsg=epsg, x0=x0, y0=y0, res=res, n=n)

    # ---------- geometry ----------
    @property
    def shape(self) -> tuple[int, int]:
        return (self.n, self.n)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(xmin, ymin, xmax, ymax) in the window CRS."""
        side = self.n * self.res
        return (self.x0, self.y0 - side, self.x0 + side, self.y0)

    @property
    def cell_area_m2(self) -> float:
        return self.res * self.res

    def affine(self) -> tuple[float, float, float, float, float, float]:
        """GDAL/rasterio-style affine (a, b, c, d, e, f) for writing GeoTIFFs later."""
        return (self.res, 0.0, self.x0, 0.0, -self.res, self.y0)

    def project(self, lon: float, lat: float) -> tuple[float, float]:
        return _to_proj(self.epsg).transform(lon, lat)

    def unproject(self, x: float, y: float) -> tuple[float, float]:
        return _to_geo(self.epsg).transform(x, y)

    def rowcol(self, lon: float, lat: float) -> tuple[int, int] | None:
        """Cell containing (lon, lat), or None if it falls outside the window."""
        x, y = self.project(lon, lat)
        col = int(math.floor((x - self.x0) / self.res))
        row = int(math.floor((self.y0 - y) / self.res))
        if 0 <= row < self.n and 0 <= col < self.n:
            return row, col
        return None

    def cell_centers(self) -> tuple[np.ndarray, np.ndarray]:
        """Projected x (per column) and y (per row) of cell centres, as 1-D arrays."""
        idx = np.arange(self.n) + 0.5
        return self.x0 + idx * self.res, self.y0 - idx * self.res

    def distance_from(self, lon: float, lat: float) -> np.ndarray:
        """Euclidean distance (metres) from (lon, lat) to every cell centre, shape (n, n)."""
        px, py = self.project(lon, lat)
        xs, ys = self.cell_centers()
        return np.hypot(xs[None, :] - px, ys[:, None] - py)
