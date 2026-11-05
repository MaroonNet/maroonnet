"""Travel time from the IPP over the terrain: the least hours needed to reach each cell.

Walking speed follows Tobler's hiking function (Tobler, W., 1993, "Three
presentations on geographical analysis and modeling", NCGIA Technical Report
93-1):

    speed (km/h) = 6 * exp(-3.5 * |S + 0.05|)      S = rise / run (tangent)

which peaks at about 5 km/h on a slight downhill and falls steeply with grade.
Tobler's note for off-path travel is to multiply by 0.6; cells joined by a
trail keep the full speed. The surface is the shortest-time path on the
8-connected grid (Dijkstra), with uphill and downhill edges costed separately.

What this is for: early in a search, cells that cannot be reached in the
time elapsed cannot hold the subject; see ``models.update.apply_time_cap``.
The published speeds describe a walker on purpose, not a lost person
(Hashimoto et al. 2022 fit a much lower effective speed for lost hikers), so
the cap is generous by design. ``max_slope_deg`` makes steeper cells
impassable; it is off by default because no value is cited here (a 31 degree
cut-off is used by travel-time models summarized in Ewers et al., arXiv
2412.13317; the team should decide and cite).
"""

from __future__ import annotations

import math

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

TOBLER_MAX_KMH = 6.0
TOBLER_RATE = 3.5
TOBLER_OFFSET = 0.05
OFF_PATH_FACTOR = 0.6

OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def tobler_kmh(slope: np.ndarray, on_path: np.ndarray | bool = False) -> np.ndarray:
    """Walking speed in km/h for a rise/run ``slope``; ``on_path`` False applies the 0.6 factor."""
    v = TOBLER_MAX_KMH * np.exp(-TOBLER_RATE * np.abs(slope + TOBLER_OFFSET))
    return np.where(on_path, v, v * OFF_PATH_FACTOR)


def travel_hours(
    dem: np.ndarray,
    res: float,
    start_rc: tuple[int, int],
    trail_mask: np.ndarray | None = None,
    max_slope_deg: float | None = None,
) -> np.ndarray:
    """(n, n) hours from ``start_rc`` to every cell; inf where unreachable (no elevation,
    or only via slopes steeper than ``max_slope_deg``)."""
    n_rows, n_cols = dem.shape
    dem = dem.astype(float)
    idx = np.arange(n_rows * n_cols).reshape(n_rows, n_cols)
    trail = np.zeros(dem.shape, bool) if trail_mask is None else trail_mask.astype(bool)
    max_tan = None if max_slope_deg is None else math.tan(math.radians(max_slope_deg))

    src, dst, hours = [], [], []
    for dr, dc in OFFSETS:
        r0, r1 = max(0, -dr), n_rows - max(0, dr)
        c0, c1 = max(0, -dc), n_cols - max(0, dc)
        a = idx[r0:r1, c0:c1]  # from
        b = idx[r0 + dr : r1 + dr, c0 + dc : c1 + dc]  # to
        za, zb = dem[r0:r1, c0:c1], dem[r0 + dr : r1 + dr, c0 + dc : c1 + dc]
        run = res * math.hypot(dr, dc)
        slope = (zb - za) / run
        on_path = trail[r0:r1, c0:c1] & trail[r0 + dr : r1 + dr, c0 + dc : c1 + dc]
        ok = np.isfinite(slope)
        if max_tan is not None:
            ok &= np.abs(slope) <= max_tan
        speed_m_h = tobler_kmh(np.where(ok, slope, 0.0), on_path) * 1000.0
        src.append(a[ok])
        dst.append(b[ok])
        hours.append(run / speed_m_h[ok])
    n = n_rows * n_cols
    graph = coo_matrix(
        (np.concatenate(hours), (np.concatenate(src), np.concatenate(dst))), shape=(n, n)
    ).tocsr()
    start = int(idx[start_rc])
    out = dijkstra(graph, directed=True, indices=start)
    return out.reshape(dem.shape)
