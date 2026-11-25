"""Deleting a sector that has never been assigned."""

import pytest

from mission.tests.conftest import ARIZONA07_ID, rows
from sectors.tests.conftest import SQUARE, add_sector, assign, corners, write


def test_a_drawn_sector_is_deleted_with_its_corners(client, bear_creek):
    path = bear_creek("active")
    add_sector(path, 1)
    add_sector(path, 2)

    response = client.delete("/api/mission/sectors/1")

    assert response.status_code == 204
    assert [s["name"] for s in client.get("/api/mission/sectors").json()] == ["S2"]
    assert rows(path, "SELECT DISTINCT search_sector_id FROM search_sector_point") == [(2,)]


def test_a_team_having_walked_through_it_does_not_stop_a_delete(client, bear_creek):
    # A radio's position can fall inside a sector nobody was given, as radio 3's did in
    # Arizona07's S7. The record of it goes with the sector.
    path = bear_creek("active")
    add_sector(path, 1)
    write(path, """
        INSERT INTO team (team_id, node_num) VALUES (1, 101);
        INSERT INTO sector_entry (team_id, search_sector_id, entered_time) VALUES (1, 1, '2026-11-20T16:30:00Z');
    """)

    assert client.delete("/api/mission/sectors/1").status_code == 204
    assert rows(path, "SELECT count(*) FROM sector_entry") == [(0,)]


def test_deleting_the_highest_lets_its_number_be_used_again(client, bear_creek):
    path = bear_creek("active")
    add_sector(path, 1)
    add_sector(path, 2)
    client.delete("/api/mission/sectors/2")

    sector = client.post("/api/mission/sectors", json=corners(*SQUARE)).json()

    assert sector["name"] == "S2"


@pytest.mark.parametrize(("setup", "reason"), [
    (lambda path: assign(path, 1), "S1 has been assigned"),
    (lambda path: assign(path, 1, released=True), "S1 has been assigned"),
    (lambda path: write(path, "UPDATE search_sector SET status = 'partial'"), "S1 has been searched"),
    (lambda path: write(path, "UPDATE search_sector SET status = 'completed', completed_time = '2026-11-20T18:00:00Z'"),
     "S1 is completed"),
])
def test_a_sector_that_has_been_used_cannot_be_deleted(client, bear_creek, setup, reason):
    path = bear_creek("active")
    add_sector(path, 1)
    setup(path)

    response = client.delete("/api/mission/sectors/1")

    assert response.status_code == 409
    assert response.json() == {"detail": f"{reason}, so it cannot be deleted."}
    assert rows(path, "SELECT count(*) FROM search_sector") == [(1,)]


def test_a_sector_that_does_not_exist_is_not_found(client, bear_creek):
    bear_creek("active")

    response = client.delete("/api/mission/sectors/9")

    assert response.status_code == 404
    assert response.json() == {"detail": "There is no sector S9."}


def test_arizona07_ended_keeps_s7(client, arizona07):
    client.post(f"/api/missions/{ARIZONA07_ID}/open")

    response = client.delete("/api/mission/sectors/7")

    assert response.status_code == 409
    assert len(client.get("/api/mission/sectors").json()) == 7
