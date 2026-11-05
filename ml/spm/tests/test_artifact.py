"""Model file round trip and raster/heatmap outputs (synthetic terrain)."""

import json

import numpy as np
import pytest
import rasterio
from test_hybrid_find_only import find_only, hybrid, world_and_cases  # noqa: F401

from spm.features.spec import FeatureSpec
from spm.geodata.grid import Window
from spm.io import raster
from spm.io.artifact import load_model, save_model
from spm.models.bayes import BayesModel
from spm.models.ring import RingModel

Q = {"hiker": {"q25": 1.0, "q50": 2.0, "q75": 4.0}}


def test_hybrid_round_trip(world_and_cases, tmp_path):  # noqa: F811
    world, cases = world_and_cases
    m = hybrid(world, lam_w=0.1).fit(find_only(cases[:30]))
    m.prior.fit(cases[30:60])
    path = save_model(m, tmp_path / "m.json", meta={"note": "test"})
    doc = json.loads(path.read_text())
    assert doc["kind"] == "hybrid" and doc["meta"]["note"] == "test"
    assert "lat" not in json.dumps(doc["meta"]) and "case_id" not in path.read_text()
    back = load_model(path, stack_provider=world)
    c = cases[60]
    w = Window.around(c.ipp.lon, c.ipp.lat, side_m=12_000, res=100)
    a, b = m.predict(c, w, world(c, w)), back.predict(c, w, world(c, w))
    np.testing.assert_allclose(b.prob, a.prob, rtol=1e-12)
    assert b.p_outside == pytest.approx(a.p_outside) and back.name == m.name
    assert back.fit_terrain is False  # a loaded model keeps its weights


def test_model_a_round_trip(world_and_cases, tmp_path):  # noqa: F811
    world, cases = world_and_cases
    spec = FeatureSpec("dist_trail_m", edges=(40,), prior=(5.5, 1.0), source="Jacobs 2015 p. 13")
    m = BayesModel([spec], prior=RingModel(quantiles=Q), stack_provider=world).fit([])
    back = load_model(save_model(m, tmp_path / "a.json"), stack_provider=world)
    c = cases[0]
    w = Window.around(c.ipp.lon, c.ipp.lat, side_m=12_000, res=100)
    np.testing.assert_allclose(
        back.predict(c, w, world(c, w)).prob, m.predict(c, w, world(c, w)).prob
    )
    assert back.prior.n_fit["hiker"] == -1 and back.specs[0].source == "Jacobs 2015 p. 13"


def test_mass_rank_and_bands():
    prob = np.array([[0.4, 0.3], [0.2, 0.1]])
    rank = raster.mass_rank(prob)
    np.testing.assert_allclose(rank, [[0.4, 0.7], [0.9, 1.0]])
    tied = raster.mass_rank(np.full((2, 2), 0.25))
    np.testing.assert_allclose(tied, 1.0)  # a flat map has no "best" cells
    bands = raster.mass_bands(rank, levels=(0.5, 0.75, 0.95))
    np.testing.assert_array_equal(bands, [[1, 2], [3, 0]])  # 1.0 is beyond the 95% level


@pytest.fixture
def pred(world_and_cases):  # noqa: F811
    world, cases = world_and_cases
    c = cases[1]
    w = Window.around(c.ipp.lon, c.ipp.lat, side_m=12_000, res=100)
    m = hybrid(world).fit(cases[2:20])
    p = m.predict(c, w, world(c, w))
    p.flags = np.zeros(w.shape, bool)
    p.flags[:5, :5] = True
    return c, world(c, w), p


def test_geotiff_round_trip(pred, tmp_path):
    c, stack, p = pred
    path = raster.write_geotiff(p, tmp_path / "p.tif")
    with rasterio.open(path) as src:
        assert src.count == 3 and src.crs.to_epsg() == p.window.epsg
        np.testing.assert_allclose(src.read(1), p.prob.astype(np.float32))
        assert float(src.tags()["p_outside"]) == pytest.approx(p.p_outside, abs=1e-6)
        assert src.read(3)[0, 0] == 1.0 and src.read(3)[-1, -1] == 0.0
        row, col = src.index(*p.window.project(c.ipp.lon, c.ipp.lat))
        assert (row, col) == p.window.rowcol(c.ipp.lon, c.ipp.lat)  # georeferencing agrees


def test_heatmap_and_overlay_write(pred, tmp_path):
    c, stack, p = pred
    png = raster.write_heatmap_png(p, tmp_path / "h.png", case=c, stack=stack)
    assert png.stat().st_size > 10_000
    raster.write_web_overlay(p, tmp_path / "o.png", tmp_path / "o.json")
    meta = json.loads((tmp_path / "o.json").read_text())
    (tl, tr, br, bl) = meta["coordinates"]
    assert tl[0] < tr[0] and bl[1] < tl[1]  # west < east, south < north
    assert tl[0] < c.ipp.lon < tr[0] and bl[1] < c.ipp.lat < tl[1]  # IPP inside the overlay
    assert meta["p_outside"] == pytest.approx(p.p_outside)
