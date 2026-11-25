"""The rest of a sector's life: assigned to a group, released, entered, completed."""

from pathlib import Path

import pytest
from sqlmodel import Session

from mission.tests.conftest import ARIZONA07_ID, add_teams, rows, utc
from missiondb import create_db_engine
from missiondb.models import SearchSector
from sectors import life
from sectors.tests.conftest import add_sector, write

NOW_TEXT = "2026-11-20T23:30:00Z"
LATER = utc(2026, 11, 20, 23, 45)
LATER_TEXT = "2026-11-20T23:45:00Z"


@pytest.fixture
def field(bear_creek):
    """Bear Creek with sectors S1, S2 and S3, all drawn, and three groups: group 1 is radio 1,
    group 2 is radio 2, and group 3 has no teams."""

    def make(status: str = "active") -> Path:
        path = bear_creek(status)
        add_teams(path)
        write(path, """
            INSERT INTO search_group (search_group_id) VALUES (2), (3);
            INSERT INTO team_group_assignment (team_id, search_group_id, from_time) VALUES (2, 2, '2026-11-20T16:00:00Z');
        """)
        for sector_id in (1, 2, 3):
            add_sector(path, sector_id)
        return path

    return make


def act(client, sector_id: int, action: str, **body):
    return client.post(f"/api/mission/sectors/{sector_id}/{action}", json=body or None)


def sector(client, sector_id: int) -> dict:
    return next(s for s in client.get("/api/mission/sectors").json() if s["id"] == sector_id)


def holds(path: Path) -> list[tuple]:
    return rows(path, "SELECT search_sector_id, search_group_id, from_time, to_time FROM sector_assignment ORDER BY assignment_id")


# Assign

def test_a_sector_is_assigned_to_a_group(client, field):
    path = field()

    response = act(client, 1, "assign", group_id=1)

    assert response.status_code == 200
    s1 = response.json()
    assert (s1["status"], s1["group_id"], s1["assigned_time"], s1["can_edit"]) == ("drawn", 1, NOW_TEXT, False)
    assert holds(path) == [(1, 1, NOW_TEXT, None)]
    assert client.get("/api/mission/groups").json()[0]["sector"] == {"id": 1, "name": "S1"}


def test_a_sector_can_be_assigned_while_the_mission_is_in_planning(client, field):
    field("planning")

    assert act(client, 1, "assign", group_id=1).status_code == 200


def test_assigning_to_a_busy_group_releases_the_sector_it_held(client, field, clock):
    path = field()
    act(client, 1, "assign", group_id=1)
    clock.set(LATER)

    act(client, 2, "assign", group_id=1)

    # Nobody had entered S1, so it is drawn again, with its shape still locked.
    s1 = sector(client, 1)
    assert (s1["status"], s1["group_id"], s1["can_edit"]) == ("drawn", None, False)
    assert sector(client, 2)["group_id"] == 1
    assert holds(path) == [(1, 1, NOW_TEXT, LATER_TEXT), (2, 1, LATER_TEXT, None)]


def test_a_sector_being_searched_is_left_partial_when_its_group_is_given_another(client, field):
    field()
    act(client, 1, "assign", group_id=1)
    act(client, 1, "entered", radio_id=1)

    act(client, 2, "assign", group_id=1)

    assert (sector(client, 1)["status"], sector(client, 1)["group_id"]) == ("partial", None)


def test_a_partial_sector_can_be_assigned_again(client, field):
    path = field()
    write(path, "UPDATE search_sector SET status = 'partial' WHERE search_sector_id = 1")

    s1 = act(client, 1, "assign", group_id=2).json()

    assert (s1["status"], s1["group_id"]) == ("partial", 2)


@pytest.mark.parametrize(("setup", "sector_id", "group_id", "code", "reason"), [
    (lambda path: write(path, "UPDATE search_sector SET status = 'completed', completed_time = '2026-11-20T18:00:00Z' WHERE search_sector_id = 1"),
     1, 1, 409, "S1 is completed, so it cannot be assigned."),
    (lambda path: write(path, "INSERT INTO sector_assignment (search_sector_id, search_group_id, from_time) VALUES (1, 2, '2026-11-20T16:30:00Z')"),
     1, 1, 409, "Group 2 holds S1. Release it first."),
    (lambda path: None, 1, 3, 409, "Group 3 has no teams, so it cannot be given a sector."),
    (lambda path: None, 1, 9, 404, "No group in this mission has this id."),
    (lambda path: None, 9, 1, 404, "There is no sector S9."),
])
def test_an_assignment_that_cannot_be_made_is_refused(client, field, setup, sector_id, group_id, code, reason):
    path = field()
    setup(path)
    before = holds(path)

    response = act(client, sector_id, "assign", group_id=group_id)

    assert (response.status_code, response.json()["detail"]) == (code, reason)
    assert holds(path) == before


def test_nothing_is_assigned_in_a_paused_session(client, field):
    field("paused")

    response = act(client, 1, "assign", group_id=1)

    assert response.status_code == 409
    assert response.json()["detail"] == "This session is paused, so nothing in it can be changed."


# Release

def test_releasing_a_sector_nobody_entered_leaves_it_drawn(client, field, clock):
    path = field("planning")
    act(client, 1, "assign", group_id=1)
    clock.set(LATER)

    s1 = act(client, 1, "release").json()

    assert (s1["status"], s1["group_id"], s1["assigned_time"], s1["can_edit"]) == ("drawn", None, None, False)
    assert holds(path) == [(1, 1, NOW_TEXT, LATER_TEXT)]
    assert client.get("/api/mission/groups").json()[0]["sector"] is None


