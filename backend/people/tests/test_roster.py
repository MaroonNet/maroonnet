"""The roster: the people the team knows, kept between missions in roster.sqlite3."""

from fastapi.testclient import TestClient

from server.main import app

from .conftest import person


def add(client, *args, **kwargs) -> dict:
    response = client.post("/api/roster", json=person(*args, **kwargs))
    assert response.status_code == 201, response.text
    return response.json()


def test_the_roster_starts_empty(client):
    assert client.get("/api/roster").json() == []


def test_a_person_is_added_with_a_name_and_a_phone(client):
    added = add(client, "Corey", "Greene", middle="b", phone=" (970) 555-0142 ")
    assert added == {"id": 1, "first_name": "Corey", "middle_initial": "B", "last_name": "Greene",
                     "phone": "(970) 555-0142"}
    assert client.get("/api/roster").json() == [added]


def test_the_initial_and_the_phone_may_be_left_out(client):
    added = add(client, " Ana ", "Ruiz", middle="", phone="  ")
    assert added == {"id": 1, "first_name": "Ana", "middle_initial": None, "last_name": "Ruiz", "phone": None}


def test_the_roster_file_is_in_the_app_data_folder(client, data_dir):
    add(client, "Ana", "Ruiz")
    assert (data_dir / "roster.sqlite3").is_file()


def test_the_roster_is_the_same_after_the_backend_restarts(client):
    added = add(client, "Ana", "Ruiz")
    assert TestClient(app).get("/api/roster").json() == [added]


def test_the_list_is_in_order_of_last_name_then_first(client):
    add(client, "Cy", "Dunn")
    add(client, "Ben", "Cho")
    add(client, "Abe", "Dunn")
    assert [p["first_name"] for p in client.get("/api/roster").json()] == ["Ben", "Abe", "Cy"]


def test_a_name_is_needed(client):
    assert client.post("/api/roster", json=person(" ", "Ruiz")).status_code == 422
    assert client.post("/api/roster", json=person("Ana", "")).status_code == 422


def test_the_initial_is_one_letter(client):
    assert client.post("/api/roster", json=person("Ana", "Ruiz", middle="BC")).status_code == 422
    assert client.post("/api/roster", json=person("Ana", "Ruiz", middle="7")).status_code == 422


def test_the_same_name_twice_is_refused(client):
    add(client, "Corey", "Greene")
    response = client.post("/api/roster", json=person("corey", "GREENE"))
    assert response.status_code == 409
    assert response.json()["detail"] == "Corey Greene is already in the roster. Add a middle initial to tell them apart."


def test_a_middle_initial_tells_two_people_apart(client):
    add(client, "Corey", "Greene")
    add(client, "Corey", "Greene", middle="B")
    response = client.post("/api/roster", json=person("Corey", "Greene", middle="b"))
    assert response.status_code == 409
    assert response.json()["detail"] == "Corey B. Greene is already in the roster. Use another middle initial to tell them apart."


def test_a_person_is_changed(client):
    ana = add(client, "Ana", "Ruiz")
    response = client.put(f"/api/roster/{ana['id']}", json=person("Anna", "Ruiz", middle="M", phone="555-0100"))
    assert response.status_code == 200
    changed = {"id": ana["id"], "first_name": "Anna", "middle_initial": "M", "last_name": "Ruiz", "phone": "555-0100"}
    assert response.json() == changed
    assert client.get("/api/roster").json() == [changed]


def test_a_person_keeps_their_own_name_when_only_the_phone_changes(client):
    ana = add(client, "Ana", "Ruiz")
    response = client.put(f"/api/roster/{ana['id']}", json=person("Ana", "Ruiz", phone="555-0100"))
    assert response.status_code == 200


def test_a_change_to_another_persons_name_is_refused(client):
    add(client, "Ana", "Ruiz")
    ben = add(client, "Ben", "Cho")
    response = client.put(f"/api/roster/{ben['id']}", json=person("Ana", "Ruiz"))
    assert response.status_code == 409


def test_a_person_is_deleted(client):
    ana = add(client, "Ana", "Ruiz")
    assert client.delete(f"/api/roster/{ana['id']}").status_code == 204
    assert client.get("/api/roster").json() == []


def test_a_deleted_persons_id_is_never_used_again(client):
    add(client, "Ana", "Ruiz")
    ben = add(client, "Ben", "Cho")
    client.delete(f"/api/roster/{ben['id']}")
    assert add(client, "Cy", "Dunn")["id"] == ben["id"] + 1


def test_a_person_who_is_not_in_the_roster(client):
    assert client.put("/api/roster/9", json=person("Ana", "Ruiz")).status_code == 404
    response = client.delete("/api/roster/9")
    assert response.status_code == 404
    assert response.json()["detail"] == "No one in the roster has this id."
