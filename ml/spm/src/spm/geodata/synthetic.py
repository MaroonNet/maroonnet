"""Fake terrain stacks with the real layer names.

For tests and for developing models before real terrain stacks exist. Nothing
learned from synthetic stacks says anything about real people or real terrain.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from spm.geodata.grid import Window
from spm.geodata.stack import FeatureStack


def make_stack(window: Window, seed: int = 0, relief_m: float = 800.0) -> FeatureStack:
    rng = np.random.default_rng(seed)
    n = window.n
    # Smooth random terrain: filtered noise plus a regional tilt.
    noise = ndimage.gaussian_filter(rng.normal(size=(n, n)), sigma=n / 12)
    noise = (noise - noise.min()) / (np.ptp(noise) + 1e-9)
    yy, xx = np.mgrid[0:n, 0:n] / n
    dem = 2500.0 + relief_m * (
        0.8 * noise + 0.2 * (rng.uniform(-1, 1) * xx + rng.uniform(-1, 1) * yy)
    )

    # Drainages: cells well below their neighbourhood.
    local = ndimage.uniform_filter(dem, size=max(3, n // 15), mode="nearest")
    stream = (dem - local) < -np.percentile(np.abs(dem - local), 85)

    # Trails: a few straight lines through the window; one road.
    def line_mask(count):
        m = np.zeros((n, n), bool)
        for _ in range(count):
            r0, c0, r1, c1 = rng.integers(0, n, size=4)
            k = max(abs(r1 - r0), abs(c1 - c0)) + 1
            m[np.linspace(r0, r1, k).astype(int), np.linspace(c0, c1, k).astype(int)] = True
        return m

    # Watersheds: split along a random line (two units, ids 1 and 2).
    a = rng.uniform(0, np.pi)
    ws = np.where(np.cos(a) * (xx - 0.5) + np.sin(a) * (yy - 0.5) > rng.uniform(-0.2, 0.2), 1, 2)

    return FeatureStack(
        window=window,
        source=f"synthetic seed={seed}",
        layers={
            "dem": dem,
            "trail_mask": line_mask(3),
            "road_mask": line_mask(1),
            "stream_mask": stream,
            "watershed_id": ws.astype(np.int32),
        },
    )
