"""Groups: sets of teams, made and changed by ticking teams."""

from mission.tests.conftest import add_sectors, add_teams, rows, utc

from .conftest import groups, make_group, make_team, radios

NOW_TEXT = "2026-11-20T23:30:00Z"
LATER = utc(2026, 11, 20, 23, 45)
LATER_TEXT = "2026-11-20T23:45:00Z"


def change_group(client, group_id: int, radio_ids: list[int]):
    return client.put(f"/api/mission/groups/{group_id}", json={"radio_ids": radio_ids})


def test_a_mission_starts_with_no_groups(client, bear_creek):
    assert client.get("/api/mission/groups").json() == []


def test_a_group_is_made_from_teams(client, bear_creek):
    make_team(client, 1, [1])
    make_team(client, 2, [2])

    group = make_group(client, [1, 2])

    assert group == {"id": 1, "radio_ids": [1, 2], "sector": None}
    assert radios(client)[1]["group_id"] == 1 and radios(client)[2]["group_id"] == 1
    assert rows(bear_creek, "SELECT team_id, search_group_id, from_time, to_time FROM team_group_assignment") == [
        (1, 1, NOW_TEXT, None), (2, 1, NOW_TEXT, None)]


def test_a_new_group_needs_at_least_one_team(client, bear_creek):
    response = client.post("/api/mission/groups", json={"radio_ids": []})

    assert response.status_code == 409
    assert response.json()["detail"] == "A group is made with at least one team."
    assert rows(bear_creek, "SELECT count(*) FROM search_group") == [(0,)]


def test_a_radio_with_nobody_on_it_cannot_be_in_a_group(client, bear_creek):
    make_team(client, 1, [1])

    response = client.post("/api/mission/groups", json={"radio_ids": [1, 2]})

    assert response.status_code == 409
    assert response.json()["detail"] == "Radio 2 has nobody on it, so it cannot be in a group."
    assert rows(bear_creek, "SELECT count(*) FROM search_group") == [(0,)]  # the group was not made


def test_a_new_group_can_take_a_team_from_another_group(client, bear_creek, clock):
    make_team(client, 1, [1])
    make_team(client, 2, [2])
    make_group(client, [1, 2])
    clock.set(LATER)

    make_group(client, [2])

    assert groups(client) == {1: [1], 2: [2]}
    assert rows(bear_creek, "SELECT search_group_id, from_time, to_time FROM team_group_assignment WHERE team_id = 2") == [
        (1, NOW_TEXT, LATER_TEXT), (2, LATER_TEXT, None)]


def test_editing_a_group_sets_which_teams_are_in_it(client, bear_creek, clock):
    for radio_id, searcher_id in ((1, 1), (2, 2), (3, 3)):
        make_team(client, radio_id, [searcher_id])
    make_group(client, [1, 2])
    make_group(client, [3])
    clock.set(LATER)

    group = change_group(client, 1, [2, 3]).json()

    # Radio 1 was unticked and has no group; radio 3 was ticked and left group 2, now empty.
    assert group["radio_ids"] == [2, 3]
    assert groups(client) == {1: [2, 3], 2: []}
    assert radios(client)[1]["group_id"] is None
    assert rows(bear_creek, "SELECT team_id, search_group_id, from_time, to_time FROM team_group_assignment ORDER BY assignment_id") == [
        (1, 1, NOW_TEXT, LATER_TEXT), (2, 1, NOW_TEXT, None), (3, 2, NOW_TEXT, LATER_TEXT), (3, 1, LATER_TEXT, None)]


def test_an_empty_group_can_be_given_teams_again(client, bear_creek):
    make_team(client, 1, [1])
    make_group(client, [1])
    change_group(client, 1, [])
    assert groups(client) == {1: []}

    assert change_group(client, 1, [1]).json()["radio_ids"] == [1]


def test_a_group_that_does_not_exist_is_refused(client, bear_creek):
    response = change_group(client, 9, [])

    assert response.status_code == 404
    assert response.json()["detail"] == "No group in this mission has this id."


def test_a_group_shows_the_sector_it_holds(client, open_bear_creek):
    path = open_bear_creek("active")
    add_teams(path)
    add_sectors(path)

    held = {group["id"]: group["sector"] for group in client.get("/api/mission/groups").json()}

    assert held == {1: {"id": 1, "name": "S1"}, 2: {"id": 2, "name": "S2"}, 3: {"id": 3, "name": "S3"}}
