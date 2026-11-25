"""Saving the open mission's search area."""

import pytest

from mission.tests.conftest import ARIZONA07_ID, rows
from sectors.tests.conftest import add_sector

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


def test_a_new_area_that_holds_every_sector_is_saved(client, open_bear_creek):
    path = open_bear_creek("active")
    add_sector(path, 1)  # the square 40.0 to 40.05 N, 105.6 to 105.55 W
    hugging = {"min_lat": 40.0, "min_lon": -105.6, "max_lat": 40.05, "max_lon": -105.55}  # its corners on the line

    assert client.put("/api/mission/search-area", json=hugging).status_code == 200


@pytest.mark.parametrize(("sectors", "line"), [
    ([1], "S1 would be outside this search area."),
    ([1, 2], "S1 and S2 would be outside this search area."),
    ([1, 2, 3], "S1, S2 and S3 would be outside this search area."),
])
def test_a_new_area_that_would_leave_a_sector_outside_is_refused(client, open_bear_creek, sectors, line):
    path = open_bear_creek("active")
    client.put("/api/mission/search-area", json=BEAR_CREEK_AREA)
    for sector_id in sectors:
        add_sector(path, sector_id)
    north_half = {"min_lat": 40.02, "min_lon": -105.7, "max_lat": 40.1, "max_lon": -105.5}  # cuts the squares

    response = client.put("/api/mission/search-area", json=north_half)

    assert response.status_code == 409
    assert response.json() == {"detail": line}
    assert client.get("/api/mission/search-area").json() == BEAR_CREEK_AREA


def test_arizona07_ended_keeps_its_search_area(client, arizona07):
    client.post(f"/api/missions/{ARIZONA07_ID}/open")

    response = client.put("/api/mission/search-area", json=BEAR_CREEK_AREA)

    assert response.status_code == 409
    assert client.get("/api/mission/search-area").json()["min_lat"] == 31.3926


def test_with_no_mission_open_saving_is_refused(client):
    response = client.put("/api/mission/search-area", json=BEAR_CREEK_AREA)

    assert response.status_code == 409
    assert response.json() == {"detail": "No mission is open."}
