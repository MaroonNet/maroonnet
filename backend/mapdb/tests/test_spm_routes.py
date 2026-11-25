"""The prediction routes, with spm itself replaced: no test here runs the real model."""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from mapdb import spm
from mapdb.routes import DEFAULT_PREDICTIONS_DIR, predictions_dir, router
from mission.open_mission import close_mission, open_folder
from mission.tests.conftest import empty_file, make_mission  # noqa: F401  (pytest finds these helpers by name)
from missiondb import create_db_engine, get_session, init_db
from missiondb.models import SearchGroup, SearchSector, SearchSectorPoint, SectorStatus

T0 = datetime(2026, 10, 23, 21, 15, 0, tzinfo=timezone.utc)

HIKER_ONLY = {"ring": {"pooled_only": False, "params": {"__all__": [1.2, 1.2], "hiker": [0.7, 1.2]}}}
OVERLAY = {"coordinates": [[-110.9, 31.7], [-110.5, 31.7], [-110.5, 31.3], [-110.9, 31.3]],
           "model": "bayes_prior_art", "p_outside": 0.05}


@pytest.fixture
def spm_root(tmp_path, monkeypatch):
    """A folder that looks like ml/spm: an environment's Python and one fitted model."""
    root = tmp_path / "spm"
    python = spm.spm_python(root)
    python.parent.mkdir(parents=True)
    python.touch()
    (root / "models").mkdir()
    (root / "models" / "model_a.json").write_text(json.dumps(HIKER_ONLY))
    monkeypatch.setenv(spm.SPM_DIR_SETTING, str(root))
    monkeypatch.setenv("SPM_PREDICTIONS_DIR", str(tmp_path / "predictions"))
    return root


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def fake_spm(returncode=0, stderr="", write=True):
    """A stand-in for spm.run that records its arguments and writes the files spm would."""
    calls = []

    def run(root, args, timeout=spm.TIMEOUT_S, capture=True):
        calls.append(args)
        if write:
            stem = args[args.index("--out") + 1]
            open(f"{stem}.tif", "wb").close()
            open(f"{stem}_overlay.png", "wb").write(b"\x89PNG")
            open(f"{stem}_overlay.json", "w").write(json.dumps(OVERLAY))
        return subprocess.CompletedProcess(args, returncode, stdout="", stderr=stderr)

    run.calls = calls
    return run


def test_status_lists_models_and_their_categories(client, spm_root):
    assert client.get("/api/spm/status").json() == {
        "available": True, "detail": "ok", "models": {"model_a": ["hiker"]},
    }


def test_status_says_why_spm_is_unavailable(client, spm_root):
    spm.spm_python(spm_root).unlink()
    body = client.get("/api/spm/status").json()
    assert body["available"] is False and "no Python" in body["detail"]
    assert client.post("/api/spm/predict", json={"lon": -110.7, "lat": 31.5}).status_code == 503


def test_predict_runs_spm_and_answers_with_the_overlay(client, spm_root, monkeypatch):
    run = fake_spm()
    monkeypatch.setattr(spm, "run", run)
    response = client.post("/api/spm/predict",
                           json={"lon": -110.7, "lat": 31.5, "elapsed_h": 2.5, "res": 50})
    assert response.status_code == 200
    overlay = response.json()
    assert overlay["coordinates"] == OVERLAY["coordinates"]
    assert overlay["id"].endswith("_hiker_150min")
    args = run.calls[0]
    assert args[0] == "predict" and args[1].endswith("model_a.json")
    assert args[args.index("--ipp") + 1:][:2] == ["-110.700000", "31.500000"]
    assert args[args.index("--elapsed-h") + 1] == "2.5"
    assert args[args.index("--res") + 1] == "50"
    # the picture is served, and the prediction is listed
    assert client.get(overlay["image"]).content == b"\x89PNG"
    assert [p["id"] for p in client.get("/api/spm/predictions").json()] == [overlay["id"]]


def test_predict_rejects_what_the_model_cannot_draw(client, spm_root, monkeypatch):
    monkeypatch.setattr(spm, "run", fake_spm())
    point = {"lon": -110.7, "lat": 31.5}
    assert client.post("/api/spm/predict", json={**point, "category": "dementia"}).status_code == 400
    assert client.post("/api/spm/predict", json={**point, "model": "../secret"}).status_code == 400
    assert client.post("/api/spm/predict", json={**point, "lat": 95}).status_code == 422
    assert client.post("/api/spm/predict", json={**point, "res": 7}).status_code == 422


def test_a_refusal_reaches_the_user_and_a_crash_does_not(client, spm_root, monkeypatch):
    point = {"lon": -110.7, "lat": 31.5}
    monkeypatch.setattr(spm, "run", fake_spm(1, "terrain is incomplete: no trail/road file", False))
    response = client.post("/api/spm/predict", json=point)
    assert response.status_code == 422 and "terrain is incomplete" in response.json()["detail"]
    crash = "Traceback (most recent call last):\n  File ...\nValueError: /secret/path"
    monkeypatch.setattr(spm, "run", fake_spm(1, crash, False))
    response = client.post("/api/spm/predict", json=point)
    assert response.status_code == 500 and "secret" not in response.text


def test_a_stuck_prediction_is_reported(client, spm_root, monkeypatch):
    def run(root, args, timeout=spm.TIMEOUT_S, capture=True):
        raise subprocess.TimeoutExpired(args, timeout)

    monkeypatch.setattr(spm, "run", run)
    assert client.post("/api/spm/predict", json={"lon": -110.7, "lat": 31.5}).status_code == 504
    # the lock was released: the next request is not turned away as "already running"
    monkeypatch.setattr(spm, "run", fake_spm())
    assert client.post("/api/spm/predict", json={"lon": -110.7, "lat": 31.5}).status_code == 200


