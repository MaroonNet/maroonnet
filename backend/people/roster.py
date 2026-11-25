"""The roster: everyone the team knows, kept between missions.

It is a small database of its own, roster.sqlite3 in the app data folder, with one table.
A mission file holds only the names of the people checked in to it; the roster is where a
phone number and a middle initial are kept. The two are tied by first and last name.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

from fastapi import HTTPException
from pydantic import BaseModel, BeforeValidator, StringConstraints

from maps.folders import app_data_folder

FILE_NAME = "roster.sqlite3"

# AUTOINCREMENT: an id is never given out twice, even after its person is deleted.
TABLE = """
    CREATE TABLE IF NOT EXISTS person (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name     TEXT NOT NULL,
        middle_initial TEXT,
        last_name      TEXT NOT NULL,
        phone          TEXT
    )
"""


def empty_to_none(value):
    """A box left empty, or holding only spaces, counts as not filled in."""
    return None if isinstance(value, str) and not value.strip() else value


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
# One letter, saved as a capital.
Initial = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z]$")]
# Kept as typed, with the spaces around it dropped.
Phone = Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)]


class PersonDetails(BaseModel):
    """What is typed in for a roster person."""

    first_name: Name
    middle_initial: Annotated[Initial | None, BeforeValidator(empty_to_none)] = None
    last_name: Name
    phone: Annotated[Phone | None, BeforeValidator(empty_to_none)] = None


class RosterPerson(PersonDetails):
    id: int


def full_name(person: PersonDetails) -> str:
    """ "Corey B. Greene", or "Corey Greene" with no initial."""
    initial = f" {person.middle_initial}." if person.middle_initial else ""
    return f"{person.first_name}{initial} {person.last_name}"


def roster_path() -> Path:
    return app_data_folder() / FILE_NAME


@contextmanager
def roster() -> Iterator[sqlite3.Connection]:
    """A connection to the roster file. The file and its table are made the first time.
    What was changed is saved when the block ends, or undone if it fails part way."""
    path = roster_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row  # a row's values can be read by column name
    try:
        with connection:
            connection.execute(TABLE)
            yield connection
    finally:
        connection.close()


def list_people() -> list[RosterPerson]:
    """Everyone in the roster, by last name, then first name."""
    with roster() as db:
        rows = db.execute("SELECT * FROM person ORDER BY last_name COLLATE NOCASE, first_name COLLATE NOCASE, id")
        return [RosterPerson(**row) for row in rows]


def get_person(person_id: int) -> RosterPerson:
    with roster() as db:
        return find(db, person_id)


def add_person(details: PersonDetails) -> RosterPerson:
    with roster() as db:
        refuse_same_name(db, details)
        added = db.execute(
            "INSERT INTO person (first_name, middle_initial, last_name, phone) VALUES (?, ?, ?, ?)",
            (details.first_name, details.middle_initial, details.last_name, details.phone),
        )
        return RosterPerson(id=added.lastrowid, **details.model_dump())


def change_person(person_id: int, details: PersonDetails) -> RosterPerson:
    with roster() as db:
        find(db, person_id)
        refuse_same_name(db, details, but_not=person_id)
        db.execute(
            "UPDATE person SET first_name = ?, middle_initial = ?, last_name = ?, phone = ? WHERE id = ?",
            (details.first_name, details.middle_initial, details.last_name, details.phone, person_id),
        )
        return RosterPerson(id=person_id, **details.model_dump())


def delete_person(person_id: int) -> None:
    with roster() as db:
        find(db, person_id)
        db.execute("DELETE FROM person WHERE id = ?", (person_id,))


def people_named(first_name: str, last_name: str) -> list[RosterPerson]:
    """The roster people with this first and last name, whatever their middle initial.
    This is how a mission's person, saved with no initial, is matched to the roster."""
    with roster() as db:
        rows = db.execute(
            "SELECT * FROM person WHERE first_name = ? COLLATE NOCASE AND last_name = ? COLLATE NOCASE ORDER BY id",
            (first_name, last_name),
        )
        return [RosterPerson(**row) for row in rows]


def find(db: sqlite3.Connection, person_id: int) -> RosterPerson:
    row = db.execute("SELECT * FROM person WHERE id = ?", (person_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "No one in the roster has this id.")
    return RosterPerson(**row)


def refuse_same_name(db: sqlite3.Connection, details: PersonDetails, but_not: int | None = None) -> None:
    """Two roster people cannot have the same first name, middle initial and last name.
    Capital and small letters count as the same. but_not: the person being changed, who
    may keep their own name."""
    same = db.execute(
        """SELECT * FROM person
           WHERE first_name = ? COLLATE NOCASE AND last_name = ? COLLATE NOCASE
             AND ifnull(middle_initial, '') = ? AND id IS NOT ?""",
        (details.first_name, details.last_name, details.middle_initial or "", but_not),
    ).fetchone()
    if same:
        advice = "Use another middle initial" if details.middle_initial else "Add a middle initial"
        # The name is given as the roster has it, not as it was typed.
        raise HTTPException(409, f"{full_name(RosterPerson(**same))} is already in the roster. {advice} to tell them apart.")
