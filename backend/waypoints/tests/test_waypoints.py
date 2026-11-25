"""The open mission's waypoints: listing, adding, changing and removing them."""

import pytest

from mission.tests.conftest import ARIZONA07_ID, rows, utc

NOW_TEXT = "2026-11-20T23:30:00Z"   # the stopped clock's time
LATER = utc(2026, 11, 20, 23, 45)
LATER_TEXT = "2026-11-20T23:45:00Z"

HAZARD = {"kind": "hazard", "lat": 40.01, "lon": -105.61, "name": "Mine shaft", "description": "Open shaft, unfenced", "note": "Told by the ranger"}
ALL_ROWS = "SELECT waypoint_id, type_code, name, created_time, removed_time FROM waypoint ORDER BY waypoint_id"


def add(client, **changes) -> dict:
    """Adds the hazard, or the hazard with some facts changed, and answers with it as saved."""
    response = client.post("/api/mission/waypoints", json=HAZARD | changes)
    assert response.status_code == 201, response.text
    return response.json()


# Listing

def test_arizona07_lists_its_six_waypoints(client, arizona07):
    client.post(f"/api/missions/{ARIZONA07_ID}/open")

    waypoints = client.get("/api/mission/waypoints").json()

    assert [(w["id"], w["kind"], w["name"]) for w in waypoints] == [
        (1, "command_post", "Command post"), (2, "last_known_position", "Start point"), (3, "landing_zone", "LZ 1"),
        (4, "evidence", "Boot prints"), (5, "find", "Helicopter sighting"), (6, "find", "Subject found"),
    ]


def test_a_waypoint_comes_with_its_place_words_times_and_the_radio_that_reported_it(client, arizona07):
    client.post(f"/api/missions/{ARIZONA07_ID}/open")

    waypoints = client.get("/api/mission/waypoints").json()

    assert waypoints[4] == {
        "id": 5, "kind": "find", "lat": 31.51, "lon": -110.6533, "name": "Helicopter sighting",
        "description": "Heat signature on FLIR, not yet confirmed on the ground",
        "note": "Reported by the Border Patrol helicopter",
        "time": "2025-04-14T08:51:19Z", "created_time": "2025-04-14T08:52:19Z", "radio_id": None,
    }
    assert [w["radio_id"] for w in waypoints] == [None, None, 4, 1, None, 1]


def test_a_new_mission_has_no_waypoints(client, open_bear_creek):
    open_bear_creek("planning")

    assert client.get("/api/mission/waypoints").json() == []


def test_with_no_mission_open_the_list_is_refused(client):
    response = client.get("/api/mission/waypoints")

    assert response.status_code == 409
    assert response.json() == {"detail": "No mission is open."}


# Adding

def test_a_new_waypoint_is_saved_as_placed_by_the_commander(client, open_bear_creek):
    path = open_bear_creek("planning")

    waypoint = add(client)

    assert waypoint == HAZARD | {"id": 1, "time": NOW_TEXT, "created_time": NOW_TEXT, "radio_id": None}
    assert rows(path, "SELECT type_code, lat, lon, name, description, note, team_id, message_id, removed_time FROM waypoint") == [
        ("hazard", 40.01, -105.61, "Mine shaft", "Open shaft, unfenced", "Told by the ranger", None, None, None),
    ]
    assert client.get("/api/mission/waypoints").json() == [waypoint]


def test_spaces_around_the_words_are_dropped_and_empty_words_are_saved_as_none(client, open_bear_creek):
    open_bear_creek("active")

    waypoint = add(client, name="  Mine shaft ", description="   ", note="")

    assert (waypoint["name"], waypoint["description"], waypoint["note"]) == ("Mine shaft", None, None)


