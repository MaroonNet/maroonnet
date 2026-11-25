"""Placeholders: a stand-in such as "Searcher #1" for someone not known yet. A placeholder
is an ordinary person row, told apart by its name alone."""

from mission.tests.conftest import rows

from .conftest import add_to_roster, check_in, people, write

NOW_TEXT = "2026-11-20T23:30:00Z"


def add_placeholder(client) -> dict:
    response = client.post("/api/mission/people/placeholders")
    assert response.status_code == 201, response.text
    return response.json()


def test_a_placeholder_is_added_checked_in(client, open_bear_creek):
    path = open_bear_creek()
    first = add_placeholder(client)
    assert (first["first_name"], first["last_name"]) == ("Searcher", "#1")
    assert first["placeholder"] is True and first["checked_in"] is True and first["in_time"] == NOW_TEXT
    assert first["in_roster"] is False
    assert rows(path, "SELECT fname, lname FROM searcher") == [("Searcher", "#1")]


def test_placeholders_are_numbered_within_the_mission(client, open_bear_creek):
    open_bear_creek()
    check_in(client, "Ana", "Ruiz")
    add_placeholder(client)
    assert add_placeholder(client)["last_name"] == "#2"
    assert people(client)["Ana Ruiz"]["placeholder"] is False


def test_a_placeholder_is_never_in_the_roster(client, open_bear_creek):
    open_bear_creek()
    searcher = add_placeholder(client)
    assert client.get("/api/roster").json() == []
    response = client.post(f"/api/mission/people/{searcher['id']}/save-to-roster")
    assert response.status_code == 409
    assert response.json()["detail"] == "A placeholder cannot be saved to the roster."


def test_replacing_a_placeholder_rewrites_its_name_and_keeps_its_radio(client, open_bear_creek):
    path = open_bear_creek("active")
    searcher = add_placeholder(client)
    write(path, f"""
        INSERT INTO team (team_id, node_num) VALUES (1, 101);
        INSERT INTO searcher_team_assignment (searcher_id, team_id, from_time) VALUES ({searcher['id']}, 1, '2026-11-20T23:40:00Z');
    """)
    ana = add_to_roster(client, "Ana", "Ruiz", phone="555-0100")
    response = client.post(f"/api/mission/people/{searcher['id']}/replace", json={"roster_id": ana["id"]})
    assert response.status_code == 200
    replaced = response.json()
    assert replaced["id"] == searcher["id"]
    assert (replaced["first_name"], replaced["last_name"]) == ("Ana", "Ruiz")
    assert replaced["placeholder"] is False and replaced["phone"] == "555-0100"
    assert replaced["team_id"] == 1 and replaced["checked_in"] is True
    assert [event["what"] for event in replaced["history"]] == ["checked_in", "took_radio"]
    assert list(people(client)) == ["Ana Ruiz"]


def test_only_a_placeholder_can_be_replaced(client, open_bear_creek):
    open_bear_creek()
    ana = check_in(client, "Ana", "Ruiz")
    ben = add_to_roster(client, "Ben", "Cho")
    response = client.post(f"/api/mission/people/{ana['id']}/replace", json={"roster_id": ben["id"]})
    assert response.status_code == 409
    assert response.json()["detail"] == "Ana Ruiz is not a placeholder."


def test_a_placeholder_is_not_replaced_with_someone_already_in_the_mission(client, open_bear_creek):
    open_bear_creek()
    check_in(client, "Ana", "Ruiz")
    searcher = add_placeholder(client)
    response = client.post(f"/api/mission/people/{searcher['id']}/replace", json={"roster_id": 1})
    assert response.status_code == 409
    assert response.json()["detail"] == "Ana Ruiz is already in this mission."


def test_a_placeholder_that_never_carried_a_radio_can_be_removed(client, open_bear_creek):
    path = open_bear_creek()
    searcher = add_placeholder(client)
    assert searcher["can_remove"] is True
    assert client.delete(f"/api/mission/people/{searcher['id']}").status_code == 204
    assert client.get("/api/mission/people").json() == []
    assert rows(path, "SELECT count(*) FROM searcher_checkin") == [(0,)]


def test_a_placeholder_that_carried_a_radio_cannot_be_removed(client, open_bear_creek):
    path = open_bear_creek("active")
    searcher = add_placeholder(client)
    write(path, f"""
        INSERT INTO team (team_id, node_num) VALUES (1, 101);
        INSERT INTO searcher_team_assignment (searcher_id, team_id, from_time, to_time)
        VALUES ({searcher['id']}, 1, '2026-11-20T23:40:00Z', '2026-11-20T23:50:00Z');
    """)
    assert people(client)["Searcher #1"]["can_remove"] is False
    response = client.delete(f"/api/mission/people/{searcher['id']}")
    assert response.status_code == 409
    assert response.json()["detail"] == "Searcher #1 has carried a radio, so it cannot be removed. Check it out instead."


def test_a_real_person_cannot_be_removed(client, open_bear_creek):
    open_bear_creek()
    ana = check_in(client, "Ana", "Ruiz")
    assert ana["can_remove"] is False
    response = client.delete(f"/api/mission/people/{ana['id']}")
    assert response.status_code == 409
    assert response.json()["detail"] == "Only a placeholder can be removed."


def test_a_mission_person_is_saved_to_the_roster(client, open_bear_creek):
    path = open_bear_creek()
    write(path, "INSERT INTO searcher (searcher_id, fname, lname) VALUES (1, 'Ana', 'Ruiz');")
    response = client.post("/api/mission/people/1/save-to-roster")
    assert response.status_code == 200
    assert response.json()["in_roster"] is True and response.json()["phone"] is None
    assert client.get("/api/roster").json() == [
        {"id": 1, "first_name": "Ana", "middle_initial": None, "last_name": "Ruiz", "phone": None}]
    assert client.post("/api/mission/people/1/save-to-roster").status_code == 409


def test_people_of_an_ended_mission_can_be_saved_to_the_roster(client, arizona07):
    client.post("/api/missions/952592f8-f48b-4310-aa51-3abcefc02005/open")
    assert client.post("/api/mission/people/1/save-to-roster").status_code == 200
    assert client.get("/api/roster").json()[0]["last_name"] == "Ibarra"
