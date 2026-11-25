"""Adding a sector to the open mission."""

import pytest

from mission.tests.conftest import ARIZONA07_ID, rows
from sectors.tests.conftest import SQUARE, add_sector, corners


def test_a_new_sector_is_saved_as_s1_drawn_with_its_corners(client, bear_creek):
    path = bear_creek("planning")

    response = client.post("/api/mission/sectors", json=corners(*SQUARE))

    assert response.status_code == 201
    sector = response.json()
    assert (sector["id"], sector["name"], sector["status"], sector["group_id"], sector["can_edit"]) == (1, "S1", "drawn", None, True)
    assert sector["corners"] == corners(*SQUARE)["corners"]
    assert sector["created_time"] == "2026-11-20T23:30:00Z"  # the stopped clock's time
    assert sector["completed_time"] is None
    assert rows(path, "SELECT search_sector_id, name, status FROM search_sector") == [(1, "S1", "drawn")]
    assert rows(path, "SELECT point_order, lat, lon FROM search_sector_point ORDER BY point_order") == [
        (order, lat, lon) for order, (lat, lon) in enumerate(SQUARE, start=1)
    ]
    assert client.get("/api/mission/sectors").json() == [sector]


def test_a_new_sector_takes_the_number_after_the_highest(client, bear_creek):
    path = bear_creek("active")
    add_sector(path, 1)
    add_sector(path, 4)  # S2 and S3 were deleted

    sector = client.post("/api/mission/sectors", json=corners(*SQUARE)).json()

    assert (sector["id"], sector["name"]) == (5, "S5")


def test_twenty_four_corners_are_allowed(client, bear_creek):
    bear_creek("planning")
    # A zigzag along the bottom, closed by the top side, so no two sides cross.
    zigzag = [(40.0 + 0.001 * (i % 2), -105.6 + 0.002 * i) for i in range(22)]
    shape = [*zigzag, (40.05, zigzag[-1][1]), (40.05, -105.6)]

    response = client.post("/api/mission/sectors", json=corners(*shape))

    assert response.status_code == 201
    assert len(response.json()["corners"]) == 24


@pytest.mark.parametrize("shape", [
    SQUARE[:2],                                                              # two corners
    [(40.0 + 0.001 * (i % 2), -105.6 + 0.001 * i) for i in range(25)],     # twenty-five
    [(40.0, -105.6), (40.05, -105.55), (40.05, -105.6), (40.0, -105.55)],  # sides that cross
])
def test_a_shape_that_breaks_a_rule_is_refused(client, bear_creek, shape):
    path = bear_creek("planning")

    response = client.post("/api/mission/sectors", json=corners(*shape))

    assert response.status_code == 422
    assert rows(path, "SELECT count(*) FROM search_sector") == [(0,)]


def test_crossing_sides_are_refused_with_a_plain_reason(client, bear_creek):
    bear_creek("planning")
    bow_tie = [(40.0, -105.6), (40.05, -105.55), (40.05, -105.6), (40.0, -105.55)]

    detail = client.post("/api/mission/sectors", json=corners(*bow_tie)).json()["detail"]

    assert "The sector's sides cannot cross." in detail[0]["msg"]


def test_a_sector_on_the_search_area_line_is_allowed(client, bear_creek):
    bear_creek("planning")
    whole_area = [(39.9, -105.7), (40.1, -105.7), (40.1, -105.5), (39.9, -105.5)]

    assert client.post("/api/mission/sectors", json=corners(*whole_area)).status_code == 201


def test_a_sector_outside_the_search_area_is_refused(client, bear_creek):
    path = bear_creek("planning")
    one_corner_out = [*SQUARE[:3], (40.0, -105.49)]

    response = client.post("/api/mission/sectors", json=corners(*one_corner_out))

    assert response.status_code == 409
    assert response.json() == {"detail": "A sector must be inside the search area."}
    assert rows(path, "SELECT count(*) FROM search_sector") == [(0,)]


def test_with_no_search_area_a_sector_is_refused(client, open_bear_creek):
    path = open_bear_creek("planning")

    response = client.post("/api/mission/sectors", json=corners(*SQUARE))

    assert response.status_code == 409
    assert response.json() == {"detail": "Draw a search area first."}
    assert rows(path, "SELECT count(*) FROM search_sector") == [(0,)]


@pytest.mark.parametrize("status", ["paused", "ended"])
def test_a_paused_or_ended_session_refuses_a_new_sector(client, bear_creek, status):
    path = bear_creek(status)

    response = client.post("/api/mission/sectors", json=corners(*SQUARE))

    assert response.status_code == 409
    assert response.json() == {"detail": f"This session is {status}, so nothing in it can be changed."}
    assert rows(path, "SELECT count(*) FROM search_sector") == [(0,)]


def test_arizona07_ended_refuses_a_new_sector(client, arizona07):
    client.post(f"/api/missions/{ARIZONA07_ID}/open")

    response = client.post("/api/mission/sectors", json=corners((31.5, -110.68), (31.51, -110.68), (31.51, -110.67)))

    assert response.status_code == 409
    assert len(client.get("/api/mission/sectors").json()) == 7
