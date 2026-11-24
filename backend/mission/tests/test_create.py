"""Creating a mission."""

import pytest

from mission.create import folder_name
from mission.files import file_url
from mission.open_mission import close_mission
from missiondb.migrate import current, head_revision


def create(client, name="Bear Creek", time_zone="America/Denver"):
    return client.post("/api/missions", json={"name": name, "time_zone": time_zone})


def test_a_new_mission_is_in_planning_with_no_start_time_and_is_open(client):
    response = create(client)

    assert response.status_code == 201
    mission = response.json()
    assert mission == {
        "id": mission["id"],
        "name": "Bear Creek",
        "time_zone": "America/Denver",
        "status": "planning",
        "session": 1,
        "start_time": None,
        "end_time": None,
        "sessions": [{"number": 1, "status": "planning", "start_time": None, "end_time": None}],
        "asks_to_continue": False,
    }
    assert client.get("/api/mission").json() == mission
    assert [m["name"] for m in client.get("/api/missions").json()] == ["Bear Creek"]


def test_its_file_is_named_from_its_name_and_id_and_is_at_the_current_schema(client, missions_dir):
    mission = create(client).json()

    file = missions_dir / f"bear-creek-{mission['id'][:8]}" / "session-01.sqlite3"
    assert file.is_file()
    assert current(file_url(file)) == head_revision()


@pytest.mark.parametrize(("name", "folder"), [
    ("Bear Creek", "bear-creek-952592f8"),
    ("  Mt. Evans / Echo Lake #2  ", "mt-evans-echo-lake-2-952592f8"),
    ("!!!", "mission-952592f8"),  # nothing in the name can be part of a folder's name
])
def test_a_folder_is_named_from_the_mission_name_and_the_first_part_of_its_id(name, folder):
    assert folder_name(name, "952592f8-f48b-4310-aa51-3abcefc02005") == folder


def test_the_name_is_saved_without_the_spaces_around_it(client):
    assert create(client, name="  Bear Creek ").json()["name"] == "Bear Creek"


@pytest.mark.parametrize("name", ["", "   ", "x" * 61])
def test_a_name_that_is_empty_or_longer_than_60_characters_is_refused(client, missions_dir, name):
    response = create(client, name=name)

    assert response.status_code == 422
    assert not missions_dir.exists()  # nothing was made


def test_a_time_zone_that_does_not_exist_is_refused(client, missions_dir):
    response = create(client, time_zone="America/Denverr")

    assert response.status_code == 422
    assert "America/Denverr is not a time zone" in response.json()["detail"][0]["msg"]
    assert not missions_dir.exists()


def test_two_missions_may_have_the_same_name(client):
    first = create(client).json()
    second = create(client).json()

    assert first["id"] != second["id"]
    assert [m["name"] for m in client.get("/api/missions").json()] == ["Bear Creek", "Bear Creek"]


def test_a_new_mission_is_still_there_and_open_after_a_restart(client):
    mission = create(client).json()

    close_mission(forget=False)
    with client:  # entering the client runs the app's start-up code
        pass

    assert client.get("/api/mission").json() == mission
