"""Binned feature specs shared by the prior-art model and the learned hybrid.

Each feature is cut into bins (e.g. distance to trail: 0-20 m, 20-50 m, ...).
The prior-art model multiplies probability by a published value per bin; the
hybrid learns a log-multiplier per bin, starting from those published values.
Using the same bins in both keeps "published" and "learned" directly comparable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml


@dataclass(frozen=True)
class FeatureSpec:
    name: str  # a key of features.relative.FEATURES
    edges: tuple[float, ...]  # inner bin edges; len(edges)+1 bins
    prior: tuple[float | None, ...]  # published multiplier per bin (None = not filled in)
    source: str = ""
    # True when the bins AND the values are as published, so Model A may use the feature.
    # False when the values are published but the feature definition is ours (Model B only).
    published: bool = True
    # Bin for cells where the feature cannot be computed (no elevation data, for example).
    # None = the last bin, right for distance features ("beyond"); elev_pos sets its
    # reference bin so missing terrain never reads as "high ground".
    missing_bin: int | None = None

    @property
    def n_bins(self) -> int:
        return len(self.edges) + 1

    @property
    def prior_complete(self) -> bool:
        return all(v is not None for v in self.prior)

    def bin_index(self, values: np.ndarray) -> np.ndarray:
        """Bin number (0..n_bins-1) of each value; non-finite values go to ``missing_bin``."""
        finite = np.isfinite(values)
        idx = np.digitize(np.where(finite, values, 0.0), self.edges, right=False)
        miss = self.n_bins - 1 if self.missing_bin is None else self.missing_bin
        return np.where(finite, idx, miss).astype(np.int16)

    def log_prior(self) -> np.ndarray:
        """Published log-multipliers; unfilled bins default to log(1) = 0 (no effect)."""
        return np.array([math.log(v) if v else 0.0 for v in self.prior])


def load_specs(path: Path) -> list[FeatureSpec]:
    cfg = yaml.safe_load(Path(path).read_text()) or {}
    specs = []
    for name, f in (cfg.get("features") or {}).items():
        edges = tuple(float(e) for e in f["edges"])
        prior = tuple(f.get("multipliers") or [None] * (len(edges) + 1))
        if len(prior) != len(edges) + 1:
            raise ValueError(
                f"{name}: {len(edges)} edges need {len(edges) + 1} multipliers, got {len(prior)}"
            )
        specs.append(
            FeatureSpec(
                name=name,
                edges=edges,
                prior=prior,
                source=f.get("source", ""),
                published=bool(f.get("published", True)),
                missing_bin=f.get("missing_bin"),
            )
        )
    return specs