def test_an_id_cannot_name_a_file_outside_the_folder(client, spm_root):
    assert client.get("/api/spm/predictions/..%2F..%2Fsecret/overlay.png").status_code == 404
    assert client.get("/api/spm/predictions/20261119-120000_hiker/overlay.png").status_code == 404


@pytest.fixture
def mission(tmp_path, client):
    """A mission database with sector 1 completed and sector 2 only drawn, behind the routes."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'mission.sqlite3'}")
    init_db(engine)
    with Session(engine) as session:
        for sector_id, status in ((1, SectorStatus.COMPLETED), (2, SectorStatus.DRAWN)):
            done = status is SectorStatus.COMPLETED
            session.add(SearchGroup(search_group_id=sector_id))
            session.add(SearchSector(
                search_sector_id=sector_id, search_group_id=sector_id, status=status,
                created_time=T0, completed_time=T0 + timedelta(hours=1) if done else None,
            ))
            session.flush()
            for order, (lat, lon) in enumerate(((31.50, -110.70), (31.50, -110.69), (31.51, -110.69)), 1):
                session.add(SearchSectorPoint(search_sector_id=sector_id, point_order=order,
                                              lat=lat, lon=lon))
        session.commit()

    def sessions():
        with Session(engine) as session:
            yield session

    client.app.dependency_overrides[get_session] = sessions


@pytest.fixture
def prediction(tmp_path, spm_root):
    """The id of a saved prediction: only its raster, which is all an update needs."""
    folder = tmp_path / "predictions"
    folder.mkdir()
    (folder / "20261119-120000_hiker.tif").touch()
    return "20261119-120000_hiker"


def test_update_sends_the_searched_sectors_to_spm(client, mission, prediction, tmp_path, monkeypatch):
    run = fake_spm()
    monkeypatch.setattr(spm, "run", run)
    response = client.post(f"/api/spm/predictions/{prediction}/update", json={"pod": 0.6})
    assert response.status_code == 200
    assert response.json()["id"] == f"{prediction}_u1"
    args = run.calls[0]
    assert args[0] == "update" and args[1].endswith(f"{prediction}.tif")
    searched = json.loads(open(args[args.index("--searched") + 1]).read())
    assert [(f["id"], f["properties"]["pod"]) for f in searched["features"]] == [(1, 0.6)]
    # a second round of searching updates the update, and is numbered after it
    response = client.post(f"/api/spm/predictions/{prediction}_u1/update",
                           json={"pod_by_sector": {"2": 0.3}, "statuses": ["completed", "drawn"]})
    assert response.json()["id"] == f"{prediction}_u2"
    searched = json.loads(open(run.calls[1][run.calls[1].index("--searched") + 1]).read())
    assert [f["properties"].get("pod") for f in searched["features"]] == [None, 0.3]


def test_update_refuses_what_it_cannot_do(client, mission, prediction, monkeypatch):
    monkeypatch.setattr(spm, "run", lambda *a, **k: pytest.fail("spm must not run"))
    url = f"/api/spm/predictions/{prediction}/update"
    assert client.post("/api/spm/predictions/20261119-000000_hiker/update", json={"pod": 0.5}).status_code == 404
    assert client.post(url, json={}).status_code == 400                       # no POD at all
    assert client.post(url, json={"pod_by_sector": {"2": 0.5}}).status_code == 400  # sector 2 is not completed
    assert client.post(url, json={"pod": 50}).status_code == 422
    assert client.post(url, json={"pod_by_sector": {"1": -0.1}}).status_code == 422


def test_update_says_so_when_the_database_is_not_a_mission(client, prediction, tmp_path, monkeypatch):
    monkeypatch.setattr(spm, "run", lambda *a, **k: pytest.fail("spm must not run"))
    engine = create_db_engine(f"sqlite:///{tmp_path / 'empty.sqlite3'}")  # a file with no tables

    def sessions():
        with Session(engine) as session:
            yield session

    client.app.dependency_overrides[get_session] = sessions
    response = client.post(f"/api/spm/predictions/{prediction}/update", json={"pod": 0.5})
    assert response.status_code == 503 and "MISSIONDB_URL" in response.json()["detail"]


def test_predictions_are_kept_with_the_open_mission(make_mission, tmp_path, monkeypatch):
    monkeypatch.delenv("SPM_PREDICTIONS_DIR", raising=False)
    shared = Path(DEFAULT_PREDICTIONS_DIR).resolve()
    assert predictions_dir() == shared  # no mission open: the shared folder
    bear_creek = make_mission("bear-creek/session-01.sqlite3").parent
    open_folder(bear_creek)
    assert predictions_dir() == (bear_creek / "predictions").resolve()
    # another mission keeps its own, so a map made in one does not show in the other
    elk_ridge = make_mission("elk-ridge/session-01.sqlite3", name="Elk Ridge",
                             mission_id="99999999-2222-3333-4444-555555555555").parent
    open_folder(elk_ridge)
    assert predictions_dir() == (elk_ridge / "predictions").resolve()
    # the variable still wins
    monkeypatch.setenv("SPM_PREDICTIONS_DIR", str(tmp_path / "elsewhere"))
    assert predictions_dir() == (tmp_path / "elsewhere").resolve()
    monkeypatch.delenv("SPM_PREDICTIONS_DIR")
    close_mission()
    assert predictions_dir() == shared


def test_an_unreadable_model_file_is_left_out(spm_root):
    (spm_root / "models" / "broken.json").write_text("not json")
    assert spm.models(spm_root) == {"model_a": ["hiker"]}
