"""Distance ring model (Koester 2008, Lost Person Behavior).

Probability depends only on straight-line distance from the IPP, following a
lognormal distance distribution per subject category. This matches the ring
model scored in Sava et al. (2016) and the lognormal ring code in the MapScore
repository (arc-models/EucDistLognormals.py).

Two ways to get the per-category distributions:

1. Fit from training cases (default). ``fit`` estimates mu and sigma of
   log(distance km) per category; categories with fewer than
   ``min_cases`` cases fall back to the pooled fit over all categories.
2. From published quantiles. Pass ``quantiles={"hiker": {"q25": .., "q50": .., "q75": ..}}``
   in km (for example Lost Person Behavior's tables, typed into
   configs/ring_quantiles.yaml). The lognormal is matched to the median and
   interquartile range. Published entries override fitted ones.

Cell probability: the radial density f(d) is spread evenly around the ring at
distance d, so the density per unit area is f(d) / (2 * pi * d), times the cell
area. Mass that falls beyond the window becomes ``p_outside``.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm

from spm.cases.validate import haversine_m
from spm.schema import Prediction

Z75 = norm.ppf(0.75)  # 0.6745: quartile z-score of the standard normal


def lognormal_from_quartiles(q25: float, q50: float, q75: float) -> tuple[float, float]:
    """(mu, sigma) of log-distance from published 25/50/75% distances."""
    return math.log(q50), (math.log(q75) - math.log(q25)) / (2 * Z75)


class RingModel:
    name = "ring"
    version = "1"

    def __init__(
        self, min_cases: int = 8, quantiles: dict | None = None, pooled_only: bool = False
    ):
        self.min_cases = min_cases
        self.quantiles = quantiles or {}
        self.pooled_only = pooled_only
        self.params: dict[str, tuple[float, float]] = {}
        self.n_fit: dict[str, int] = {}
        if pooled_only:
            self.name = "ring_pooled"

    def fit(self, cases):
        logs: dict[str, list[float]] = {}
        for c in cases:
            if c.ipp is None or c.find is None:
                continue
            d_km = _dist_km(c)
            if d_km <= 0:
                continue
            logs.setdefault("__all__", []).append(math.log(d_km))
            if not self.pooled_only:
                logs.setdefault(c.category, []).append(math.log(d_km))
        self.params, self.n_fit = {}, {}
        for cat, v in logs.items():
            if cat == "__all__" or len(v) >= self.min_cases:
                self.params[cat] = (
                    float(np.mean(v)),
                    float(np.std(v, ddof=1)) if len(v) > 1 else 1.0,
                )
                self.n_fit[cat] = len(v)
        for cat, q in self.quantiles.items():
            self.params[cat] = lognormal_from_quartiles(q["q25"], q["q50"], q["q75"])
            self.n_fit[cat] = -1  # marks "from published table"
        return self

    def params_for(self, category: str) -> tuple[float, float]:
        if not self.pooled_only and category in self.params:
            return self.params[category]
        return self.params["__all__"]

    def predict(self, case, window, stack=None):
        if case.ipp is None:
            raise NotImplementedError(
                "ring model needs an IPP; no-known-position handling is a later step"
            )
        mu, sigma = self.params_for(case.category)
        d_km = window.distance_from(case.ipp.lon, case.ipp.lat) / 1000.0
        d_km = np.maximum(d_km, window.res / 4000.0)  # avoid d = 0 at the IPP cell
        radial = np.exp(-((np.log(d_km) - mu) ** 2) / (2 * sigma**2)) / (
            d_km * sigma * math.sqrt(2 * math.pi)
        )
        prob = radial / (2 * math.pi * d_km) * (window.cell_area_m2 / 1e6)
        inside = float(prob.sum())
        if inside > 1.0:
            prob /= inside
            inside = 1.0
        return Prediction(
            prob=prob,
            window=window,
            model=self.name,
            model_version=self.version,
            p_outside=1.0 - inside,
        )


def _dist_km(c) -> float:
    return haversine_m(c.ipp, c.find) / 1000.0
