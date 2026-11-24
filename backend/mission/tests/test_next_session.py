"""Starting the next session of a mission."""

import pytest

from mission.files import file_url
from missiondb.migrate import current, head_revision

from .conftest import ARIZONA07_ID, add_teams, rows

PRESSED = "2026-11-20T23:30:00Z"  # the stopped clock


def start_next(client, keep_teams: bool):
    return client.post("/api/mission/next-session", json={"keep_teams": keep_teams})


@pytest.fixture
def arizona07_reopened(client, arizona07, clock):
    """Arizona07 open and paused, ready for its second session. Answers with the first
    session's file."""
    client.post(f"/api/missions/{ARIZONA07_ID}/open")
    client.post("/api/mission/reopen")
    return arizona07


def test_the_next_session_is_a_new_file_beside_the_last_and_is_the_one_open(client, arizona07_reopened):
    response = start_next(client, keep_teams=True)

    assert response.status_code == 201
    mission = response.json()
    assert (mission["id"], mission["name"], mission["time_zone"]) == (ARIZONA07_ID, "Arizona07", "America/Phoenix")
    assert (mission["session"], mission["status"], mission["start_time"], mission["end_time"]) == (2, "active", PRESSED, None)
    assert [(s["number"], s["status"]) for s in mission["sessions"]] == [(1, "paused"), (2, "active")]
    assert client.get("/api/mission").json() == mission

    new_file = arizona07_reopened.with_name("session-02.sqlite3")
    assert new_file.is_file()
    assert current(file_url(new_file)) == head_revision()
    # The first session's file is as it was.
    assert rows(arizona07_reopened, "SELECT status, operational_period FROM mission") == [("paused", 1)]


def test_the_radios_people_area_sectors_and_waypoints_carry_over(client, arizona07_reopened):
    start_next(client, keep_teams=False)
    new_file = arizona07_reopened.with_name("session-02.sqlite3")

    def count(table):
        return rows(new_file, f"SELECT count(*) FROM {table}")[0][0]

    assert (count("team"), count("searcher"), count("search_area"), count("waypoint")) == (8, 21, 1, 6)
    # A sector keeps its id and its status: S4 and S6 are still partial, S7 still drawn.
    assert rows(new_file, "SELECT search_sector_id, status FROM search_sector ORDER BY 1") == [
        (1, "completed"), (2, "completed"), (3, "completed"), (4, "partial"),
        (5, "completed"), (6, "partial"), (7, "drawn"),
    ]
    # What happened in the first session stays in its file.
    assert (count("location"), count("message"), count("sector_assignment")) == (0, 0, 0)


def test_keeping_teams_puts_each_person_back_on_their_radio_and_each_radio_back_in_its_group(client, arizona07_reopened):
    start_next(client, keep_teams=True)
    new_file = arizona07_reopened.with_name("session-02.sqlite3")

    # As the first session ended: radio 3 in group 3, radio 4 in no group. Each row starts
    # when the new session does, and is still going.
    assert rows(new_file, "SELECT team_id, search_group_id, from_time, to_time FROM team_group_assignment ORDER BY team_id") == [
        (1, 1, PRESSED, None), (2, 1, PRESSED, None), (3, 3, PRESSED, None),
        (5, 3, PRESSED, None), (7, 2, PRESSED, None),
    ]
    assert rows(new_file, "SELECT search_group_id FROM search_group ORDER BY 1") == [(1,), (2,), (3,)]
    carries = "SELECT searcher_id, team_id FROM searcher_team_assignment WHERE from_time = '%s' AND to_time IS NULL ORDER BY searcher_id" % PRESSED
    as_it_ended = "SELECT searcher_id, team_id FROM searcher_team_assignment WHERE to_time = '2025-04-14T11:20:00Z' ORDER BY searcher_id"
    assert len(rows(new_file, carries)) == 21
    assert rows(new_file, carries) == rows(arizona07_reopened, as_it_ended)


def test_nobody_is_checked_in_by_starting_a_session(client, arizona07_reopened):
    start_next(client, keep_teams=True)

    assert rows(arizona07_reopened.with_name("session-02.sqlite3"), "SELECT count(*) FROM searcher_checkin") == [(0,)]


def test_starting_with_no_teams_brings_the_radios_and_people_but_no_team_rows_and_no_groups(client, arizona07_reopened):
    start_next(client, keep_teams=False)
    new_file = arizona07_reopened.with_name("session-02.sqlite3")

    for table in ("searcher_team_assignment", "team_group_assignment", "search_group"):
        assert rows(new_file, f"SELECT count(*) FROM {table}") == [(0,)]


def test_a_row_that_ended_before_the_session_did_is_not_brought_back(client, open_bear_creek):
    file = open_bear_creek("active")
    add_teams(file)  # searcher 3 was on radio 1 until 4 pm, and radio 2 in group 1 until 4 pm
    client.post("/api/mission/end-session")

    start_next(client, keep_teams=True)

    new_file = file.with_name("session-02.sqlite3")
    assert rows(new_file, "SELECT searcher_id, team_id FROM searcher_team_assignment ORDER BY 1") == [(1, 1), (2, 1), (3, 2)]
    assert rows(new_file, "SELECT team_id, search_group_id FROM team_group_assignment") == [(1, 1)]


@pytest.mark.parametrize("status", ["planning", "active", "ended"])
def test_the_next_session_starts_only_from_a_paused_one(client, open_bear_creek, status):
    file = open_bear_creek(status)

    response = start_next(client, keep_teams=True)

    assert response.status_code == 409
    assert response.json() == {"detail": "The next session can be started only from a paused session."}
    assert not file.with_name("session-02.sqlite3").exists()
    assert client.get("/api/mission").json()["session"] == 1


def test_a_file_already_in_the_way_is_refused_and_left_alone(client, open_bear_creek):
    file = open_bear_creek("paused")
    in_the_way = file.with_name("session-02.sqlite3")
    in_the_way.write_text("something else")

    response = start_next(client, keep_teams=True)

    assert response.status_code == 409
    assert response.json() == {"detail": "session-02.sqlite3 is already in the mission's folder."}
    assert in_the_way.read_text() == "something else"


def test_the_request_must_say_whether_teams_are_kept(client, open_bear_creek):
    open_bear_creek("paused")

    assert client.post("/api/mission/next-session", json={}).status_code == 422


def test_a_session_with_a_later_one_is_no_longer_the_open_one_so_it_cannot_be_resumed(client, open_bear_creek):
    open_bear_creek("paused")
    start_next(client, keep_teams=False)

    # Session 2 is open and active, so there is no paused session to resume.
    response = client.post("/api/mission/resume")

    assert response.status_code == 409
    assert client.get("/api/mission").json()["session"] == 2
