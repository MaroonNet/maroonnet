"""Sanity baseline: every cell equally likely. MapScore of a uniform map is exactly 0."""

from __future__ import annotations

import numpy as np

from spm.schema import Prediction


class UniformModel:
    name = "uniform"
    version = "1"

    def fit(self, cases):
        return self

    def predict(self, case, window, stack=None):
        prob = np.full(window.shape, 1.0 / (window.n * window.n))
        return Prediction(prob=prob, window=window, model=self.name, model_version=self.version)
