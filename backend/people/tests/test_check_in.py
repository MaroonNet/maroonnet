"""Checking people in to the open mission and out of it."""

from mission.tests.conftest import NOW, add_teams, rows, utc

from .conftest import add_to_roster, check_in, people, write

NOW_TEXT = "2026-11-20T23:30:00Z"


def test_a_mission_starts_with_nobody(client, open_bear_creek):
    open_bear_creek()
    assert client.get("/api/mission/people").json() == []


def test_checking_in_copies_the_name_and_saves_the_time(client, open_bear_creek):
    path = open_bear_creek()
    ana = check_in(client, "Ana", "Ruiz", middle="M", phone="555-0100")
    assert ana["first_name"] == "Ana" and ana["last_name"] == "Ruiz"
    assert ana["checked_in"] is True
    assert ana["in_time"] == NOW_TEXT and ana["out_time"] is None
    # The mission file has the first and last name only; the initial stays in the roster.
    assert rows(path, "SELECT fname, lname FROM searcher") == [("Ana", "Ruiz")]
    assert rows(path, "SELECT searcher_id, in_time, out_time FROM searcher_checkin") == [(1, NOW_TEXT, None)]


def test_a_checked_in_person_shows_their_roster_phone(client, open_bear_creek):
    open_bear_creek()
    ana = check_in(client, "Ana", "Ruiz", phone="555-0100")
    assert ana["in_roster"] is True and ana["phone"] == "555-0100"


def test_people_can_be_checked_in_while_planning_and_while_active(client, open_bear_creek):
    open_bear_creek("active")
    assert check_in(client, "Ana", "Ruiz")["checked_in"] is True


def test_a_paused_session_takes_no_check_in(client, open_bear_creek):
    open_bear_creek("paused")
    ana = add_to_roster(client, "Ana", "Ruiz")
    response = client.post("/api/mission/people/check-in", json={"roster_id": ana["id"]})
    assert response.status_code == 409


def test_checking_in_needs_an_open_mission(client):
    ana = add_to_roster(client, "Ana", "Ruiz")
    response = client.post("/api/mission/people/check-in", json={"roster_id": ana["id"]})
    assert response.status_code == 409
    assert response.json()["detail"] == "No mission is open."


def test_the_same_roster_person_cannot_be_checked_in_twice(client, open_bear_creek):
    open_bear_creek()
    check_in(client, "Ana", "Ruiz")
    response = client.post("/api/mission/people/check-in", json={"roster_id": 1})
    assert response.status_code == 409
    assert response.json()["detail"] == "Ana Ruiz is already checked in."


def test_two_roster_people_with_one_name_are_two_rows(client, open_bear_creek):
    path = open_bear_creek()
    check_in(client, "Corey", "Greene", phone="555-0001")
    corey_b = check_in(client, "Corey", "Greene", middle="B", phone="555-0002")
    assert rows(path, "SELECT fname, lname FROM searcher") == [("Corey", "Greene"), ("Corey", "Greene")]
    # The app cannot tell which of the two a row is, so it shows no phone.
    assert corey_b["in_roster"] is True and corey_b["phone"] is None


def test_checking_in_from_the_roster_uses_the_row_a_carried_person_already_has(client, open_bear_creek):
    path = open_bear_creek()
    write(path, "INSERT INTO searcher (searcher_id, fname, lname) VALUES (1, 'Ana', 'Ruiz');")
    ana = check_in(client, "ana", "ruiz")
    assert ana["id"] == 1
    assert rows(path, "SELECT count(*) FROM searcher") == [(1,)]


def test_a_carried_person_is_not_checked_in_until_they_are(client, open_bear_creek):
    path = open_bear_creek()
    write(path, "INSERT INTO searcher (searcher_id, fname, lname) VALUES (1, 'Ana', 'Ruiz');")
    ana = people(client)["Ana Ruiz"]
    assert ana["checked_in"] is False and ana["in_time"] is None and ana["in_roster"] is False

    response = client.post("/api/mission/people/1/check-in")
    assert response.status_code == 200
    assert response.json()["checked_in"] is True
    assert response.json()["in_time"] == NOW_TEXT


def test_checking_out_saves_the_time(client, open_bear_creek, clock):
    path = open_bear_creek()
    ana = check_in(client, "Ana", "Ruiz")
    clock.set(utc(2026, 11, 21, 1, 10))
    response = client.post(f"/api/mission/people/{ana['id']}/check-out")
    assert response.status_code == 200
    out = response.json()
    assert out["checked_in"] is False
    assert out["in_time"] == NOW_TEXT and out["out_time"] == "2026-11-21T01:10:00Z"
    assert rows(path, "SELECT out_time FROM searcher_checkin") == [("2026-11-21T01:10:00Z",)]


def test_coming_back_is_a_new_check_in(client, open_bear_creek, clock):
    path = open_bear_creek()
    ana = check_in(client, "Ana", "Ruiz")
    clock.set(utc(2026, 11, 21, 1))
    client.post(f"/api/mission/people/{ana['id']}/check-out")
    clock.set(utc(2026, 11, 21, 2))
    back = client.post(f"/api/mission/people/{ana['id']}/check-in").json()
    assert back["checked_in"] is True and back["in_time"] == "2026-11-21T02:00:00Z"
    assert rows(path, "SELECT count(*) FROM searcher_checkin") == [(2,)]
    assert [(event["time"], event["what"]) for event in back["history"]] == [
        (NOW_TEXT, "checked_in"),
        ("2026-11-21T01:00:00Z", "checked_out"),
        ("2026-11-21T02:00:00Z", "checked_in"),
    ]


