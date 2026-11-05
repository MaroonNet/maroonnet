"""Pieces of the Gate B comparison: frozen terrain weights, log-prob score, paired differences."""

import numpy as np
import pandas as pd
import pytest
from test_hybrid_find_only import find_only, hybrid, world_and_cases  # noqa: F401

from spm.eval.runner import evaluate, log_p_find, paired
from spm.features.spec import FeatureSpec
from spm.geodata.grid import Window
from spm.models.bayes import BayesModel
from spm.models.ring import RingModel
from spm.models.uniform import UniformModel
from spm.schema import Case, LonLat


def test_frozen_keeps_terrain_and_refits_only_the_ring(world_and_cases):  # noqa: F811
    world, cases = world_and_cases
    base = hybrid(world).fit(find_only(cases[:20]))
    w = base.w.copy()
    before = (dict(base.prior.params), dict(base.prior.n_fit))
    m = base.frozen("b").fit(cases[20:60])  # cases with an IPP: ring data
    np.testing.assert_array_equal(m.w, w)
    assert m.name == "b" and m.prior is not base.prior and m.prior.params
    assert (base.prior.params, base.prior.n_fit) == before  # original ring untouched
    w_ipp = hybrid(world).fit(cases[20:60]).w
    assert not np.allclose(w_ipp, w)  # an unfrozen fit would have changed the weights


def test_log_p_find_uniform_map():
    c = Case("t:1", "t", LonLat(-111.0, 34.0), "hiker", find=LonLat(-111.001, 34.001))
    w = Window.around(c.ipp.lon, c.ipp.lat, side_m=2000, res=100)
    pred = UniformModel().fit([]).predict(c, w)
    assert log_p_find(pred, c) == pytest.approx(np.log(pred.prob[w.rowcol(*c.find)]))


def test_paired_difference():
    df = pd.DataFrame(
        {
            "model": ["a", "a", "a", "b", "b", "b"],
            "case_id": [1, 2, 3, 1, 2, 3],
            "mapscore": [0.5, 0.6, 0.7, 0.4, 0.6, 0.5],
        }
    )
    r = paired(df, "a", "b")
    assert r["mean_diff"] == pytest.approx(0.1)
    assert r["frac_better"] == pytest.approx(2 / 3) and r["frac_worse"] == 0
    assert r["ci95_low"] <= r["mean_diff"] <= r["ci95_high"]


def test_model_a_runs_through_the_folds(world_and_cases):  # noqa: F811
    """Published multipliers only; the ring is refitted per fold. (The synthetic World serves
    model-resolution windows only; the sub-cell path is covered in test_aggregate.)"""
    world, cases = world_and_cases
    spec = FeatureSpec("dist_trail_m", edges=(40,), prior=(5.5, 1.0))  # Jacobs-style within/beyond
    test = cases[:6]  # cases with an IPP
    models = {"ring": RingModel, "model_a": lambda: BayesModel([spec], stack_provider=world)}
    per_case = evaluate(models, test, split="loo", res=100, side_m=12_000, stack_provider=world)
    assert set(per_case["model"]) == {"ring", "model_a"} and len(per_case) == 12
    p = per_case.pivot(index="case_id", columns="model", values="log_p_find")
    assert not np.allclose(p["model_a"], p["ring"])  # the multipliers changed the map
    assert paired(per_case, "model_a", "ring")["n_cases"] == 6


def test_combined_multiplier_is_capped_and_flagged(world_and_cases):  # noqa: F811
    from spm.features.spec import FeatureSpec
    from spm.models.bayes import BayesModel

    world, cases = world_and_cases
    Q = {"hiker": {"q25": 1.0, "q50": 2.0, "q75": 4.0}}  # noqa: N806
    big = [
        FeatureSpec("dist_trail_m", edges=(40,), prior=(5.0, 1.0), source="t p. 1"),
        FeatureSpec("dist_road_m", edges=(40,), prior=(3.0, 1.0), source="t p. 1"),
        FeatureSpec("dist_stream_m", edges=(80,), prior=(2.0, 1.0), source="t p. 1"),
    ]
    c = cases[0]
    w = Window.around(c.ipp.lon, c.ipp.lat, side_m=12_000, res=100)
    uncapped = BayesModel(big, RingModel(quantiles=Q), world, max_multiplier=None).fit([])
    capped = BayesModel(big, RingModel(quantiles=Q), world, max_multiplier=7.5).fit([])
    a, b = uncapped.predict(c, w, world(c, w)), capped.predict(c, w, world(c, w))
    b.check()
    assert a.flags is None and b.flags is not None
    ratio_a = a.prob / RingModel(quantiles=Q).fit([]).predict(c, w).prob
    assert ratio_a.max() / ratio_a.min() > 7.5  # 5 x 3 x 2 = 30x stacks exist uncapped
    assert b.flags.any() and b.flags.sum() < b.flags.size / 10
    m = hybrid(world).fit(find_only(cases[:20]))
    assert m.max_logm is not None and m.max_logm <= m.w.max() * len(m.specs) + 1e-9
