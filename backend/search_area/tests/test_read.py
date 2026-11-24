"""Reading the open mission's search area."""

from mission.tests.conftest import ARIZONA07_ID


def test_arizona07s_search_area_is_read(client, arizona07):
    client.post(f"/api/missions/{ARIZONA07_ID}/open")

    response = client.get("/api/mission/search-area")

    assert response.status_code == 200
    assert response.json() == {"min_lat": 31.3926, "min_lon": -110.8083, "max_lat": 31.619, "max_lon": -110.544}


def test_a_mission_with_no_search_area_answers_nothing(client, open_bear_creek):
    open_bear_creek("planning")

    response = client.get("/api/mission/search-area")

    assert response.status_code == 200
    assert response.json() is None


def test_with_no_mission_open_the_request_is_refused(client):
    response = client.get("/api/mission/search-area")

    assert response.status_code == 409
    assert response.json() == {"detail": "No mission is open."}
