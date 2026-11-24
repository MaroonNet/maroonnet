"""A session that is still active when the backend starts: the web app is told to ask
whether to continue it or end it."""

import pytest

from mission.open_mission import close_mission

from .conftest import BEAR_CREEK_ID


def restart(client):
    close_mission(forget=False)
    with client:  # entering the client runs the app's start-up code
        pass


def asks(client) -> bool:
    return client.get("/api/mission").json()["asks_to_continue"]


def test_a_session_still_active_when_the_backend_starts_asks_until_it_is_answered(client, open_bear_creek):
    open_bear_creek("active")
    assert asks(client) is False  # opened by hand: nothing to ask

    restart(client)

    assert asks(client) is True
    assert asks(client) is True  # reading it again, as a reloaded page does, does not answer it


def test_continue_answers_it_and_the_session_stays_active(client, open_bear_creek):
    open_bear_creek("active")
    restart(client)

    response = client.post("/api/mission/continue")

    assert response.status_code == 200
    assert (response.json()["status"], response.json()["asks_to_continue"]) == ("active", False)
    assert asks(client) is False


def test_end_session_answers_it_too(client, open_bear_creek):
    open_bear_creek("active")
    restart(client)

    response = client.post("/api/mission/end-session")

    assert (response.json()["status"], response.json()["asks_to_continue"]) == ("paused", False)


@pytest.mark.parametrize("status", ["planning", "paused", "ended"])
def test_a_session_that_is_not_active_when_the_backend_starts_asks_nothing(client, open_bear_creek, status):
    open_bear_creek(status)

    restart(client)

    assert client.get("/api/mission").json()["status"] == status
    assert asks(client) is False


def test_opening_the_mission_again_by_hand_asks_nothing(client, open_bear_creek):
    open_bear_creek("active")
    restart(client)

    client.post(f"/api/missions/{BEAR_CREEK_ID}/open")

    assert asks(client) is False


def test_with_no_mission_open_continue_says_so(client):
    response = client.post("/api/mission/continue")

    assert response.status_code == 409
    assert response.json() == {"detail": "No mission is open."}
