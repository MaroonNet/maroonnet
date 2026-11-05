"""The one interface every SPM model implements.

    model.fit(train_cases)                 -> learns whatever it needs (may do nothing)
    model.predict(case, window, stack)     -> Prediction on that window

``stack`` is the terrain feature stack for the window (elevation, land cover,
distance to trails, ...). It is None until terrain stacks exist (build step 3);
models that do not use terrain ignore it.
"""

from __future__ import annotations

from typing import Any, Protocol

from spm.geodata.grid import Window
from spm.schema import Case, Prediction


class Model(Protocol):
    name: str
    version: str

    def fit(self, cases: list[Case]) -> Model: ...

    def predict(self, case: Case, window: Window, stack: Any | None = None) -> Prediction: ...
