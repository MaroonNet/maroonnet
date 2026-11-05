"""The data contract shared by every part of SPM.

Everything that enters SPM becomes a ``Case``; everything a model returns is a
``Prediction``. Adapters, models, the scorer and the (P)MP export all speak
these two types and nothing else, so any piece can be swapped independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple

import numpy as np

from spm.geodata.grid import Window


class LonLat(NamedTuple):
    """WGS84 longitude/latitude in decimal degrees (EPSG:4326 axis order lon, lat)."""

    lon: float
    lat: float


@dataclass(frozen=True)
class Case:
    """One lost-person incident, harmonized from any source.

    Required for training and scoring: ``ipp``, ``find``, ``category``.
    Everything else is optional and ``None`` when the source does not say.
    """

    case_id: str  # unique across all sources, e.g. "mapscore:Arizona01"
    source: str  # adapter name, e.g. "mapscore"
    ipp: LonLat | None  # None = "no known position" case
    category: str  # canonical category (see cases/categories.py)
    find: LonLat | None = None  # None for live missions
    ipp_type: str = "unknown"  # pls | lkp | route | unknown
    category_raw: str | None = None
    age: float | None = None
    sex: str | None = None
    party_size: int | None = None
    ecoregion: str | None = None  # e.g. dry | temperate | ... (source vocabulary, lowercased)
    terrain: str | None = None  # flat | mountainous
    elapsed_h: float | None = None  # hours from last seen to found
    status: str | None = None  # well | injured | doa
    region: str | None = None  # used for leave-one-region-out splits
    notes: str | None = None
    extra: dict = field(default_factory=dict, compare=False)


@dataclass
class Prediction:
    """A probability surface over a window.

    ``prob`` holds the probability of each cell. It sums to ``1 - p_outside``;
    ``p_outside`` is the mass the model places beyond the window ("rest of world").
    """

    prob: np.ndarray
    window: Window
    model: str
    model_version: str = "0"
    p_outside: float = 0.0
    # True where the model is extrapolating (terrain unlike anything in training).
    # (P)MP can hatch these cells; None = model does not report confidence.
    flags: np.ndarray | None = None

    def check(self, atol: float = 1e-6) -> None:
        """Raise if the prediction breaks the contract."""
        if self.prob.shape != self.window.shape:
            raise ValueError(f"prob shape {self.prob.shape} != window shape {self.window.shape}")
        if not np.all(np.isfinite(self.prob)):
            raise ValueError("prob contains NaN or inf")
        if np.any(self.prob < 0):
            raise ValueError("prob contains negative values")
        if not 0.0 <= self.p_outside <= 1.0:
            raise ValueError(f"p_outside {self.p_outside} not in [0, 1]")
        total = float(self.prob.sum()) + self.p_outside
        if abs(total - 1.0) > atol:
            raise ValueError(f"prob.sum() + p_outside = {total}, expected 1")
