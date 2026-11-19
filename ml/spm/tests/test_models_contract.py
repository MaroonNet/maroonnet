"""Every registered model must return a valid Prediction. New models are covered automatically."""

from pathlib import Path

import pytest

from spm.cases.adapters import mapscore
from spm.cases.validate import validate
from spm.eval.mapscore import score
from spm.geodata.grid import Window
from spm.models import REGISTRY

CASES, _ = validate(mapscore.load(Path(__file__).parent / "fixtures" / "mapscore"))


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_prediction_contract(name):
    model = REGISTRY[name]().fit(CASES)
    for case in CASES:
        window = Window.around(case.ipp.lon, case.ipp.lat, side_m=10_000, res=50)
        pred = model.predict(case, window)
        pred.check()  # shape, finite, non-negative, sums to 1 with p_outside
        assert -1.0 <= score(pred, case) <= 1.0


def test_ring_beats_uniform_on_close_finds():
    ring = REGISTRY["ring_pooled"]().fit(CASES)
    uni = REGISTRY["uniform"]().fit(CASES)
    case = next(c for c in CASES if c.case_id == "mapscore:T01")
    w = Window.around(case.ipp.lon, case.ipp.lat, side_m=25_000, res=50)
    assert score(ring.predict(case, w), case) > score(uni.predict(case, w), case)
