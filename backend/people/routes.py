"""The web routes for the people in the open mission.

    GET  /api/mission/people                  everyone in the open mission
    POST /api/mission/people/check-in         check a roster person in
    POST /api/mission/people/{id}/check-in    check in a person the mission already holds
    POST /api/mission/people/{id}/check-out   check a person out, and take them off their radio
    POST /api/mission/people/placeholders     add the next "Searcher #n", checked in
    POST /api/mission/people/{id}/replace     give a placeholder's row a roster person's name
    DELETE /api/mission/people/{id}           remove a placeholder that never carried a radio
    POST /api/mission/people/{id}/save-to-roster  add a mission person to the roster

Each route that changes a person answers with that person as they now are.
"""

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlmodel import Session

from mission.open_mission import changeable_session, mission_session

from . import mission_people
from .mission_people import PersonFacts

router = APIRouter(prefix="/api/mission/people")


class FromRoster(BaseModel):
    roster_id: int


@router.get("")
def get_people(db: Session = Depends(mission_session)) -> list[PersonFacts]:
    return mission_people.list_people(db)


@router.post("/check-in", status_code=201)
def post_check_in_from_roster(who: FromRoster, db: Session = Depends(changeable_session)) -> PersonFacts:
    return mission_people.check_in_from_roster(db, who.roster_id)


@router.post("/{searcher_id}/check-in")
def post_check_in(searcher_id: int, db: Session = Depends(changeable_session)) -> PersonFacts:
    return mission_people.check_in(db, searcher_id)


@router.post("/{searcher_id}/check-out")
def post_check_out(searcher_id: int, db: Session = Depends(changeable_session)) -> PersonFacts:
    return mission_people.check_out(db, searcher_id)


@router.post("/placeholders", status_code=201)
def post_placeholder(db: Session = Depends(changeable_session)) -> PersonFacts:
    return mission_people.add_placeholder(db)


@router.post("/{searcher_id}/replace")
def post_replace(searcher_id: int, who: FromRoster, db: Session = Depends(changeable_session)) -> PersonFacts:
    return mission_people.replace_placeholder(db, searcher_id, who.roster_id)


@router.delete("/{searcher_id}", status_code=204)
def delete_placeholder(searcher_id: int, db: Session = Depends(changeable_session)) -> Response:
    mission_people.remove_placeholder(db, searcher_id)
    return Response(status_code=204)


# This changes the roster and not the mission, so it also works in a paused or ended session.
@router.post("/{searcher_id}/save-to-roster")
def post_save_to_roster(searcher_id: int, db: Session = Depends(mission_session)) -> PersonFacts:
    return mission_people.save_to_roster(db, searcher_id)
