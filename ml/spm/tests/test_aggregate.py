import zlib

import numpy as np
import pytest

from spm.features import aggregate, relative
from spm.features.spec import FeatureSpec
from spm.geodata.grid import Window
from spm.geodata.synthetic import make_stack

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
