"""What changing the roster does to the open mission. The two are tied by name only."""

from mission.tests.conftest import rows

from .conftest import add_to_roster, check_in, people, person, write


def test_a_checked_in_person_cannot_be_deleted_from_the_roster(client, open_bear_creek):
    open_bear_creek()
    ana = check_in(client, "Ana", "Ruiz")
    response = client.delete("/api/roster/1")
    assert response.status_code == 409
    assert response.json()["detail"] == "Ana Ruiz is checked in to this mission. Check them out first."

    client.post(f"/api/mission/people/{ana['id']}/check-out")
    assert client.delete("/api/roster/1").status_code == 204
    # The mission keeps its row and its history.
    kept = people(client)["Ana Ruiz"]
    assert kept["in_roster"] is False and len(kept["history"]) == 2


def test_a_roster_person_is_deleted_freely_with_no_mission_open(client):
    add_to_roster(client, "Ana", "Ruiz")
    assert client.delete("/api/roster/1").status_code == 204


def test_renaming_a_roster_person_renames_their_mission_row(client, open_bear_creek):
    path = open_bear_creek()
    check_in(client, "Ana", "Ruiz", phone="555-0100")
    response = client.put("/api/roster/1", json=person("Anna", "Ruiz", phone="555-0100"))
    assert response.status_code == 200
    assert rows(path, "SELECT fname, lname FROM searcher") == [("Anna", "Ruiz")]
    assert people(client)["Anna Ruiz"]["phone"] == "555-0100"


def test_the_row_follows_whether_or_not_the_person_is_checked_in(client, open_bear_creek):
    path = open_bear_creek()
    write(path, "INSERT INTO searcher (searcher_id, fname, lname) VALUES (1, 'Ana', 'Ruiz');")
    add_to_roster(client, "Ana", "Ruiz")
    client.put("/api/roster/1", json=person("Anna", "Ruiz"))
    assert rows(path, "SELECT fname FROM searcher") == [("Anna",)]


def test_changing_only_the_phone_or_the_initial_leaves_the_mission_alone(client, open_bear_creek):
    path = open_bear_creek()
    check_in(client, "Ana", "Ruiz")
    client.put("/api/roster/1", json=person("Ana", "Ruiz", middle="M", phone="555-0100"))
    assert rows(path, "SELECT fname, lname FROM searcher") == [("Ana", "Ruiz")]
    assert people(client)["Ana Ruiz"]["phone"] == "555-0100"


def test_a_paused_session_is_not_renamed(client, open_bear_creek):
    path = open_bear_creek("paused")
    write(path, "INSERT INTO searcher (searcher_id, fname, lname) VALUES (1, 'Ana', 'Ruiz');")
    add_to_roster(client, "Ana", "Ruiz")
    assert client.put("/api/roster/1", json=person("Anna", "Ruiz")).status_code == 200
    assert rows(path, "SELECT fname FROM searcher") == [("Ana",)]


def test_with_two_people_of_the_old_name_only_the_roster_is_renamed(client, open_bear_creek):
    path = open_bear_creek()
    check_in(client, "Corey", "Greene")
    check_in(client, "Corey", "Greene", middle="B")
    assert client.put("/api/roster/2", json=person("Cory", "Greene", middle="B")).status_code == 200
    assert rows(path, "SELECT fname FROM searcher") == [("Corey",), ("Corey",)]
