"""Teams: putting checked-in people on a radio, and changing who is on it."""

from mission.tests.conftest import rows, utc
from people.tests.conftest import people, write

from .conftest import change_team, groups, make_group, make_team, names, radios

NOW_TEXT = "2026-11-20T23:30:00Z"
LATER = utc(2026, 11, 20, 23, 45)
LATER_TEXT = "2026-11-20T23:45:00Z"


def test_every_radio_is_listed_with_nobody_on_it(client, bear_creek):
    assert client.get("/api/mission/radios").json() == [
        {"id": 1, "node_num": 101, "kind": "searcher", "people": [], "group_id": None, "last_position": None},
        {"id": 2, "node_num": 102, "kind": "searcher", "people": [], "group_id": None, "last_position": None},
        {"id": 3, "node_num": 103, "kind": "searcher", "people": [], "group_id": None, "last_position": None},
        {"id": 4, "node_num": 104, "kind": "command_post", "people": [], "group_id": None, "last_position": None},
    ]


def test_making_a_team_puts_its_searchers_on_the_radio(client, bear_creek):
    team = make_team(client, 1, [1, 2])

    assert team["id"] == 1 and team["group_id"] is None
    assert team["people"] == [
        {"id": 1, "name": "Ana Ruiz", "placeholder": False}, {"id": 2, "name": "Ben Cho", "placeholder": False}]
    assert rows(bear_creek, "SELECT searcher_id, team_id, from_time, to_time FROM searcher_team_assignment") == [
        (1, 1, NOW_TEXT, None), (2, 1, NOW_TEXT, None)]
    assert people(client)["Ana Ruiz"]["team_id"] == 1


def test_a_team_can_be_made_in_a_group(client, bear_creek):
    group = make_group(client, [make_team(client, 1, [1])["id"]])

    team = make_team(client, 2, [2], group_id=group["id"])

    assert team["group_id"] == 1
    assert groups(client) == {1: [1, 2]}


def test_a_placeholder_can_be_on_a_team(client, bear_creek):
    placeholder = client.post("/api/mission/people/placeholders").json()

    team = make_team(client, 1, [placeholder["id"]])

    assert team["people"] == [{"id": placeholder["id"], "name": "Searcher #1", "placeholder": True}]


def test_a_new_team_needs_at_least_one_searcher(client, bear_creek):
    response = client.post("/api/mission/teams", json={"radio_id": 1, "searcher_ids": [], "group_id": None})

    assert response.status_code == 409
    assert response.json()["detail"] == "A team needs at least one searcher."


def test_a_radio_that_is_a_team_cannot_be_made_one_again(client, bear_creek):
    make_team(client, 1, [1])

    response = client.post("/api/mission/teams", json={"radio_id": 1, "searcher_ids": [2], "group_id": None})

    assert response.status_code == 409
    assert response.json()["detail"] == "Radio 1 is already a team."


def test_only_a_searcher_radio_can_be_a_team(client, bear_creek):
    response = client.post("/api/mission/teams", json={"radio_id": 4, "searcher_ids": [1], "group_id": None})

    assert response.status_code == 409
    assert response.json()["detail"] == "Radio 4 is not a searcher radio, so it cannot be a team."


def test_a_person_carries_one_radio(client, bear_creek):
    make_team(client, 1, [1])

    response = client.post("/api/mission/teams", json={"radio_id": 2, "searcher_ids": [1], "group_id": None})

    assert response.status_code == 409
    assert response.json()["detail"] == "Ana Ruiz already carries Radio 1."
    assert rows(bear_creek, "SELECT count(*) FROM searcher_team_assignment") == [(1,)]


def test_a_person_who_is_not_checked_in_cannot_be_on_a_team(client, bear_creek):
    client.post("/api/mission/people/1/check-out")

    response = client.post("/api/mission/teams", json={"radio_id": 1, "searcher_ids": [1], "group_id": None})

    assert response.status_code == 409
    assert response.json()["detail"] == "Ana Ruiz is not checked in."


def test_a_radio_a_person_or_a_group_that_does_not_exist_is_refused(client, bear_creek):
    def post(radio_id, searcher_ids, group_id=None):
        return client.post("/api/mission/teams", json={
            "radio_id": radio_id, "searcher_ids": searcher_ids, "group_id": group_id})

    assert post(9, [1]).json()["detail"] == "No radio in this mission has this id."
    assert post(1, [9]).json()["detail"] == "No one in this mission has this id."
    assert post(1, [1], group_id=9).json()["detail"] == "No group in this mission has this id."
    assert rows(bear_creek, "SELECT count(*) FROM searcher_team_assignment") == [(0,)]


def test_a_paused_session_takes_no_team(client, open_bear_creek):
    path = open_bear_creek("paused")
    write(path, "INSERT INTO team (team_id, node_num) VALUES (1, 101);"
                "INSERT INTO searcher (searcher_id, fname, lname) VALUES (1, 'Ana', 'Ruiz');")

    response = client.post("/api/mission/teams", json={"radio_id": 1, "searcher_ids": [1], "group_id": None})

    assert response.status_code == 409


