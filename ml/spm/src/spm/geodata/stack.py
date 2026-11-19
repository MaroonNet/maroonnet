"""FeatureStack: the terrain layers for one window, all on the same grid.

Base layers (names are the contract; builders in step 3 must use them):

    dem            elevation, metres (float)
    trail_mask     True where a trail passes through the cell
    road_mask      True where a road passes through the cell
    stream_mask    True where a stream or drainage line passes through the cell
    watershed_id   integer watershed unit (e.g. WBD HUC-12), 0 = unknown
    landcover      integer land-cover class (NLCD codes)

Any layer may be missing; models use what exists. Real stacks come from
3DEP / OSM + NPS trails / NHD / WBD / NLCD (build step 3). Until then,
``spm.geodata.synthetic`` makes fake stacks with the same layer names so the
models and tests can be written now.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from spm.geodata.grid import Window

BASE_LAYERS = ("dem", "trail_mask", "road_mask", "stream_mask", "watershed_id", "landcover")


@dataclass
class FeatureStack:
    window: Window
    layers: dict[str, np.ndarray] = field(default_factory=dict)
    source: str = "unknown"  # e.g. "3dep+osm+wbd 2026-10" or "synthetic seed=3"

    def __post_init__(self):
        for name, arr in self.layers.items():
            if arr.shape != self.window.shape:
                raise ValueError(
                    f"layer {name} has shape {arr.shape}, window is {self.window.shape}"
                )

    def has(self, name: str) -> bool:
        return name in self.layers

    def __getitem__(self, name: str) -> np.ndarray:
        return self.layers[name]
