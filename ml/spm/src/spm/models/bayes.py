"""Prior-art model: ring prior x published terrain multipliers (no training).

    P(cell) proportional to ring(cell) x product over features of multiplier[bin of cell]

This is the Bayesian combination step of SPM v1.1 §3.1, built only from
published numbers (Koester 2008 rings; Doke 2012 / Sava et al. 2016 watershed;
Jacobs 2015 terrain multipliers). It is the fall deliverable and the baseline
the learned hybrid has to beat.

Features whose multipliers are not filled in configs/prior_art.yaml are
skipped, so with an empty config this model equals the ring model.
"""

from __future__ import annotations

import numpy as np

from spm.features import aggregate, relative
from spm.features.spec import FeatureSpec
from spm.models.ring import RingModel
from spm.schema import Prediction


def apply_log_multipliers(
    ring: Prediction, logm: np.ndarray, name: str, version: str
) -> Prediction:
    """Reweight a ring prediction by exp(logm), keeping the ring's in-window mass."""
    inside = 1.0 - ring.p_outside
    w = ring.prob * np.exp(logm - logm.max())
    total = w.sum()
    prob = w * (inside / total) if total > 0 else ring.prob
    return Prediction(
        prob=prob, window=ring.window, model=name, model_version=version, p_outside=ring.p_outside
    )


# Model A is the published model and stays that way: only features whose bins and values
# are as published (FeatureSpec.published), no cap, nothing fitted but the ring. The
# ``max_multiplier`` parameter exists for experiments; ``spm fit`` never sets it.


class BayesModel:
    name = "bayes_prior_art"
    version = "1"

    def __init__(
        self,
        specs: list[FeatureSpec],
        prior: RingModel | None = None,
        stack_provider=None,
        feature_res: float | None = None,
        max_multiplier: float | None = None,
    ):
        """``stack_provider`` + ``feature_res``: bin features on a fine grid, as HybridModel.

        ``max_multiplier`` caps the product of the per-feature multipliers; cells that hit
        it are flagged.
        """
        self.specs = [s for s in specs if s.prior_complete and s.published]
        self.prior = prior or RingModel()
        self.stack_provider = stack_provider
        self.feature_res = feature_res
        self.max_multiplier = max_multiplier

    def fit(self, cases):
        self.prior.fit(cases)  # only the ring distances are fitted; multipliers are published
        return self

    def predict(self, case, window, stack=None):
        ring = self.prior.predict(case, window)
        if stack is None or not self.specs:
            return apply_log_multipliers(ring, np.zeros(window.shape), self.name, self.version)
        fine, factor = window, 1
        if self.feature_res is not None and self.stack_provider is not None:
            fine, factor = aggregate.fine_window(window, self.feature_res)
            stack = self.stack_provider(case, fine)
            if stack is None:
                return apply_log_multipliers(ring, np.zeros(window.shape), self.name, self.version)
        feats = relative.compute(stack, fine.rowcol(case.ipp.lon, case.ipp.lat))
        design = aggregate.SubcellDesign.from_features(self.specs, feats, factor)
        logm = design.log_intensity(np.concatenate([s.log_prior() for s in self.specs]))
        logm = logm.reshape(window.shape)
        flags = aggregate.no_data(stack, factor)
        if self.max_multiplier is not None:
            flags |= logm > np.log(self.max_multiplier)
            logm = np.minimum(logm, np.log(self.max_multiplier))
        pred = apply_log_multipliers(ring, logm, self.name, self.version)
        pred.flags = flags
        return pred