def test_editing_a_team_adds_and_takes_off_searchers(client, bear_creek, clock):
    make_team(client, 1, [1, 2])
    clock.set(LATER)

    team = change_team(client, 1, [2, 3]).json()

    assert names(team) == ["Ben Cho", "Cy Dunn"]
    # Ben's row is untouched; Ana's is closed and Cy's opened at the same moment.
    assert rows(bear_creek, "SELECT searcher_id, from_time, to_time FROM searcher_team_assignment") == [
        (1, NOW_TEXT, LATER_TEXT), (2, NOW_TEXT, None), (3, LATER_TEXT, None)]


def test_a_person_is_moved_by_editing_both_teams_and_their_history_says_so(client, bear_creek, clock):
    make_team(client, 1, [1, 2])
    make_team(client, 2, [3])
    clock.set(LATER)

    change_team(client, 1, [2])
    change_team(client, 2, [3, 1])

    assert names(radios(client)[1]) == ["Ben Cho"]
    assert names(radios(client)[2]) == ["Ana Ruiz", "Cy Dunn"]
    ana = people(client)["Ana Ruiz"]
    assert ana["team_id"] == 2
    assert [(event["what"], event["team_id"]) for event in ana["history"]] == [
        ("checked_in", None), ("took_radio", 1), ("left_radio", 1), ("took_radio", 2)]


def test_editing_a_team_changes_its_group(client, bear_creek, clock):
    make_group(client, [make_team(client, 1, [1])["id"]])
    make_group(client, [make_team(client, 2, [2])["id"]])
    clock.set(LATER)

    team = change_team(client, 1, [1], group_id=2).json()

    assert team["group_id"] == 2
    assert groups(client) == {1: [], 2: [1, 2]}  # the emptied group stays listed
    assert rows(bear_creek, "SELECT search_group_id, from_time, to_time FROM team_group_assignment WHERE team_id = 1") == [
        (1, NOW_TEXT, LATER_TEXT), (2, LATER_TEXT, None)]


def test_editing_a_team_can_take_it_out_of_its_group(client, bear_creek):
    make_group(client, [make_team(client, 1, [1])["id"]])

    assert change_team(client, 1, [1], group_id=None).json()["group_id"] is None


def test_taking_everyone_off_a_radio_takes_it_out_of_its_group(client, bear_creek, clock):
    make_group(client, [make_team(client, 1, [1])["id"]])
    clock.set(LATER)

    radio = change_team(client, 1, [], group_id=1).json()

    assert radio["people"] == [] and radio["group_id"] is None
    assert groups(client) == {1: []}
    assert rows(bear_creek, "SELECT to_time FROM searcher_team_assignment") == [(LATER_TEXT,)]
    assert rows(bear_creek, "SELECT to_time FROM team_group_assignment") == [(LATER_TEXT,)]
    # The radio can be made a team again, and its person put on another.
    assert make_team(client, 2, [1])["people"][0]["name"] == "Ana Ruiz"
    assert make_team(client, 1, [2])["people"][0]["name"] == "Ben Cho"


def test_an_edit_that_changes_nothing_writes_nothing(client, bear_creek, clock):
    make_group(client, [make_team(client, 1, [1, 2])["id"]])
    clock.set(LATER)

    change_team(client, 1, [2, 1], group_id=1)

    assert rows(bear_creek, "SELECT count(*), count(to_time) FROM searcher_team_assignment") == [(2, 0)]
    assert rows(bear_creek, "SELECT count(*), count(to_time) FROM team_group_assignment") == [(1, 0)]


def test_an_edit_is_refused_whole_when_one_person_cannot_join(client, bear_creek):
    make_team(client, 1, [1])
    make_team(client, 2, [2])

    response = change_team(client, 1, [3, 2])

    assert response.status_code == 409
    assert response.json()["detail"] == "Ben Cho already carries Radio 2."
    assert names(radios(client)[1]) == ["Ana Ruiz"]


def test_a_radio_shows_its_newest_position(client, bear_creek):
    write(bear_creek, """
        INSERT INTO location (team_id, time, rx_time, lat, lon, elevation) VALUES
            (1, '2026-11-20T16:00:00Z', '2026-11-20T16:00:01Z', 39.5, -105.5, 2400),
            (1, '2026-11-20T16:05:00Z', '2026-11-20T16:05:01Z', 39.6, -105.6, NULL);
    """)

    assert radios(client)[1]["last_position"] == {
        "time": "2026-11-20T16:05:00Z", "lat": 39.6, "lon": -105.6, "elevation": None}
    assert radios(client)[2]["last_position"] is None


def test_arizona07_reads_as_it_stood_when_it_ended(client, arizona07):
    client.post("/api/missions/952592f8-f48b-4310-aa51-3abcefc02005/open")
    found = radios(client)

    assert [radio["kind"] for radio in found.values()] == [
        "searcher", "searcher", "searcher", "searcher", "searcher", "relay", "searcher", "command_post"]
    assert names(found[1]) == ["Marcus Ibarra", "Tessa Lindqvist", "Owen Whitfield"]
    assert found[1]["group_id"] == 1
    assert found[3]["group_id"] == 3   # it moved from group 1 at 1:24 am
    assert found[4]["group_id"] is None and len(found[4]["people"]) == 4
    assert found[6]["people"] == [] and found[6]["last_position"] is None
    assert names(found[8]) == ["Ellen Brandt"]
    assert found[1]["last_position"]["time"].startswith("2025-04-14T11:")
    assert groups(client) == {1: [1, 2], 2: [7], 3: [3, 5]}
