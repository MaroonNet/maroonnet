"""Changing the mission's time zone."""

import pytest

from .conftest import BEAR_CREEK_ID, rows, utc

ZONE_AND_TIMES = "SELECT time_zone, start_time, end_time FROM mission"


def change(client, time_zone):
    return client.patch("/api/mission", json={"time_zone": time_zone})


@pytest.mark.parametrize("status", ["planning", "active", "paused"])
def test_the_time_zone_can_be_changed_until_the_mission_ends(client, open_bear_creek, status):
    file = open_bear_creek(status)
    [(_, start, end)] = rows(file, ZONE_AND_TIMES)

    response = change(client, "America/Phoenix")

    assert response.status_code == 200
    assert response.json()["time_zone"] == "America/Phoenix"
    # No saved time changes: only the zone they are shown in.
    assert rows(file, ZONE_AND_TIMES) == [("America/Phoenix", start, end)]


def test_an_ended_mission_keeps_its_time_zone(client, open_bear_creek):
    file = open_bear_creek("ended")

    response = change(client, "America/Phoenix")

    assert response.status_code == 409
    assert response.json() == {"detail": "The mission has ended, so its time zone cannot be changed."}
    assert rows(file, "SELECT time_zone FROM mission") == [("America/Denver",)]


def test_a_time_zone_that_does_not_exist_is_refused(client, open_bear_creek):
    file = open_bear_creek("planning")

    assert change(client, "Mountain").status_code == 422
    assert rows(file, "SELECT time_zone FROM mission") == [("America/Denver",)]


def test_only_the_time_zone_can_be_changed_this_way(client, open_bear_creek):
    file = open_bear_creek("planning")

    response = client.patch("/api/mission", json={"time_zone": "America/Phoenix", "name": "Other"})

    assert response.status_code == 422
    assert rows(file, "SELECT name, time_zone FROM mission") == [("Bear Creek", "America/Denver")]


def test_the_change_is_saved_in_the_open_sessions_file_only(client, make_mission):
    first = make_mission("bear-creek/session-01.sqlite3", session=1, status="paused",
                         start=utc(2026, 11, 20, 15), end=utc(2026, 11, 20, 23))
    second = make_mission("bear-creek/session-02.sqlite3", session=2, status="active", start=utc(2026, 11, 21, 15))
    client.post(f"/api/missions/{BEAR_CREEK_ID}/open")

    change(client, "America/Phoenix")

    assert rows(second, "SELECT time_zone FROM mission") == [("America/Phoenix",)]
    assert rows(first, "SELECT time_zone FROM mission") == [("America/Denver",)]


def test_with_no_mission_open_changing_the_time_zone_says_so(client):
    assert change(client, "America/Phoenix").status_code == 409
