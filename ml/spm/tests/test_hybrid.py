"""The prior-art and hybrid models on synthetic terrain.

These tests check the math and the plumbing: that a known terrain effect
planted in synthetic data is recovered, that learning beats the ring on an
unseen region when the effect is real, and that pooling and fallback behave.
They say nothing about how real lost people behave.
"""

import zlib

import numpy as np
import pytest

from spm.eval.mapscore import score
from spm.features import relative
from spm.features.spec import FeatureSpec
from spm.geodata.grid import Window
from spm.geodata.synthetic import make_stack
from spm.models.bayes import BayesModel
from spm.models.hybrid import HybridModel
from spm.models.ring import RingModel
from spm.schema import Case, LonLat

SIDE, RES = 12_000, 100
Q = {"hiker": {"q25": 1.0, "q50": 2.0, "q75": 4.0}}
TRAIL = FeatureSpec("dist_trail_m", edges=(100, 300), prior=(None, None, None))
TRUE_TRAIL_LOGM = np.log([6.0, 2.0, 1.0])  # planted: finds strongly drawn to trails
REGIONS = {"R1": (-111.0, 34.0), "R2": (-119.5, 37.8), "R3": (-74.0, 44.0)}


def stack_for(case, window):
    return make_stack(window, seed=zlib.crc32(case.case_id.encode()))


def make_cases(n_per_region=25, seed=0):
    rng = np.random.default_rng(seed)
    ring = RingModel(quantiles=Q).fit([])
    cases = []
    for reg, (lon0, lat0) in REGIONS.items():
        for i in range(n_per_region):
            cid = f"syn:{reg}-{i}"
            ipp = LonLat(lon0 + rng.uniform(-0.3, 0.3), lat0 + rng.uniform(-0.3, 0.3))
            c = Case(case_id=cid, source="syn", ipp=ipp, category="hiker", region=reg)
            w = Window.around(ipp.lon, ipp.lat, side_m=SIDE, res=RES)
            feats = relative.compute(stack_for(c, w), w.rowcol(ipp.lon, ipp.lat))
            p = ring.predict(c, w).prob * np.exp(
                TRUE_TRAIL_LOGM[TRAIL.bin_index(feats["dist_trail_m"])]
            )
            k = rng.choice(p.size, p=(p / p.sum()).ravel())
            xs, ys = w.cell_centers()
            find = LonLat(*w.unproject(xs[k % w.n], ys[k // w.n]))
            cases.append(
                Case(case_id=cid, source="syn", ipp=ipp, find=find, category="hiker", region=reg)
            )
    return cases


@pytest.fixture(scope="module")
def cases():
    return make_cases()


def hybrid(**kw):
    return HybridModel([TRAIL], stack_for, prior=RingModel(quantiles=Q), side_m=SIDE, res=RES, **kw)


def mean_score(model, test):
    out = []
    for c in test:
        w = Window.around(c.ipp.lon, c.ipp.lat, side_m=SIDE, res=RES)
        pred = model.predict(c, w, stack_for(c, w))
        pred.check()
        out.append(score(pred, c))
    return float(np.mean(out))


def test_bayes_with_blank_config_equals_ring(cases):
    c = cases[0]
    w = Window.around(c.ipp.lon, c.ipp.lat, side_m=SIDE, res=RES)
    ring = RingModel(quantiles=Q).fit([]).predict(c, w)
    bayes = BayesModel([TRAIL], prior=RingModel(quantiles=Q)).fit([]).predict(c, w, stack_for(c, w))
    assert np.allclose(ring.prob, bayes.prob)


def test_bayes_applies_published_multipliers(cases):
    filled = FeatureSpec("dist_trail_m", edges=(100, 300), prior=(6.0, 2.0, 1.0))
    model = BayesModel([filled], prior=RingModel(quantiles=Q)).fit([])
    assert mean_score(model, cases[:20]) > mean_score(RingModel(quantiles=Q).fit([]), cases[:20])


def test_hybrid_recovers_planted_trail_effect(cases):
    m = hybrid(lam_w=0.1, lam_region=50).fit(cases)
    learned = np.log(m.multipliers()["dist_trail_m"])
    learned -= learned[-1]  # compare shape relative to the far bin
    assert learned[0] > learned[1] > 0.3
    assert learned[0] == pytest.approx(TRUE_TRAIL_LOGM[0], abs=0.6)


def test_hybrid_transfers_to_unseen_region(cases):
    train = [c for c in cases if c.region != "R3"]
    test = [c for c in cases if c.region == "R3"]
    m = hybrid().fit(train)
    assert "R3" not in m.delta  # never seen: uses the shared weights only
    assert mean_score(m, test) > mean_score(RingModel(quantiles=Q).fit([]), test)


def test_region_offsets_shrink_toward_zero(cases):
    loose = hybrid(lam_region=0.01).fit(cases)
    tight = hybrid(lam_region=100.0).fit(cases)
    size = lambda m: sum(np.abs(d).sum() for d in m.delta.values())  # noqa: E731
    assert size(tight) < size(loose)


def test_out_of_range_cells_flagged(cases):
    m = hybrid().fit(cases[:10])
    m.ranges["dist_trail_m"] = (0.0, 150.0)  # pretend training never saw cells far from trails
    c = cases[30]
    w = Window.around(c.ipp.lon, c.ipp.lat, side_m=SIDE, res=RES)
    pred = m.predict(c, w, stack_for(c, w))
    assert pred.flags is not None and pred.flags.any() and not pred.flags.all()
    pred.check()
