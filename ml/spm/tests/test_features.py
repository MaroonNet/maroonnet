import re
from pathlib import Path

import numpy as np
import pytest

from spm.features import relative
from spm.features.spec import FeatureSpec, load_specs
from spm.geodata.grid import Window
from spm.geodata.synthetic import make_stack

CFG = Path(__file__).parents[1] / "configs" / "prior_art.yaml"


def test_distance_to_mask():
    m = np.zeros((5, 5), bool)
    m[2, 2] = True
    d = relative.distance_to(m, res=10)
    assert (
        d[2, 2] == 0 and d[2, 4] == pytest.approx(20) and d[0, 0] == pytest.approx(np.hypot(20, 20))
    )


def test_distance_to_empty_mask_is_inf():
    assert np.isinf(relative.distance_to(np.zeros((3, 3), bool), 10)).all()


def test_elevation_change_zero_at_ipp_and_signed():
    dem = np.arange(25.0).reshape(5, 5)
    e = relative.elevation_change(dem, (2, 2))
    assert e[2, 2] == 0 and e[4, 4] > 0 and e[0, 0] < 0


def test_tpi_negative_in_valley():
    yy, xx = np.mgrid[0:41, 0:41]
    dem = np.abs(xx - 20).astype(float) * 10  # V-shaped valley along column 20
    t = relative.tpi(dem, res=10, radius_m=50)
    assert t[20, 20] < 0 and t[20, 5] == pytest.approx(0, abs=1e-6)


def test_compute_on_synthetic_stack_has_all_features():
    w = Window.around(-105.6, 40.25, side_m=5_000, res=50)
    feats = relative.compute(make_stack(w, seed=1), w.rowcol(-105.6, 40.25))
    assert set(feats) == set(relative.FEATURES)
    assert all(a.shape == w.shape for a in feats.values())


def test_spec_binning_and_config_loads():
    s = FeatureSpec("dist_trail_m", edges=(20, 50), prior=(3.0, 1.5, None))
    assert s.bin_index(np.array([0, 20, 49, 50, np.inf, np.nan])).tolist() == [0, 1, 1, 2, 2, 2]
    assert not s.prior_complete
    specs = load_specs(CFG)
    assert {sp.name for sp in specs} <= set(relative.FEATURES)
    for sp in specs:  # anything filled in must say where it came from, with a page
        if sp.prior_complete:
            assert re.search(r"p\. ?\d+", sp.source), f"{sp.name}: source needs a page reference"


def test_interface_and_elevation_position():
    lon, lat = -74.0, 44.0
    w = Window.around(lon, lat, side_m=3000, res=100)
    feats = relative.compute(make_stack(w, seed=4), w.rowcol(lon, lat))
    inter = feats["interface_m"]
    assert np.all(inter >= feats["dist_trail_m"]) and np.all(inter >= feats["dist_stream_m"])
    assert (inter <= 80).sum() <= (feats["dist_trail_m"] <= 80).sum()  # subset of near-trail
    pos = feats["elev_pos"]
    assert pos.shape == w.shape and pos.min() >= 0 and pos.max() <= 1
    assert (pos < 0.2).any() and (pos > 0.8).any()  # synthetic terrain has relief
    flat = relative.elev_pos(np.full((9, 9), 1200.0), 100.0)
    np.testing.assert_allclose(flat, 0.5)  # no relief: no low or high points
    ramp = relative.elev_pos(np.tile(np.arange(9.0), (9, 1)), 100.0, radius_m=400)
    assert ramp[4, 0] == 0.0 and ramp[4, 8] == 1.0  # ends of a slope are the local extremes