@pytest.mark.parametrize("changes, reason", [
    ({"name": "   "}, "A waypoint needs a name."),
    ({"name": "x" * 31}, "A waypoint's name holds 30 bytes at most."),
    ({"name": "é" * 16}, "A waypoint's name holds 30 bytes at most."),  # 16 letters, 32 bytes
    ({"description": "x" * 101}, "A waypoint's description holds 100 bytes at most."),
    ({"kind": "campsite"}, "There is no waypoint kind 'campsite'."),
    ({"lat": 0, "lon": 0}, "A waypoint cannot be at latitude 0, longitude 0."),
])
def test_a_waypoint_that_breaks_a_rule_is_refused(client, open_bear_creek, changes, reason):
    path = open_bear_creek("planning")

    response = client.post("/api/mission/waypoints", json=HAZARD | changes)

    assert response.status_code == 422
    assert response.json() == {"detail": reason}
    assert rows(path, "SELECT count(*) FROM waypoint") == [(0,)]


def test_a_name_of_thirty_bytes_and_a_description_of_a_hundred_are_allowed(client, open_bear_creek):
    open_bear_creek("planning")

    waypoint = add(client, name="x" * 30, description="é" * 50)

    assert (len(waypoint["name"]), len(waypoint["description"])) == (30, 50)


# Changing

def test_changing_a_waypoint_closes_its_row_and_adds_a_new_one(client, open_bear_creek, clock):
    path = open_bear_creek("active")
    add(client)
    clock.set(LATER)

    response = client.put("/api/mission/waypoints/1", json=HAZARD | {"lat": 40.02, "name": "Old mine shaft"})

    assert response.status_code == 200
    changed = response.json()
    # The new row keeps when the thing was seen; it was saved now.
    assert changed == HAZARD | {"id": 2, "lat": 40.02, "name": "Old mine shaft", "time": NOW_TEXT, "created_time": LATER_TEXT, "radio_id": None}
    assert rows(path, ALL_ROWS) == [
        (1, "hazard", "Mine shaft", NOW_TEXT, LATER_TEXT),
        (2, "hazard", "Old mine shaft", LATER_TEXT, None),
    ]
    assert client.get("/api/mission/waypoints").json() == [changed]


def test_a_changed_waypoint_keeps_the_radio_and_the_message_it_came_from(client, arizona07):
    client.post(f"/api/missions/{ARIZONA07_ID}/open")
    client.post("/api/mission/reopen")
    client.post("/api/mission/next-session", json={"keep_teams": True})
    session_2 = arizona07.parent / "session-02.sqlite3"
    before = rows(session_2, "SELECT team_id, message_id, time FROM waypoint WHERE name = 'Boot prints'")

    boot_prints = next(w for w in client.get("/api/mission/waypoints").json() if w["name"] == "Boot prints")
    facts = {key: boot_prints[key] for key in ("kind", "lat", "lon", "name", "description", "note")}
    changed = client.put(f"/api/mission/waypoints/{boot_prints['id']}", json=facts | {"note": "Size 11"}).json()

    assert changed["radio_id"] == boot_prints["radio_id"]
    assert rows(session_2, f"SELECT team_id, message_id, time FROM waypoint WHERE waypoint_id = {changed['id']}") == before


def test_a_waypoint_that_was_not_moved_keeps_its_elevation_and_a_moved_one_loses_it(client, arizona07):
    client.post(f"/api/missions/{ARIZONA07_ID}/open")
    client.post("/api/mission/reopen")
    client.post("/api/mission/next-session", json={"keep_teams": True})
    session_2 = arizona07.parent / "session-02.sqlite3"
    waypoints = {w["name"]: w for w in client.get("/api/mission/waypoints").json()}

    def facts(name: str) -> dict:
        return {key: waypoints[name][key] for key in ("kind", "lat", "lon", "name", "description", "note")}

    reworded = client.put(f"/api/mission/waypoints/{waypoints['LZ 1']['id']}", json=facts("LZ 1") | {"name": "LZ one"}).json()
    moved = client.put(f"/api/mission/waypoints/{waypoints['Boot prints']['id']}", json=facts("Boot prints") | {"lat": 31.5072}).json()

    assert rows(session_2, f"SELECT elevation FROM waypoint WHERE waypoint_id = {reworded['id']}") == [(1393.0,)]
    assert rows(session_2, f"SELECT elevation FROM waypoint WHERE waypoint_id = {moved['id']}") == [(None,)]


