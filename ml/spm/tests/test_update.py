"""Travel-time surface, time cap, searched-area update, GeoTIFF read-back."""

import numpy as np
import pytest

from spm.geodata import travel
from spm.geodata.grid import Window
from spm.io import raster
from spm.io.coverage import pod_from_geojson
from spm.models.ring import RingModel
from spm.models.update import apply_search, apply_time_cap, combine_pod
from spm.schema import Case, LonLat, Prediction

LON, LAT = -110.676, 31.506
RES, N = 100.0, 21
FLAT_OFF = travel.tobler_kmh(0.0, False)  # 6 e^-0.175 x 0.6 = 3.02 km/h
FLAT_ON = travel.tobler_kmh(0.0, True)


def test_tobler_speeds():
    assert FLAT_ON == pytest.approx(5.036, abs=0.01)
    assert travel.tobler_kmh(-0.05, True) == pytest.approx(6.0)  # fastest: slight downhill
    assert travel.tobler_kmh(0.3, True) < travel.tobler_kmh(0.0, True)


def test_travel_hours_flat_trail_and_wall():
    dem = np.zeros((N, N))
    start = (10, 10)
    h = travel.travel_hours(dem, RES, start)
    assert h[start] == 0.0
    assert h[10, 20] == pytest.approx(1.0 / FLAT_OFF, rel=1e-6)  # 1 km east, off trail
    assert h[0, 10] == pytest.approx(1.0 / FLAT_OFF, rel=1e-6)
    trail = np.zeros((N, N), bool)
    trail[10, :] = True
    h2 = travel.travel_hours(dem, RES, start, trail)
    assert h2[10, 20] == pytest.approx(1.0 / FLAT_ON, rel=1e-6)
    assert h2[0, 10] == pytest.approx(h[0, 10])  # off the trail nothing changed
    # a cliff: 200 m rise over one 100 m cell = 63 degrees; impassable at 31 degrees
    cliff = dem.copy()
    cliff[:, 15:] = 200.0
    h3 = travel.travel_hours(cliff, RES, start, max_slope_deg=31)
    assert np.isinf(h3[:, 15:]).all() and np.isfinite(h3[:, :15]).all()
    h4 = travel.travel_hours(cliff, RES, start)  # passable, just slow
    assert np.isfinite(h4[10, 20]) and h4[10, 20] > h[10, 20]
    assert np.isinf(travel.travel_hours(np.full((3, 3), np.nan), RES, (1, 1))[0, 0])


@pytest.fixture
def ring_pred():
    c = Case("t:1", "t", LonLat(LON, LAT), "hiker")
    w = Window.around(LON, LAT, side_m=N * RES, res=RES)
    q = {"hiker": {"q25": 0.5, "q50": 1.0, "q75": 2.0}}
    return c, RingModel(quantiles=q).fit([]).predict(c, w)


def test_time_cap_zeroes_unreachable_and_renormalizes(ring_pred):
    c, pred = ring_pred
    hours = travel.travel_hours(np.zeros((N, N)), RES, pred.window.rowcol(LON, LAT))
    capped = apply_time_cap(pred, hours, elapsed_h=0.1)  # ~300 m reach, window edge 1 km away
    capped.check()
    assert capped.p_outside == 0.0  # the edge is out of reach, so beyond it is too
    assert capped.prob[hours > 0.1].sum() == 0.0 and capped.prob.sum() == pytest.approx(1.0)
    later = apply_time_cap(pred, hours, elapsed_h=10.0)
    np.testing.assert_allclose(later.prob, pred.prob)  # everything reachable: unchanged
    assert later.p_outside == pred.p_outside and later.model.endswith("+cap10h")


def test_search_update_is_bayes(ring_pred):
    c, pred = ring_pred
    pod = np.zeros((N, N))
    pod[:, :10] = 0.8  # west half searched at POD 0.8, not found
    post = apply_search(pred, pod)
    post.check()
    found = (pred.prob * pod).sum()
    np.testing.assert_allclose(post.prob[:, :10], pred.prob[:, :10] * 0.2 / (1 - found))
    np.testing.assert_allclose(post.prob[:, 10:], pred.prob[:, 10:] / (1 - found))
    assert post.p_outside == pytest.approx(pred.p_outside / (1 - found))
    assert post.prob[:, 10:].sum() > pred.prob[:, 10:].sum()  # mass moved to the unsearched side
    np.testing.assert_allclose(combine_pod([pod, pod])[:, :10], 1 - 0.2 * 0.2)
    # the whole window searched at POD 1: all the mass is now beyond the window
    assert apply_search(pred, np.ones((N, N))).p_outside == pytest.approx(1.0)
    closed = Prediction(prob=pred.prob / pred.prob.sum(), window=pred.window, model="x")
    with pytest.raises(ValueError):  # ...unless there is no beyond
        apply_search(closed, np.ones((N, N)))


def test_pod_from_geojson_rasterizes_and_combines(ring_pred):
    c, pred = ring_pred
    w = pred.window
    xmin, ymin, xmax, ymax = w.bounds
    xmid = (xmin + xmax) / 2

    def poly(x0, y0, x1, y1, pod):
        corners = [w.unproject(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))]
        return {
            "type": "Feature",
            "properties": {"pod": pod},
            "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in corners]]},
        }

    doc = {
        "type": "FeatureCollection",
        "features": [poly(xmin, ymin, xmid, ymax, 0.5), poly(xmin, ymin, xmax, ymax, 0.5)],
    }
    pod = pod_from_geojson(doc, w)
    assert pod[10, 2] == pytest.approx(0.75)  # two searches at 0.5 overlap in the west
    assert pod[10, 18] == pytest.approx(0.5)
    with pytest.raises(ValueError):
        pod_from_geojson(
            {"type": "FeatureCollection", "features": [poly(xmin, ymin, xmax, ymax, 2)]}, w
        )


def test_geotiff_read_back(ring_pred, tmp_path):
    c, pred = ring_pred
    pred.flags = np.zeros((N, N), bool)
    pred.flags[0, 0] = True
    path = raster.write_geotiff(pred, tmp_path / "p.tif", ipp=(LON, LAT))
    back, ipp = raster.read_geotiff(path)
    assert back.window == pred.window and ipp == pytest.approx((LON, LAT))
    np.testing.assert_allclose(back.prob, pred.prob.astype(np.float32))
    assert back.p_outside == pytest.approx(pred.p_outside, abs=1e-6)
    assert back.flags[0, 0] and not back.flags[1, 1] and back.model == pred.model


def test_prediction_check_rejects_unnormalized():
    w = Window.around(LON, LAT, side_m=300, res=100)
    with pytest.raises(ValueError):
        Prediction(prob=np.ones(w.shape), window=w, model="x").check()