def test_checking_out_twice_is_refused(client, open_bear_creek):
    open_bear_creek()
    ana = check_in(client, "Ana", "Ruiz")
    client.post(f"/api/mission/people/{ana['id']}/check-out")
    response = client.post(f"/api/mission/people/{ana['id']}/check-out")
    assert response.status_code == 409
    assert response.json()["detail"] == "Ana Ruiz is not checked in."
    response = client.post(f"/api/mission/people/{ana['id']}/check-in")
    assert response.status_code == 200
    response = client.post(f"/api/mission/people/{ana['id']}/check-in")
    assert response.status_code == 409


def test_a_person_who_is_not_in_the_mission(client, open_bear_creek):
    open_bear_creek()
    response = client.post("/api/mission/people/9/check-out")
    assert response.status_code == 404
    assert response.json()["detail"] == "No one in this mission has this id."
    assert client.post("/api/mission/people/check-in", json={"roster_id": 9}).status_code == 404


def test_a_person_shows_their_radio_group_and_who_shares_it(client, open_bear_creek):
    path = open_bear_creek("active")
    add_teams(path)
    everyone = people(client)
    ana = everyone["Ana Ruiz"]
    assert (ana["team_id"], ana["node_num"], ana["group_id"]) == (1, 101, 1)
    assert ana["shares"] == ["Ben Cho"] and ana["last_on_radio"] is False
    cy = everyone["Cy Dunn"]
    assert (cy["team_id"], cy["group_id"]) == (2, None)
    assert cy["shares"] == [] and cy["last_on_radio"] is True


def test_the_history_has_check_ins_and_radio_changes_in_time_order(client, open_bear_creek):
    path = open_bear_creek("active")
    add_teams(path)
    cy = people(client)["Cy Dunn"]
    assert [(event["time"], event["what"], event["team_id"]) for event in cy["history"]] == [
        ("2026-11-20T14:00:00Z", "checked_in", None),
        ("2026-11-20T15:00:00Z", "took_radio", 1),
        ("2026-11-20T16:00:00Z", "left_radio", 1),
        ("2026-11-20T16:00:00Z", "checked_out", None),
        ("2026-11-20T16:00:00Z", "checked_in", None),
        ("2026-11-20T16:00:00Z", "took_radio", 2),
    ]


def test_checking_out_takes_the_person_off_their_radio(client, open_bear_creek):
    path = open_bear_creek("active")
    add_teams(path)
    out = client.post("/api/mission/people/1/check-out").json()
    assert out["team_id"] is None and out["checked_in"] is False
    assert rows(path, "SELECT to_time FROM searcher_team_assignment WHERE searcher_id = 1") == [(NOW_TEXT,)]
    # Ben still carries radio 1, so it stays in its group.
    assert rows(path, "SELECT to_time FROM team_group_assignment WHERE team_id = 1") == [(None,)]
    assert people(client)["Ben Cho"]["last_on_radio"] is True


def test_when_the_last_searcher_checks_out_the_radio_leaves_its_group(client, open_bear_creek):
    path = open_bear_creek("active")
    add_teams(path)
    client.post("/api/mission/people/1/check-out")
    client.post("/api/mission/people/2/check-out")
    assert rows(path, "SELECT to_time FROM team_group_assignment WHERE team_id = 1") == [(NOW_TEXT,)]


def test_an_ended_session_is_read_as_it_stood_at_its_end(client, arizona07):
    client.post("/api/missions/952592f8-f48b-4310-aa51-3abcefc02005/open")
    everyone = people(client)
    assert len(everyone) == 21
    assert all(person["checked_in"] for person in everyone.values())
    marcus = everyone["Marcus Ibarra"]
    assert marcus["in_time"] == "2025-04-14T03:30:28Z" and marcus["out_time"] == "2025-04-14T11:20:00Z"
    assert (marcus["team_id"], marcus["group_id"]) == (1, 1)
    assert marcus["shares"] == ["Tessa Lindqvist", "Owen Whitfield"]
    # Radio 4 left its group at 11:25 pm, long before the end.
    assert (everyone["Diego Alas"]["team_id"], everyone["Diego Alas"]["group_id"]) == (4, None)


def test_in_the_next_session_everyone_is_carried_and_nobody_is_checked_in(client, arizona07):
    client.post("/api/missions/952592f8-f48b-4310-aa51-3abcefc02005/open")
    client.post("/api/mission/reopen")
    assert client.post("/api/mission/next-session", json={"keep_teams": True}).status_code == 201
    everyone = people(client)
    assert len(everyone) == 21
    assert not any(person["checked_in"] for person in everyone.values())
    assert everyone["Marcus Ibarra"]["team_id"] == 1
    assert everyone["Marcus Ibarra"]["in_roster"] is False


def test_the_clock_fixture_is_what_these_tests_think(clock):
    assert NOW == utc(2026, 11, 20, 23, 30)
