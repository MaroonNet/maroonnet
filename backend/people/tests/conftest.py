"""The people tests use the mission tests' made-up mission files, with a few helpers of their own."""

import sqlite3
from contextlib import closing
from pathlib import Path

from mission.tests.conftest import (  # noqa: F401  (pytest finds these helpers by name)
    arizona07, arizona07_file, client, clock, empty_file, make_mission, open_bear_creek,
)


def write(path: Path, sql: str) -> None:
    """Writes rows straight into a mission file, for a state no route makes yet."""
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(sql)
        connection.commit()


def add_to_roster(client, first: str, last: str, middle: str | None = None, phone: str | None = None) -> dict:
    response = client.post("/api/roster", json=person(first, last, middle, phone))
    assert response.status_code == 201, response.text
    return response.json()


def check_in(client, first: str, last: str, **more) -> dict:
    """Adds a person to the roster and checks them in to the open mission."""
    roster_person = add_to_roster(client, first, last, **more)
    response = client.post("/api/mission/people/check-in", json={"roster_id": roster_person["id"]})
    assert response.status_code == 201, response.text
    return response.json()


def people(client) -> dict[str, dict]:
    """The open mission's people, by full name."""
    return {f"{p['first_name']} {p['last_name']}": p for p in client.get("/api/mission/people").json()}


def person(first: str, last: str, middle: str | None = None, phone: str | None = None) -> dict:
    """A request body for a roster person."""
    return {"first_name": first, "middle_initial": middle, "last_name": last, "phone": phone}
