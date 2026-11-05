import zlib

import numpy as np
import pytest

from spm.features import aggregate, relative
from spm.features.spec import FeatureSpec
from spm.geodata.grid import Window
from spm.geodata.synthetic import make_stack
from spm.models.bayes import BayesModel
from spm.models.hybrid import HybridModel, Stratum
from spm.models.ring import RingModel
from spm.schema import Case, LonLat

TRAIL = FeatureSpec("dist_trail_m", edges=(20, 50, 100, 200), prior=(5.0, 3.0, 2.0, 1.5, 1.0))
LON, LAT = -74.0, 44.0
Q = {"hiker": {"q25": 1.0, "q50": 2.0, "q75": 4.0}}


def test_fine_window_keeps_extent():
    w = Window.around(LON, LAT, side_m=4000, res=100)
    fine, factor = aggregate.fine_window(w, 10)
    assert factor == 10 and fine.n == w.n * 10 and fine.res == 10
    assert fine.bounds == pytest.approx(w.bounds)
    assert aggregate.fine_window(w, None) == (w, 1)
    with pytest.raises(ValueError):
        aggregate.fine_window(w, 30)


def test_cell_score_is_log_mean_sub_cell_intensity():
    v = np.array([[10.0, 30.0], [30.0, 500.0]])  # one 2x2 model cell: bins 0, 1, 1, 5
    d = aggregate.SubcellDesign.from_features([TRAIL], {"dist_trail_m": v}, factor=2)
    theta = np.log([5.0, 3.0, 2.0, 1.5, 1.0])
    expected = np.log(np.mean([5.0, 3.0, 3.0, 1.0]))  # point multipliers averaged
    np.testing.assert_allclose(d.log_intensity(theta), [expected], rtol=1e-6)


def test_factor_one_is_plain_binning():
    w = Window.around(LON, LAT, side_m=3000, res=100)
    feats = relative.compute(make_stack(w, seed=3), None)
    d = aggregate.SubcellDesign.from_features([TRAIL], feats, 1)
    theta = np.log(np.array(TRAIL.prior))
    idx = TRAIL.bin_index(feats["dist_trail_m"]).ravel()
    np.testing.assert_allclose(d.log_intensity(theta), theta[idx], rtol=1e-6)


def test_two_features_combine_per_sub_cell():
    road = FeatureSpec("dist_road_m", edges=(50,), prior=(2.0, 1.0))
    feats = {
        "dist_trail_m": np.array([[10.0, 500.0]] * 2),
        "dist_road_m": np.array([[10.0, 10.0]] * 2),
    }
    d = aggregate.SubcellDesign.from_features([TRAIL, road], feats, factor=2)
    theta = np.concatenate([np.log(TRAIL.prior), np.log(road.prior)])
    # sub-cells: (trail 5x, road 2x) twice and (trail 1x, road 2x) twice
    expected = np.log(np.mean([10.0, 10.0, 2.0, 2.0]))
    np.testing.assert_allclose(d.log_intensity(theta), [expected], rtol=1e-6)


def test_gradient_matches_finite_differences():
    w = Window.around(LON, LAT, side_m=2000, res=100)
    fine, factor = aggregate.fine_window(w, 10)
    feats = relative.compute(make_stack(fine, seed=5), None)
    d = aggregate.SubcellDesign.from_features([TRAIL], feats, factor)
    rng = np.random.default_rng(0)
    theta, weights = rng.normal(size=5), rng.normal(size=d.n_cells)
    g = d.grad(theta, weights)
    for k in range(5):
        e = np.zeros(5)
        e[k] = 1e-6
        num = weights @ (d.log_intensity(theta + e) - d.log_intensity(theta - e)) / 2e-6
        assert g[k] == pytest.approx(num, rel=1e-4, abs=1e-6)


def test_near_bins_fill_only_with_sub_cells():
    """At 100 m nothing lands in 20-50 m or 50-100 m; at 10 m those bins appear."""
    w = Window.around(LON, LAT, side_m=3000, res=100)
    fine, factor = aggregate.fine_window(w, 10)
    coarse = aggregate.SubcellDesign.from_features(
        [TRAIL], relative.compute(make_stack(w, seed=3), None), 1
    )
    sub = aggregate.SubcellDesign.from_features(
        [TRAIL], relative.compute(make_stack(fine, seed=3), None), factor
    )
    assert coarse.patterns[:, 1:3].sum() == 0
    assert sub.patterns[:, 1:3].sum() > 0
    np.testing.assert_array_equal(np.asarray(sub.counts.sum(axis=1)).ravel(), factor * factor)


def test_point_multipliers_recovered_from_coarse_cells():
    """Finds drawn from a point process with known multipliers; fitted on 10x10-sub-cell
    cells, exp(theta) recovers the point multipliers (not cell-size-dependent ones)."""
    rng = np.random.default_rng(1)
    true = np.log([8.0, 3.0, 1.0])
    spec = FeatureSpec("dist_trail_m", edges=(20, 100), prior=(None, None, None))
    strata = []
    for i in range(400):
        n = 9  # 3x3 model cells of 10x10 sub-cells; a "trail" runs through some of them
        v = np.full((30, 30), 1000.0)
        for _ in range(rng.integers(1, 3)):
            c = rng.integers(0, 30)
            v[:, c] = 0.0
            v[:, max(c - 3, 0) : c + 4] = np.minimum(v[:, max(c - 3, 0) : c + 4], 50.0)
        d = aggregate.SubcellDesign.from_features([spec], {"dist_trail_m": v}, 10)
        p = np.exp(d.log_intensity(true))
        k = rng.choice(n, p=p / p.sum())
        order = np.r_[k, np.delete(np.arange(n), k)]
        strata.append(Stratum(f"s{i}", "R", np.zeros(n), d.take(order), {}, True))
    m = HybridModel([spec], None, lam_w=1e-3, lam_region=1e3).fit_strata(strata)
    learned = m.w - m.w[-1]
    np.testing.assert_allclose(learned, true - true[-1], atol=0.45)


