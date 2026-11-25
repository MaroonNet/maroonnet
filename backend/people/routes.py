"""The web routes for the people in the open mission.

    GET  /api/mission/people                  everyone in the open mission
    POST /api/mission/people/check-in         check a roster person in
    POST /api/mission/people/{id}/check-in    check in a person the mission already holds
    POST /api/mission/people/{id}/check-out   check a person out, and take them off their radio

Each route that changes a person answers with that person as they now are.
"""

from fastapi import APIRouter, Depends
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
