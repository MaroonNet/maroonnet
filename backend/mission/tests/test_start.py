"""Start Mission."""

import pytest

from .conftest import rows


def test_start_mission_makes_a_planning_mission_active_and_saves_the_start_time(client, open_bear_creek):
    file = open_bear_creek("planning")

    response = client.post("/api/mission/start")

    assert response.status_code == 200
    mission = response.json()
    assert (mission["status"], mission["start_time"], mission["end_time"]) == ("active", "2026-11-20T23:30:00Z", None)
    assert rows(file, "SELECT status, start_time, end_time FROM mission") == [("active", "2026-11-20T23:30:00Z", None)]


@pytest.mark.parametrize("status", ["active", "paused", "ended"])
def test_only_a_mission_in_planning_can_be_started(client, open_bear_creek, status):
    file = open_bear_creek(status)
    before = rows(file, "SELECT status, start_time, end_time FROM mission")

    response = client.post("/api/mission/start")

    assert response.status_code == 409
    assert response.json() == {"detail": "Only a mission in planning can be started."}
    assert rows(file, "SELECT status, start_time, end_time FROM mission") == before


def test_with_no_mission_open_start_mission_says_so(client):
    response = client.post("/api/mission/start")

    assert response.status_code == 409
    assert response.json() == {"detail": "No mission is open."}
