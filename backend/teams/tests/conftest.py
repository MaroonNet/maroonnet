"""The team tests use the mission tests' made-up mission files and the people tests' helpers."""

from pathlib import Path

import pytest

from mission.tests.conftest import (  # noqa: F401  (pytest finds these helpers by name)
    arizona07, arizona07_file, client, clock, empty_file, make_mission, open_bear_creek,
)
from people.tests.conftest import check_in, write


@pytest.fixture
def bear_creek(client, open_bear_creek) -> Path:
    """Bear Creek, open and in planning, with four radios and four people checked in.
    Radios 1, 2 and 3 are searcher radios and radio 4 is the command post's. Ana Ruiz is
    person 1, Ben Cho 2, Cy Dunn 3 and Di Ezra 4. Nobody carries a radio yet."""
    path = open_bear_creek()
    write(path, """
        INSERT INTO team (team_id, node_num, kind) VALUES
            (1, 101, 'searcher'), (2, 102, 'searcher'), (3, 103, 'searcher'), (4, 104, 'command_post');
    """)
    for first, last in (("Ana", "Ruiz"), ("Ben", "Cho"), ("Cy", "Dunn"), ("Di", "Ezra")):
        check_in(client, first, last)
    return path


def make_team(client, radio_id: int, searcher_ids: list[int], group_id: int | None = None) -> dict:
    response = client.post("/api/mission/teams", json={
        "radio_id": radio_id, "searcher_ids": searcher_ids, "group_id": group_id})
    assert response.status_code == 201, response.text
    return response.json()


def change_team(client, radio_id: int, searcher_ids: list[int], group_id: int | None = None):
    return client.put(f"/api/mission/teams/{radio_id}", json={"searcher_ids": searcher_ids, "group_id": group_id})


def make_group(client, radio_ids: list[int]) -> dict:
    response = client.post("/api/mission/groups", json={"radio_ids": radio_ids})
    assert response.status_code == 201, response.text
    return response.json()


def radios(client) -> dict[int, dict]:
    """The open mission's radios, by id."""
    return {radio["id"]: radio for radio in client.get("/api/mission/radios").json()}


def groups(client) -> dict[int, list[int]]:
    """The radios of each group of the open mission, by the group's id."""
    return {group["id"]: group["radio_ids"] for group in client.get("/api/mission/groups").json()}


def names(radio: dict) -> list[str]:
    return [person["name"] for person in radio["people"]]
