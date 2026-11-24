"""End Session, End Mission, and undoing each: Resume Session and Reopen."""

import pytest

from .conftest import ARIZONA07_ID, add_sectors, add_teams, rows, utc

MISSION = "SELECT status, start_time, end_time FROM mission"
STARTED = "2026-11-20T15:00:00Z"
PRESSED = "2026-11-20T23:30:00Z"   # the stopped clock: when a test's button is pressed
ENDED_BEFORE = "2026-11-20T22:00:00Z"  # the end time of a mission made already paused or ended

# Who carries which radio, which radio is in which group, and who is checked in.
TEAM_TABLES = {
    "carries": "SELECT searcher_id, team_id, to_time FROM searcher_team_assignment ORDER BY assignment_id",
    "groups": "SELECT team_id, search_group_id, to_time FROM team_group_assignment ORDER BY assignment_id",
    "checkins": "SELECT searcher_id, out_time FROM searcher_checkin ORDER BY checkin_id",
}


def teams(file) -> dict:
    return {table: rows(file, sql) for table, sql in TEAM_TABLES.items()}


def refused(response, detail) -> bool:
    return response.status_code == 409 and response.json() == {"detail": detail}


# End Session

def test_end_session_pauses_an_active_session_and_saves_the_end_time(client, open_bear_creek):
    file = open_bear_creek("active")

    response = client.post("/api/mission/end-session")

    assert response.status_code == 200
    assert (response.json()["status"], response.json()["end_time"]) == ("paused", PRESSED)
    assert rows(file, MISSION) == [("paused", STARTED, PRESSED)]


def test_end_session_closes_every_open_team_row_and_check_in_at_the_end_time(client, open_bear_creek):
    file = open_bear_creek("active")
    add_teams(file)

    client.post("/api/mission/end-session")

    assert teams(file) == {
        # The first row of each table had ended at 4 pm, and keeps that time.
        "carries": [(3, 1, "2026-11-20T16:00:00Z"), (1, 1, PRESSED), (2, 1, PRESSED), (3, 2, PRESSED)],
        "groups": [(2, 1, "2026-11-20T16:00:00Z"), (1, 1, PRESSED)],
        "checkins": [(3, "2026-11-20T16:00:00Z"), (1, PRESSED), (2, PRESSED), (3, PRESSED)],
    }


@pytest.mark.parametrize("status", ["planning", "paused", "ended"])
def test_only_an_active_session_can_be_ended(client, open_bear_creek, status):
    file = open_bear_creek(status)
    before = rows(file, MISSION)

    assert refused(client.post("/api/mission/end-session"), "Only an active session can be ended.")
    assert rows(file, MISSION) == before


# End Mission

def test_end_mission_ends_an_active_session_and_closes_its_team_rows(client, open_bear_creek):
    file = open_bear_creek("active")
    add_teams(file)

    response = client.post("/api/mission/end")

    assert response.status_code == 200
    assert rows(file, MISSION) == [("ended", STARTED, PRESSED)]
    assert teams(file)["checkins"] == [(3, "2026-11-20T16:00:00Z"), (1, PRESSED), (2, PRESSED), (3, PRESSED)]


def test_end_mission_on_a_paused_session_keeps_the_end_time_it_has(client, open_bear_creek):
    file = open_bear_creek("paused")

    assert client.post("/api/mission/end").status_code == 200
    assert rows(file, MISSION) == [("ended", STARTED, ENDED_BEFORE)]


def test_a_mission_that_has_not_started_or_has_ended_cannot_be_ended(client, open_bear_creek):
    open_bear_creek("planning")
    assert refused(client.post("/api/mission/end"), "A mission in planning has not started, so it cannot be ended.")

    client.post("/api/mission/start")
    client.post("/api/mission/end")
    assert refused(client.post("/api/mission/end"), "The mission has already ended.")


# Resume Session

def test_resume_puts_a_paused_session_back_to_active_with_no_end_time(client, open_bear_creek):
    file = open_bear_creek("active")
    client.post("/api/mission/end-session")

    response = client.post("/api/mission/resume")

    assert response.status_code == 200
    assert (response.json()["status"], response.json()["end_time"]) == ("active", None)
    assert rows(file, MISSION) == [("active", STARTED, None)]


def test_end_session_then_resume_leaves_the_teams_as_they_were(client, open_bear_creek):
    file = open_bear_creek("active")
    add_teams(file)
    before = teams(file)

    client.post("/api/mission/end-session")
    assert teams(file) != before
    client.post("/api/mission/resume")

    assert teams(file) == before


@pytest.mark.parametrize("status", ["planning", "active", "ended"])
def test_only_a_paused_session_can_be_resumed(client, open_bear_creek, status):
    file = open_bear_creek(status)
    before = rows(file, MISSION)

    assert refused(client.post("/api/mission/resume"), "Only a paused session can be resumed.")
    assert rows(file, MISSION) == before


