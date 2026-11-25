"""Reading the open mission's sectors."""

from mission.tests.conftest import ARIZONA07_ID
from sectors.tests.conftest import add_sector, assign


def test_arizona07_lists_its_seven_sectors_as_they_ended(client, arizona07):
    client.post(f"/api/missions/{ARIZONA07_ID}/open")

    sectors = client.get("/api/mission/sectors").json()

    assert [(s["name"], s["status"]) for s in sectors] == [
        ("S1", "completed"), ("S2", "completed"), ("S3", "completed"), ("S4", "partial"),
        ("S5", "completed"), ("S6", "partial"), ("S7", "drawn"),
    ]
    # At the end of the night no group holds a sector, and only S7 was never assigned.
    assert [s["group_id"] for s in sectors] == [None] * 7
    assert [s["name"] for s in sectors if s["can_edit"]] == ["S7"]


def test_a_sector_comes_with_its_corners_in_order_and_its_times(client, arizona07):
    client.post(f"/api/missions/{ARIZONA07_ID}/open")

    s1 = client.get("/api/mission/sectors").json()[0]

    assert s1["id"] == 1
    assert len(s1["corners"]) == 8
    assert s1["corners"][0] == {"lat": 31.510137, "lon": -110.676217}
    assert s1["corners"][-1] == {"lat": 31.508693, "lon": -110.680063}
    assert s1["created_time"] == "2025-04-14T03:35:00Z"
    assert s1["completed_time"] == "2025-04-14T08:21:45Z"


def test_a_new_mission_has_no_sectors(client, open_bear_creek):
    open_bear_creek("planning")

    assert client.get("/api/mission/sectors").json() == []


def test_the_group_that_holds_a_sector_is_given(client, open_bear_creek):
    path = open_bear_creek("active")
    add_sector(path, 1)
    add_sector(path, 2)
    assign(path, 1)                  # group 1 holds S1
    assign(path, 2, released=True)   # S2 was held and let go

    sectors = client.get("/api/mission/sectors").json()

    assert [(s["name"], s["group_id"], s["can_edit"]) for s in sectors] == [("S1", 1, False), ("S2", None, False)]


def test_with_no_mission_open_the_list_is_refused(client):
    response = client.get("/api/mission/sectors")

    assert response.status_code == 409
    assert response.json() == {"detail": "No mission is open."}
