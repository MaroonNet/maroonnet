"""Finding the missions folder, and listing the missions in it."""

from maps.folders import app_data_folder
from mission.folders import MISSIONS_DIR_VARIABLE, missions_folder

from .conftest import ARIZONA07_ID, utc

BEAR_CREEK_ID = "11111111-2222-3333-4444-555555555555"


def test_each_test_gets_its_own_missions_folder(missions_dir):
    # The guard that keeps tests away from real mission files.
    assert missions_folder() == missions_dir


def test_the_missions_folder_is_inside_the_app_data_folder_unless_the_variable_names_another(monkeypatch, tmp_path):
    monkeypatch.delenv(MISSIONS_DIR_VARIABLE)
    assert missions_folder() == app_data_folder() / "missions"

    monkeypatch.setenv(MISSIONS_DIR_VARIABLE, str(tmp_path / "elsewhere"))
    assert missions_folder() == tmp_path / "elsewhere"


def test_with_no_missions_folder_the_list_is_empty(client, missions_dir):
    assert not missions_dir.exists()
    response = client.get("/api/missions")

    assert response.status_code == 200
    assert response.json() == []


def test_arizona07_and_a_made_up_mission_are_both_listed(client, arizona07, make_mission):
    make_mission("bear-creek-11111111/session-01.sqlite3")

    assert client.get("/api/missions").json() == [
        {
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
        },
        {
            "id": BEAR_CREEK_ID,
            "name": "Bear Creek",
            "time_zone": "America/Denver",
            "status": "planning",
            "session": 1,
            "start_time": None,
            "end_time": None,
            "sessions": [{"number": 1, "status": "planning", "start_time": None, "end_time": None}],
        },
    ]


def test_a_mission_with_two_sessions_has_the_facts_of_its_latest(client, make_mission):
    # The file names say nothing: the session number is read from inside each file.
    make_mission("bear-creek/b.sqlite3", session=1, status="paused",
                 start=utc(2026, 11, 20, 15), end=utc(2026, 11, 20, 23))
    make_mission("bear-creek/a.sqlite3", session=2, status="active", start=utc(2026, 11, 21, 15))

    [mission] = client.get("/api/missions").json()

    assert mission["status"] == "active"
    assert mission["session"] == 2
    assert mission["start_time"] == "2026-11-21T15:00:00Z"
    assert [(s["number"], s["status"]) for s in mission["sessions"]] == [(1, "paused"), (2, "active")]


def test_files_that_are_not_missions_are_left_out(client, missions_dir, make_mission, empty_file):
    make_mission("bear-creek/session-01.sqlite3")
    (missions_dir / "bear-creek" / "notes.sqlite3").write_text("not a database")
    (missions_dir / "bear-creek" / "notes.txt").write_text("not a mission file")
    # A folder whose only file holds the tables but no mission is not a mission.
    (missions_dir / "empty").mkdir()
    (missions_dir / "empty" / "session-01.sqlite3").write_bytes(empty_file.read_bytes())
    (missions_dir / "stray.sqlite3").write_bytes(empty_file.read_bytes())

    missions = client.get("/api/missions").json()

    assert [m["name"] for m in missions] == ["Bear Creek"]
    assert len(missions[0]["sessions"]) == 1