# Reopen

def test_reopen_makes_an_ended_mission_paused_and_keeps_its_end_time(client, open_bear_creek):
    file = open_bear_creek("ended")

    response = client.post("/api/mission/reopen")

    assert response.status_code == 200
    assert rows(file, MISSION) == [("paused", STARTED, ENDED_BEFORE)]


@pytest.mark.parametrize("status", ["planning", "active", "paused"])
def test_only_an_ended_mission_can_be_reopened(client, open_bear_creek, status):
    file = open_bear_creek(status)
    before = rows(file, MISSION)

    assert refused(client.post("/api/mission/reopen"), "Only an ended mission can be reopened.")
    assert rows(file, MISSION) == before


def test_a_mistaken_end_mission_is_undone_by_reopen_then_resume(client, open_bear_creek):
    file = open_bear_creek("active")
    add_teams(file)
    before = teams(file)

    client.post("/api/mission/end")
    client.post("/api/mission/reopen")
    client.post("/api/mission/resume")

    assert rows(file, MISSION) == [("active", STARTED, None)]
    assert teams(file) == before


# Sectors a group still holds. End Session leaves them alone; End Mission takes each group
# off its sector; Reopen puts them back.

SECTOR_TABLES = {
    "sectors": "SELECT name, status FROM search_sector ORDER BY search_sector_id",
    "holds": "SELECT search_sector_id, search_group_id, to_time FROM sector_assignment ORDER BY assignment_id",
}
SECTORS_BEFORE = {
    "sectors": [("S1", "searching"), ("S2", "drawn"), ("S3", "partial"), ("S4", "drawn"), ("S5", "completed")],
    "holds": [(5, 1, "2026-11-20T15:05:00Z"), (3, 3, "2026-11-20T15:08:00Z"), (1, 1, None), (2, 2, None), (3, 3, None)],
}


def sectors(file) -> dict:
    return {table: rows(file, sql) for table, sql in SECTOR_TABLES.items()}


def released_at(time) -> dict:
    """The sectors once every group has been taken off: the searching one is partial, and
    each hold that was going ended at this time. Earlier holds keep their own end."""
    return {
        "sectors": [("S1", "partial"), ("S2", "drawn"), ("S3", "partial"), ("S4", "drawn"), ("S5", "completed")],
        "holds": [(5, 1, "2026-11-20T15:05:00Z"), (3, 3, "2026-11-20T15:08:00Z"), (1, 1, time), (2, 2, time), (3, 3, time)],
    }


@pytest.fixture
def mid_search(open_bear_creek):
    file = open_bear_creek("active")
    add_teams(file)
    add_sectors(file)
    assert sectors(file) == SECTORS_BEFORE
    return file


def test_end_session_leaves_sectors_and_the_groups_holding_them_alone(client, mid_search):
    client.post("/api/mission/end-session")

    assert sectors(mid_search) == SECTORS_BEFORE


def test_end_mission_takes_each_group_off_its_sector_and_a_searching_sector_becomes_partial(client, mid_search):
    client.post("/api/mission/end")

    assert sectors(mid_search) == released_at(PRESSED)


def test_end_mission_on_a_paused_session_takes_the_groups_off_at_the_time_the_session_ended(client, mid_search, clock):
    client.post("/api/mission/end-session")  # at the stopped clock's time
    clock.set(utc(2026, 11, 21, 9))          # the next morning

    client.post("/api/mission/end")

    assert sectors(mid_search) == released_at(PRESSED)


def test_reopen_puts_each_group_back_on_its_sector_as_it_was(client, mid_search):
    client.post("/api/mission/end")

    client.post("/api/mission/reopen")

    # S1 is searching again because radio 1 had entered it. S3 was held and not yet
    # entered, so it is partial as before.
    assert sectors(mid_search) == SECTORS_BEFORE


def test_arizona07_reopened_and_resumed_has_its_teams_as_the_night_ended(client, arizona07):
    client.post(f"/api/missions/{ARIZONA07_ID}/open")

    assert client.post("/api/mission/reopen").json()["status"] == "paused"
    assert client.post("/api/mission/resume").json()["status"] == "active"

    # Radio 3 had moved to group 3 and radio 4 had left group 2, both before the end.
    open_groups = "SELECT team_id, search_group_id FROM team_group_assignment WHERE to_time IS NULL ORDER BY team_id"
    assert rows(arizona07, open_groups) == [(1, 1), (2, 1), (3, 3), (5, 3), (7, 2)]
    assert rows(arizona07, "SELECT count(*) FROM searcher_team_assignment WHERE to_time IS NULL") == [(21,)]
    assert rows(arizona07, "SELECT count(*) FROM searcher_checkin WHERE out_time IS NULL") == [(21,)]