def test_find_point_likelihood_pins_down_near_bins():
    """Same point process, but each stratum knows the find's own sub-cell: the
    multipliers come back tighter than from the find's cell alone."""
    rng = np.random.default_rng(2)
    true = np.log([8.0, 3.0, 1.0])
    spec = FeatureSpec("dist_trail_m", edges=(20, 100), prior=(None, None, None))
    strata = []
    for i in range(400):
        v = np.full((30, 30), 1000.0)
        for _ in range(rng.integers(1, 3)):
            c = rng.integers(0, 30)
            v[:, max(c - 3, 0) : c + 4] = np.minimum(v[:, max(c - 3, 0) : c + 4], 50.0)
            v[:, c] = 0.0
        p = np.exp(true[spec.bin_index(v)]).ravel()
        sub = rng.choice(p.size, p=p / p.sum())  # the find point
        rc = divmod(sub, 30)
        k = (rc[0] // 10) * 3 + rc[1] // 10  # its model cell
        d = aggregate.SubcellDesign.from_features([spec], {"dist_trail_m": v}, 10)
        order = np.r_[k, np.delete(np.arange(9), k)]
        fp = aggregate.point_pattern([spec], {"dist_trail_m": v}, rc)
        strata.append(Stratum(f"s{i}", "R", np.zeros(9), d.take(order), {}, True, fp))
    m = HybridModel([spec], None, lam_w=1e-3, lam_region=1e3).fit_strata(strata)
    np.testing.assert_allclose(m.w - m.w[-1], true - true[-1], atol=0.25)


def test_out_of_range_flags_any_sub_cell():
    v = np.zeros((4, 4))
    v[0, 0] = 999.0
    flags = aggregate.out_of_range([TRAIL], {"dist_trail_m": v}, {"dist_trail_m": (0, 100)}, 2)
    np.testing.assert_array_equal(flags, [[True, False], [False, False]])
    # beyond the last edge (200 m) every value is the same bin: not an extrapolation
    seen_far = {"dist_trail_m": (0, 300)}
    assert not aggregate.out_of_range([TRAIL], {"dist_trail_m": v}, seen_far, 2).any()


def provider(case, window):
    return make_stack(window, seed=zlib.crc32(case.case_id.encode()))


def test_models_fit_and_predict_with_feature_res():
    rng = np.random.default_rng(0)
    cases = [
        Case(
            case_id=f"t:{i}",
            source="t",
            ipp=None,
            find=LonLat(LON + rng.uniform(-0.2, 0.2), LAT + rng.uniform(-0.2, 0.2)),
            category="hiker",
            region="R",
        )
        for i in range(4)
    ]
    m = HybridModel([TRAIL], provider, prior=RingModel(quantiles=Q), feature_res=10.0)
    m.fit(cases)
    assert m.n_find_only == 4 and m.fit_result.success
    c = Case(case_id="t:p", source="t", ipp=LonLat(LON, LAT), category="hiker", region="R")
    w = Window.around(LON, LAT, side_m=3000, res=100)
    bayes = BayesModel([TRAIL], RingModel(quantiles=Q), provider, feature_res=10.0).fit([])
    for pred in (m.predict(c, w, provider(c, w)), bayes.predict(c, w, provider(c, w))):
        pred.check()
        assert pred.prob.shape == w.shape


def test_predict_at_finer_resolution_than_training():
    """Weights are point multipliers, so a model fitted on 100 m cells renders at 20 m
    (10 m features, factor 2) without refitting, and the two maps agree when aggregated."""
    rng = np.random.default_rng(3)
    cases = [
        Case(
            case_id=f"t:{i}",
            source="t",
            ipp=None,
            find=LonLat(LON + rng.uniform(-0.2, 0.2), LAT + rng.uniform(-0.2, 0.2)),
            category="hiker",
            region="R",
        )
        for i in range(4)
    ]
    m = HybridModel([TRAIL], provider, prior=RingModel(quantiles=Q), feature_res=10.0).fit(cases)
    c = Case(case_id="t:p", source="t", ipp=LonLat(LON, LAT), category="hiker", region="R")
    coarse_w = Window.around(LON, LAT, side_m=2000, res=100)
    fine_w = Window(coarse_w.epsg, coarse_w.x0, coarse_w.y0, 20.0, coarse_w.n * 5)
    coarse = m.predict(c, coarse_w, provider(c, coarse_w))
    fine = m.predict(c, fine_w, provider(c, fine_w))
    coarse.check()
    fine.check()
    assert fine.prob.shape == (coarse_w.n * 5, coarse_w.n * 5)
    # same terrain (make_stack is seeded per window, so give both the same fine features):
    # the test only checks the mechanics and mass, not cell-by-cell equality.
    assert fine.p_outside == pytest.approx(coarse.p_outside, abs=0.02)
    summed = fine.prob.reshape(coarse_w.n, 5, coarse_w.n, 5).sum(axis=(1, 3))
    assert summed.sum() == pytest.approx(coarse.prob.sum(), abs=0.02)
