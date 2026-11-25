"""Changing a sector's shape (Edit Shape)."""

import pytest

from mission.tests.conftest import rows
from sectors.tests.conftest import SQUARE, add_sector, assign, corners, write

# The square with one more corner pulled out of its right side.
FIVE_CORNERS = [(40.0, -105.6), (40.05, -105.6), (40.05, -105.55), (40.025, -105.52), (40.0, -105.55)]


def test_a_drawn_sectors_shape_is_replaced(client, bear_creek):
    path = bear_creek("active")
    add_sector(path, 1)

    response = client.put("/api/mission/sectors/1/corners", json=corners(*FIVE_CORNERS))

    assert response.status_code == 200
    assert response.json()["corners"] == corners(*FIVE_CORNERS)["corners"]
    assert rows(path, "SELECT point_order, lat, lon FROM search_sector_point ORDER BY point_order") == [
        (order, lat, lon) for order, (lat, lon) in enumerate(FIVE_CORNERS, start=1)
    ]
    # The rest of the sector is as it was.
    assert rows(path, "SELECT name, status, created_time FROM search_sector") == [("S1", "drawn", "2026-11-20T16:00:00Z")]


def test_a_shape_with_fewer_corners_leaves_none_of_the_old_ones(client, bear_creek):
    path = bear_creek("active")
    add_sector(path, 1)

    client.put("/api/mission/sectors/1/corners", json=corners(*SQUARE[:3]))

    assert rows(path, "SELECT count(*) FROM search_sector_point") == [(3,)]


@pytest.mark.parametrize(("setup", "reason"), [
    (lambda path: assign(path, 1), "S1 has been assigned"),
    (lambda path: assign(path, 1, released=True), "S1 has been assigned"),
    (lambda path: write(path, """
        INSERT INTO team (team_id, node_num) VALUES (1, 101);
        INSERT INTO sector_dispatch (search_sector_id, team_id, sent_time) VALUES (1, 1, '2026-11-20T16:30:00Z');
    """), "S1 has been assigned"),
])
def test_a_sector_that_has_been_assigned_keeps_its_shape(client, bear_creek, setup, reason):
    path = bear_creek("active")
    add_sector(path, 1)
    setup(path)

    response = client.put("/api/mission/sectors/1/corners", json=corners(*FIVE_CORNERS))

    assert response.status_code == 409
    assert response.json() == {"detail": f"{reason}, so its shape cannot be changed."}
    assert rows(path, "SELECT count(*) FROM search_sector_point") == [(4,)]


@pytest.mark.parametrize(("status", "reason"), [
    ("completed", "S1 is completed"),
    ("partial", "S1 has been searched"),     # carried from an earlier session, where it was assigned
    ("searching", "S1 has been searched"),
])
def test_a_sector_that_has_been_searched_keeps_its_shape(client, bear_creek, status, reason):
    path = bear_creek("active")
    add_sector(path, 1, status=status)

    response = client.put("/api/mission/sectors/1/corners", json=corners(*FIVE_CORNERS))

    assert response.status_code == 409
    assert response.json() == {"detail": f"{reason}, so its shape cannot be changed."}


def test_a_new_shape_must_follow_the_shape_rules(client, bear_creek):
    path = bear_creek("active")
    add_sector(path, 1)
    bow_tie = [(40.0, -105.6), (40.05, -105.55), (40.05, -105.6), (40.0, -105.55)]
    outside = [*SQUARE[:3], (40.0, -105.49)]

    assert client.put("/api/mission/sectors/1/corners", json=corners(*bow_tie)).status_code == 422
    assert client.put("/api/mission/sectors/1/corners", json=corners(*outside)).status_code == 409
    assert rows(path, "SELECT count(*) FROM search_sector_point") == [(4,)]


def test_a_sector_that_does_not_exist_is_not_found(client, bear_creek):
    bear_creek("active")

    response = client.put("/api/mission/sectors/9/corners", json=corners(*SQUARE))

    assert response.status_code == 404
    assert response.json() == {"detail": "There is no sector S9."}


def test_a_paused_session_refuses_a_new_shape(client, bear_creek):
    path = bear_creek("paused")
    add_sector(path, 1)

    response = client.put("/api/mission/sectors/1/corners", json=corners(*FIVE_CORNERS))

    assert response.status_code == 409
    assert rows(path, "SELECT count(*) FROM search_sector_point") == [(4,)]