def test_releasing_a_sector_being_searched_leaves_it_partial(client, field):
    field()
    act(client, 1, "assign", group_id=1)
    act(client, 1, "entered", radio_id=1)

    assert act(client, 1, "release").json()["status"] == "partial"


def test_a_sector_no_group_holds_cannot_be_released(client, field):
    field()

    response = act(client, 1, "release")

    assert (response.status_code, response.json()["detail"]) == (409, "No group holds S1.")


# Mark entered

def test_marking_a_team_as_entered_turns_the_sector_searching(client, field, clock):
    path = field()
    act(client, 1, "assign", group_id=1)
    clock.set(LATER)

    s1 = act(client, 1, "entered", radio_id=1).json()

    assert (s1["status"], s1["group_id"], s1["entered_time"]) == ("searching", 1, LATER_TEXT)
    assert rows(path, "SELECT team_id, search_sector_id, entered_time FROM sector_entry") == [(1, 1, LATER_TEXT)]


def test_a_team_entering_again_after_a_release_turns_the_sector_searching_again(client, field, clock):
    path = field()
    act(client, 1, "assign", group_id=1)
    act(client, 1, "entered", radio_id=1)
    act(client, 1, "release")
    act(client, 1, "assign", group_id=1)
    clock.set(LATER)

    s1 = act(client, 1, "entered", radio_id=1).json()

    # missiondb keeps a team's first entry only, so no second row is written.
    assert s1["status"] == "searching"
    assert rows(path, "SELECT team_id, search_sector_id, entered_time FROM sector_entry") == [(1, 1, NOW_TEXT)]


@pytest.mark.parametrize(("status", "assigned_to", "radio_id", "code", "reason"), [
    ("active", None, 1, 409, "No group holds S1."),
    ("active", 1, 2, 409, "Radio 2 is not in Group 1, which holds S1."),
    ("active", 1, 9, 404, "No radio in this mission has this id."),
    ("planning", 1, 1, 409, "The mission has not started, so no team has entered a sector."),
])
def test_an_entry_that_cannot_be_is_refused(client, field, status, assigned_to, radio_id, code, reason):
    path = field(status)
    if assigned_to:
        act(client, 1, "assign", group_id=assigned_to)

    response = act(client, 1, "entered", radio_id=radio_id)

    assert (response.status_code, response.json()["detail"]) == (code, reason)
    assert rows(path, "SELECT count(*) FROM sector_entry") == [(0,)]
    assert sector(client, 1)["status"] == "drawn"


def test_a_radio_entering_a_sector_its_group_does_not_hold_is_recorded_and_changes_nothing(field):
    # What a radio's position will do once radios report: radio 1 walks through S2, which
    # nobody was given.
    path = field()
    engine = create_db_engine(f"sqlite:///{path}")
    with Session(engine) as db:
        life.team_entered(db, 1, db.get(SearchSector, 2), LATER)
        db.commit()
    engine.dispose()

    assert rows(path, "SELECT team_id, search_sector_id, entered_time FROM sector_entry") == [(1, 2, LATER_TEXT)]
    assert rows(path, "SELECT status FROM search_sector WHERE search_sector_id = 2") == [("drawn",)]


# Mark Completed

@pytest.mark.parametrize("entered", [False, True])
def test_a_sector_a_group_holds_is_marked_completed(client, field, clock, entered):
    path = field()
    act(client, 1, "assign", group_id=1)
    if entered:
        act(client, 1, "entered", radio_id=1)
    clock.set(LATER)

    s1 = act(client, 1, "complete").json()

    assert (s1["status"], s1["completed_time"], s1["completed_by"], s1["group_id"]) == ("completed", LATER_TEXT, 1, None)
    assert holds(path) == [(1, 1, NOW_TEXT, LATER_TEXT)]  # completing ends the group's hold


def test_a_completed_sector_is_final(client, field):
    field()
    act(client, 1, "assign", group_id=1)
    act(client, 1, "complete")

    for action, body in (("assign", {"group_id": 1}), ("release", {}), ("entered", {"radio_id": 1}), ("complete", {})):
        response = act(client, 1, action, **body)
        assert response.status_code == 409, action
    assert sector(client, 1)["status"] == "completed"


@pytest.mark.parametrize(("status", "assigned_to", "reason"), [
    ("active", None, "No group holds S1. Assign it first."),
    ("planning", 1, "The mission has not started, so a sector cannot be completed."),
])
def test_a_completion_that_cannot_be_is_refused(client, field, status, assigned_to, reason):
    field(status)
    if assigned_to:
        act(client, 1, "assign", group_id=assigned_to)

    response = act(client, 1, "complete")

    assert (response.status_code, response.json()["detail"]) == (409, reason)
    assert sector(client, 1)["status"] == "drawn"


# What the list says of a sector's past

def test_arizona07_sectors_come_with_their_sends_and_who_completed_them(client, arizona07):
    client.post(f"/api/missions/{ARIZONA07_ID}/open")

    sectors = client.get("/api/mission/sectors").json()

    assert sectors[0]["sends"] == [
        {"radio_id": 1, "sent_time": "2025-04-14T03:50:55Z", "ack_time": "2025-04-14T03:51:08Z"},
        {"radio_id": 2, "sent_time": "2025-04-14T03:50:57Z", "ack_time": "2025-04-14T03:51:06Z"},
        {"radio_id": 3, "sent_time": "2025-04-14T03:50:59Z", "ack_time": "2025-04-14T03:51:10Z"},
    ]
    assert sectors[6]["sends"] == []  # S7 was never assigned
    # S1, S2, S3 and S5 were completed; S4 and S6 were left partial.
    assert [s["completed_by"] for s in sectors] == [1, 3, 2, None, 2, None, None]