def test_a_change_that_breaks_a_rule_is_refused_and_the_waypoint_stays(client, open_bear_creek):
    path = open_bear_creek("active")
    add(client)

    response = client.put("/api/mission/waypoints/1", json=HAZARD | {"name": ""})

    assert response.status_code == 422
    assert rows(path, ALL_ROWS) == [(1, "hazard", "Mine shaft", NOW_TEXT, None)]


# Removing

def test_removing_a_waypoint_closes_its_row_and_keeps_it_in_the_file(client, open_bear_creek, clock):
    path = open_bear_creek("active")
    add(client)
    clock.set(LATER)

    response = client.delete("/api/mission/waypoints/1")

    assert response.status_code == 204
    assert client.get("/api/mission/waypoints").json() == []
    assert rows(path, ALL_ROWS) == [(1, "hazard", "Mine shaft", NOW_TEXT, LATER_TEXT)]


@pytest.mark.parametrize("method", ["put", "delete"])
def test_a_waypoint_that_is_not_on_the_map_cannot_be_changed_or_removed(client, open_bear_creek, method):
    open_bear_creek("active")
    add(client)
    client.delete("/api/mission/waypoints/1")
    body = {"json": HAZARD} if method == "put" else {}

    for waypoint_id in (1, 99):  # removed, and never there
        response = getattr(client, method)(f"/api/mission/waypoints/{waypoint_id}", **body)

        assert response.status_code == 404
        assert response.json() == {"detail": f"There is no waypoint {waypoint_id} on the map."}


# The command post

def test_placing_a_new_command_post_closes_the_old_one(client, open_bear_creek, clock):
    path = open_bear_creek("planning")
    add(client, kind="command_post", name="Command post")
    add(client)
    clock.set(LATER)

    new = add(client, kind="command_post", name="Command post", lat=40.03)

    assert [(w["id"], w["kind"]) for w in client.get("/api/mission/waypoints").json()] == [(2, "hazard"), (3, "command_post")]
    assert new["lat"] == 40.03
    assert rows(path, "SELECT waypoint_id, removed_time FROM waypoint ORDER BY waypoint_id") == [(1, LATER_TEXT), (2, None), (3, None)]


def test_turning_a_waypoint_into_the_command_post_closes_the_old_one(client, open_bear_creek):
    open_bear_creek("planning")
    add(client, kind="command_post", name="Command post")
    add(client)

    client.put("/api/mission/waypoints/2", json=HAZARD | {"kind": "command_post"})

    assert [(w["id"], w["kind"]) for w in client.get("/api/mission/waypoints").json()] == [(3, "command_post")]


def test_moving_the_command_post_leaves_one_command_post(client, open_bear_creek):
    open_bear_creek("planning")
    add(client, kind="command_post", name="Command post")

    client.put("/api/mission/waypoints/1", json=HAZARD | {"kind": "command_post", "name": "Command post", "lat": 40.05})

    assert [(w["id"], w["lat"]) for w in client.get("/api/mission/waypoints").json()] == [(2, 40.05)]


# A session that cannot be changed

@pytest.mark.parametrize("status", ["paused", "ended"])
def test_a_paused_or_ended_session_refuses_every_change(client, open_bear_creek, status):
    path = open_bear_creek(status)

    responses = [
        client.post("/api/mission/waypoints", json=HAZARD),
        client.put("/api/mission/waypoints/1", json=HAZARD),
        client.delete("/api/mission/waypoints/1"),
    ]

    assert [r.status_code for r in responses] == [409, 409, 409]
    assert responses[0].json() == {"detail": f"This session is {status}, so nothing in it can be changed."}
    assert rows(path, "SELECT count(*) FROM waypoint") == [(0,)]
