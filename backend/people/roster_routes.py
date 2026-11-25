"""The web routes for the roster.

    GET    /api/roster        everyone in the roster
    POST   /api/roster        add a person
    PUT    /api/roster/{id}   change a person's name, initial or phone
    DELETE /api/roster/{id}   delete a person

The roster is not part of any mission, so these work with no mission open.
"""

from fastapi import APIRouter, Response

from . import roster
from .roster import PersonDetails, RosterPerson

router = APIRouter(prefix="/api/roster")


@router.get("")
def get_roster() -> list[RosterPerson]:
    return roster.list_people()


@router.post("", status_code=201)
def post_person(details: PersonDetails) -> RosterPerson:
    return roster.add_person(details)


@router.put("/{person_id}")
def put_person(person_id: int, details: PersonDetails) -> RosterPerson:
    return roster.change_person(person_id, details)


@router.delete("/{person_id}", status_code=204)
def delete_person(person_id: int) -> Response:
    roster.delete_person(person_id)
    return Response(status_code=204)
