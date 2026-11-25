"""The web routes for the roster.

    GET    /api/roster        everyone in the roster
    POST   /api/roster        add a person
    PUT    /api/roster/{id}   change a person's name, initial or phone
    DELETE /api/roster/{id}   delete a person

The roster is not part of any mission, so these work with no mission open. While a mission
is open, two of them look at it too, because a mission person is tied to the roster by name:
a changed name is changed in the open session as well, and a person who is checked in
cannot be deleted.
"""

from fastapi import APIRouter, HTTPException, Response
from sqlmodel import Session

from mission.open_mission import get_open_mission

from . import mission_people, roster
from .roster import PersonDetails, RosterPerson, full_name

router = APIRouter(prefix="/api/roster")


@router.get("")
def get_roster() -> list[RosterPerson]:
    return roster.list_people()


@router.post("", status_code=201)
def post_person(details: PersonDetails) -> RosterPerson:
    return roster.add_person(details)


@router.put("/{person_id}")
def put_person(person_id: int, details: PersonDetails) -> RosterPerson:
    old = roster.get_person(person_id)
    # Counted before the change: with two roster people of the old name, the app cannot
    # tell whose row the mission holds, so the mission is left alone.
    only_one = len(roster.people_named(old.first_name, old.last_name)) == 1
    changed = roster.change_person(person_id, details)
    renamed = (old.first_name, old.last_name) != (changed.first_name, changed.last_name)
    opened = get_open_mission()
    if renamed and only_one and opened:
        with Session(opened.engine) as db:
            mission_people.rename(db, old, changed)
    return changed


@router.delete("/{person_id}", status_code=204)
def delete_person(person_id: int) -> Response:
    person = roster.get_person(person_id)
    opened = get_open_mission()
    if opened:
        with Session(opened.engine) as db:
            if mission_people.checked_in_as(db, person.first_name, person.last_name):
                raise HTTPException(409, f"{full_name(person)} is checked in to this mission. Check them out first.")
    roster.delete_person(person_id)
    return Response(status_code=204)
