"""The command line end to end: predict with a time cap and a searched sector, then update.

Runs on the synthetic tile and OSM extract from conftest, with SPM_ROOT pointing at a
temporary project folder, so no network and no real case data are involved.
"""

import json

import numpy as np
import pytest
import rasterio
from conftest import LAT, LON

from spm import cli
from spm.features.spec import FeatureSpec
from spm.io.artifact import save_model
from spm.models.bayes import BayesModel
from spm.models.ring import RingModel

Q = {"hiker": {"q25": 1.29, "q50": 2.09, "q75": 6.60}}
TRAIL = FeatureSpec("dist_trail_m", edges=(40.0,), prior=(5.5, 1.0), source="test")


@pytest.fixture
def project(tmp_path, tile_dir, gpkg, monkeypatch):
    """A project root with a Model A file, and a data dir whose terrain holds the test tile."""
    root = tmp_path / "proj"
    (root / "configs").mkdir(parents=True)
    (root / "configs" / "prior_art.yaml").write_text("features: {}\n")
    data = tmp_path / "data"
    dem_dir = data / "terrain" / "dem_tiles"
    dem_dir.mkdir(parents=True)
    for tile in tile_dir.iterdir():
        tile.rename(dem_dir / tile.name)
    model = BayesModel([TRAIL], prior=RingModel(quantiles=Q), feature_res=10.0).fit([])
    save_model(model, root / "models" / "model_a.json", {"note": "test"})
    monkeypatch.setenv("SPM_ROOT", str(root))
    monkeypatch.setattr(cli, "ROOT", root)
    return {"root": root, "data": data, "gpkg": gpkg, "model": root / "models" / "model_a.json"}


def run(project, *args):
    cli.main(["--data", str(project["data"]), *map(str, args)])


def predict_args(project, lon=LON, lat=LAT, **extra):
    out = [
        "predict",
        project["model"],
        "--ipp",
        lon,
        lat,
        "--side",
        2000,
        "--res",
        100,
        "--lines",
        project["gpkg"],
        "--streams",
        "--out",
        project["root"] / "predictions" / "run",
    ]
    for k, v in extra.items():
        out += [f"--{k.replace('_', '-')}", *([] if v is None else [v])]
    return out


def test_predict_then_update(project, tmp_path):
    sectors = tmp_path / "sectors.geojson"
    half = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": "A", "pod": 0.6},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [LON - 0.02, LAT - 0.02],
                            [LON, LAT - 0.02],
                            [LON, LAT + 0.02],
                            [LON - 0.02, LAT + 0.02],
                            [LON - 0.02, LAT - 0.02],
                        ]
                    ],
                },
            }
        ],
    }
    sectors.write_text(json.dumps(half))
    run(project, *predict_args(project, elapsed_h=2, searched=sectors))
    stem = project["root"] / "predictions" / "run"
    with rasterio.open(stem.with_suffix(".tif")) as ds:
        tags = ds.tags()
        prob = ds.read(1)
    assert tags["model"] == "bayes_prior_art+cap2h+search"
    assert tags["ipp"] == f"{LON:.6f},{LAT:.6f}"
    assert prob.shape == (21, 21) and abs(prob.sum() + float(tags["p_outside"]) - 1) < 1e-5
    corners = json.loads(stem.with_name("run_overlay.json").read_text())["coordinates"]
    assert len(corners) == 4 and corners[0][0] < LON < corners[1][0]
    assert stem.with_name("run_travel_h.tif").exists()
    # the searched half carries less mass than the unsearched half
    assert prob[:, :10].sum() < prob[:, 11:].sum()

    run(project, "update", stem.with_suffix(".tif"), "--searched", sectors)
    with rasterio.open(stem.with_name("run_u2.tif")) as ds:
        assert ds.tags()["model"].endswith("+search+search")
        prob2 = ds.read(1)
    assert prob2[:, :10].sum() < prob[:, :10].sum()


def test_predict_refuses_time_cap_without_elevation(project):
    # a window reaching past the east edge of the synthetic tile has no elevation there
    with pytest.raises(SystemExit, match="elevation everywhere"):
        run(project, *predict_args(project, lon=-74.405, elapsed_h=2))
    run(project, *predict_args(project, lon=-74.405, elapsed_h=2, allow_missing_dem=None))
    with rasterio.open(project["root"] / "predictions" / "run.tif") as ds:
        flags = ds.read(3)
    assert flags[:, -1].all() and not flags[:, 0].any()  # no-data cells are flagged


def test_predict_rejects_resolution_not_multiple_of_feature_res(project):
    with pytest.raises(SystemExit, match="multiple of the feature res"):
        run(project, *[a if a != 100 else 25 for a in predict_args(project)])


def test_update_names_follow_the_run(project, tmp_path):
    run(project, *predict_args(project))
    stem = project["root"] / "predictions" / "run"
    stem.with_suffix(".tif").rename(stem.with_name("mount_umbrella.tif"))
    sectors = tmp_path / "s.geojson"
    sectors.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
    run(project, "update", stem.with_name("mount_umbrella.tif"), "--searched", sectors)
    assert stem.with_name("mount_umbrella_u1.tif").exists()


def test_fit_refuses_without_holdout(project):
    with pytest.raises(SystemExit, match="no frozen test set"):
        run(project, "fit", "--model", "model_a")


def test_nan_elevation_is_not_high_ground():
    """No-data cells take the feature's missing bin, never the last (high-ground) bin."""
    spec = FeatureSpec("elev_pos", edges=(0.2, 0.8), prior=(1.9, 1.0, 1.6), missing_bin=1)
    idx = spec.bin_index(np.array([0.1, 0.5, 0.9, np.nan, np.inf]))
    assert idx.tolist() == [0, 1, 2, 1, 1]
    dist = FeatureSpec("dist_trail_m", edges=(40.0,), prior=(5.5, 1.0))
    assert dist.bin_index(np.array([np.nan])).tolist() == [1]
