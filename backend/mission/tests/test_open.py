"""Opening a mission: the backend remembers one open mission, and every route reads it."""

import json
import subprocess

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from mapdb import spm
from mission.open_mission import changeable_session, close_mission, mission_session
from missiondb.models import Mission
from server.main import app
from settings.settings_file import read_settings

from .conftest import ARIZONA07_ID, utc

BEAR_CREEK_ID = "11111111-2222-3333-4444-555555555555"


def restart(client):
    """What stopping the backend and starting it again does: the open mission is forgotten,
    then the start-up code runs."""
    close_mission(forget=False)
    with client:  # entering the client runs the app's start-up code
        pass


def test_with_no_mission_open_the_answer_is_empty(client):
    response = client.get("/api/mission")

    assert response.status_code == 200
    assert response.json() is None


def test_opening_a_mission_answers_its_facts_and_it_stays_open(client, arizona07):
    response = client.post(f"/api/missions/{ARIZONA07_ID}/open")

    assert response.status_code == 200
    assert response.json() == {
        "id": ARIZONA07_ID,
        "name": "Arizona07",
        "time_zone": "America/Phoenix",
        "status": "ended",
        "session": 1,
        "start_time": "2025-04-14T03:30:00Z",
        "end_time": "2025-04-14T11:20:00Z",
        "sessions": [
            {"number": 1, "status": "ended",
             "start_time": "2025-04-14T03:30:00Z", "end_time": "2025-04-14T11:20:00Z"},
        ],
        "asks_to_continue": False,
    }
    assert client.get("/api/mission").json() == response.json()


def test_opening_another_mission_changes_which_one_is_read(client, arizona07, make_mission):
    make_mission("bear-creek/session-01.sqlite3")

    client.post(f"/api/missions/{ARIZONA07_ID}/open")
    assert client.get("/api/mission").json()["name"] == "Arizona07"

    client.post(f"/api/missions/{BEAR_CREEK_ID}/open")
    assert client.get("/api/mission").json()["name"] == "Bear Creek"


def test_opening_a_mission_opens_its_latest_session(client, make_mission):
    make_mission("bear-creek/session-01.sqlite3", session=1, status="paused",
                 start=utc(2026, 11, 20, 15), end=utc(2026, 11, 20, 23))
    make_mission("bear-creek/session-02.sqlite3", session=2, status="active", start=utc(2026, 11, 21, 15))

    mission = client.post(f"/api/missions/{BEAR_CREEK_ID}/open").json()

    assert (mission["session"], mission["status"]) == (2, "active")


def test_opening_a_mission_that_is_not_there_is_refused(client, arizona07):
    response = client.post("/api/missions/no-such-mission/open")

    assert response.status_code == 404
    assert response.json() == {"detail": "No mission has this id."}
    assert client.get("/api/mission").json() is None


def test_closing_the_mission_leaves_none_open(client, arizona07):
    client.post(f"/api/missions/{ARIZONA07_ID}/open")

    assert client.post("/api/mission/close").status_code == 204

    assert client.get("/api/mission").json() is None


def test_the_last_mission_opened_is_open_again_after_a_restart(client, arizona07, make_mission):
    make_mission("bear-creek/session-01.sqlite3")
    client.post(f"/api/missions/{BEAR_CREEK_ID}/open")
    client.post(f"/api/missions/{ARIZONA07_ID}/open")
    assert read_settings().last_mission == ARIZONA07_ID

    restart(client)

    assert client.get("/api/mission").json()["name"] == "Arizona07"


def test_a_closed_mission_is_not_opened_by_a_restart(client, arizona07):
    client.post(f"/api/missions/{ARIZONA07_ID}/open")
    client.post("/api/mission/close")

    restart(client)

    assert client.get("/api/mission").json() is None


def test_a_restart_opens_nothing_when_the_last_mission_is_gone(client, make_mission):
    path = make_mission("bear-creek/session-01.sqlite3")
    client.post(f"/api/missions/{BEAR_CREEK_ID}/open")
    close_mission(forget=False)
    path.unlink()

    restart(client)

    assert client.get("/api/mission").json() is None


