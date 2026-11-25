"""Saving the open mission's search area."""

import pytest

from mission.tests.conftest import ARIZONA07_ID, rows

BEAR_CREEK_AREA = {"min_lat": 39.9, "min_lon": -105.7, "max_lat": 40.1, "max_lon": -105.5}


def test_a_new_missions_search_area_is_saved_and_read_back(client, open_bear_creek):
    path = open_bear_creek("planning")

    response = client.put("/api/mission/search-area", json=BEAR_CREEK_AREA)

    assert response.status_code == 200
    assert response.json() == BEAR_CREEK_AREA
    assert client.get("/api/mission/search-area").json() == BEAR_CREEK_AREA
    assert rows(path, "SELECT mission_id, min_lat, min_lon, max_lat, max_lon FROM search_area") == [
        (1, 39.9, -105.7, 40.1, -105.5),
    ]


def test_saving_again_replaces_the_search_area(client, open_bear_creek):
    path = open_bear_creek("active")
    client.put("/api/mission/search-area", json=BEAR_CREEK_AREA)
    smaller = {"min_lat": 39.95, "min_lon": -105.65, "max_lat": 40.05, "max_lon": -105.55}

    response = client.put("/api/mission/search-area", json=smaller)

    assert response.status_code == 200
    assert client.get("/api/mission/search-area").json() == smaller
    assert rows(path, "SELECT count(*) FROM search_area") == [(1,)]  # still one, not two


@pytest.mark.parametrize("change", [
    {"min_lat": 40.1, "max_lat": 39.9},     # upside down: south above north
    {"min_lon": -105.5, "max_lon": -105.7}, # back to front: west past east
    {"max_lat": 39.9},                      # no height
    {"max_lat": 90.5},                      # past the north pole
    {"min_lon": -180.5},                    # past the date line
])
def test_a_rectangle_that_breaks_the_corner_rule_is_refused(client, open_bear_creek, change):
    path = open_bear_creek("planning")

    response = client.put("/api/mission/search-area", json=BEAR_CREEK_AREA | change)

    assert response.status_code == 422
    assert rows(path, "SELECT count(*) FROM search_area") == [(0,)]


@pytest.mark.parametrize("status", ["paused", "ended"])
def test_a_paused_or_ended_session_refuses_a_new_search_area(client, open_bear_creek, status):
    path = open_bear_creek(status)

    response = client.put("/api/mission/search-area", json=BEAR_CREEK_AREA)

    assert response.status_code == 409
    assert response.json() == {"detail": f"This session is {status}, so nothing in it can be changed."}
    assert rows(path, "SELECT count(*) FROM search_area") == [(0,)]


def test_arizona07_ended_keeps_its_search_area(client, arizona07):
    client.post(f"/api/missions/{ARIZONA07_ID}/open")

    response = client.put("/api/mission/search-area", json=BEAR_CREEK_AREA)

    assert response.status_code == 409
    assert client.get("/api/mission/search-area").json()["min_lat"] == 31.3926


def test_with_no_mission_open_saving_is_refused(client):
    response = client.put("/api/mission/search-area", json=BEAR_CREEK_AREA)

    assert response.status_code == 409
    assert response.json() == {"detail": "No mission is open."}