def test_changing_a_setting_keeps_the_last_mission_and_the_settings_routes_do_not_show_it(client, arizona07):
    client.post(f"/api/missions/{ARIZONA07_ID}/open")

    response = client.patch("/api/settings", json={"units": "metric"})

    assert response.json() == {"units": "metric"}
    assert client.get("/api/settings").json() == {"units": "metric"}
    assert read_settings().last_mission == ARIZONA07_ID
    # The last mission is the backend's to save: a request cannot change it.
    assert client.patch("/api/settings", json={"last_mission": "another"}).status_code == 422


# The two functions a route uses to reach the open mission, tried through two routes made
# for these tests: one that reads, and one that saves.

@pytest.fixture
def probe():
    probe_app = FastAPI()

    @probe_app.get("/name")
    def name(db: Session = Depends(mission_session)):
        return db.exec(select(Mission.name)).one()

    @probe_app.post("/save")
    def save(db: Session = Depends(changeable_session)):
        return "saved"

    return TestClient(probe_app)


def test_a_route_reads_the_open_mission(client, probe, arizona07):
    client.post(f"/api/missions/{ARIZONA07_ID}/open")

    assert probe.get("/name").json() == "Arizona07"


def test_with_no_mission_open_a_mission_route_says_so(probe):
    for response in (probe.get("/name"), probe.post("/save")):
        assert response.status_code == 409
        assert response.json() == {"detail": "No mission is open."}


@pytest.mark.parametrize(("status", "times", "allowed"), [
    ("planning", {}, True),
    ("active", {"start": utc(2026, 11, 20, 15)}, True),
    ("paused", {"start": utc(2026, 11, 20, 15), "end": utc(2026, 11, 20, 23)}, False),
    ("ended", {"start": utc(2026, 11, 20, 15), "end": utc(2026, 11, 20, 23)}, False),
])
def test_a_saving_route_is_refused_unless_the_session_is_in_planning_or_active(
    client, probe, make_mission, status, times, allowed,
):
    make_mission("bear-creek/session-01.sqlite3", status=status, **times)
    client.post(f"/api/missions/{BEAR_CREEK_ID}/open")

    response = probe.post("/save")

    if allowed:
        assert response.status_code == 200
    else:
        assert response.status_code == 409
        assert response.json() == {"detail": f"This session is {status}, so nothing in it can be changed."}


# JJ's route that re-works a probability map asks missiondb for a session. It must get the
# open mission, with nothing changed in his file.

@pytest.fixture
def prediction(tmp_path, monkeypatch):
    """A saved prediction for JJ's route to update, and a folder that looks like ml/spm."""
    root = tmp_path / "spm"
    python = spm.spm_python(root)
    python.parent.mkdir(parents=True)
    python.touch()
    (root / "models").mkdir()
    (root / "models" / "model_a.json").write_text(json.dumps({"ring": {"params": {"hiker": [0.7, 1.2]}}}))
    monkeypatch.setenv(spm.SPM_DIR_SETTING, str(root))
    folder = tmp_path / "predictions"
    folder.mkdir()
    monkeypatch.setenv("SPM_PREDICTIONS_DIR", str(folder))
    (folder / "20261119-120000_hiker.tif").touch()
    return "20261119-120000_hiker"


def test_the_probability_map_update_reads_the_open_mission(client, arizona07, prediction, monkeypatch):
    searched = []

    def fake_run(root, args, timeout=spm.TIMEOUT_S, capture=True):
        """Stands in for the model: keeps the sectors it was handed and writes its files."""
        searched.append(json.loads(open(args[args.index("--searched") + 1]).read()))
        stem = args[args.index("--out") + 1]
        open(f"{stem}_overlay.png", "wb").write(b"\x89PNG")
        open(f"{stem}_overlay.json", "w").write(json.dumps({"coordinates": []}))
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(spm, "run", fake_run)
    url = f"/api/spm/predictions/{prediction}/update"

    refused = client.post(url, json={"pod": 0.5})
    assert refused.status_code == 409
    assert refused.json() == {"detail": "No mission is open."}

    client.post(f"/api/missions/{ARIZONA07_ID}/open")
    assert client.post(url, json={"pod": 0.5}).status_code == 200
    # Arizona07's four completed sectors.
    assert [feature["id"] for feature in searched[0]["features"]] == [1, 2, 3, 5]


def test_the_main_app_is_the_one_whose_missiondb_sessions_are_the_open_mission():
    from missiondb import get_session
    assert app.dependency_overrides[get_session] is mission_session
