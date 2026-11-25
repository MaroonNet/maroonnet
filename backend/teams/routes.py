"""The web routes for the radios, teams and groups of the open mission.

    GET  /api/mission/radios        every radio: its kind, who carries it, its group, its newest position
    POST /api/mission/teams         make a team: put people on a radio that has nobody
    PUT  /api/mission/teams/{id}    set a team's people and its group
    GET  /api/mission/groups        every group: its teams and the sector it holds
    POST /api/mission/groups        make a group from teams
    PUT  /api/mission/groups/{id}   set which teams are in a group
    GET  /api/mission/tracks        where each searcher radio has been, cut where it changed group

A team's id is its radio's id. Each route that changes a team answers with its radio as it
now is, and each that changes a group answers with that group.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from mission.open_mission import changeable_session, mission_session

from . import teams, tracks
from .teams import GroupFacts, RadioFacts
from .tracks import Track

router = APIRouter(prefix="/api/mission")


class TeamChange(BaseModel):
    searcher_ids: list[int]
    group_id: int | None  # none: in no group


class NewTeam(TeamChange):
    radio_id: int


class GroupTeams(BaseModel):
    radio_ids: list[int]


@router.get("/radios")
def get_radios(db: Session = Depends(mission_session)) -> list[RadioFacts]:
    return teams.list_radios(db)


@router.post("/teams", status_code=201)
def post_team(new: NewTeam, db: Session = Depends(changeable_session)) -> RadioFacts:
    return teams.make_team(db, new.radio_id, new.searcher_ids, new.group_id)


@router.put("/teams/{radio_id}")
def put_team(radio_id: int, change: TeamChange, db: Session = Depends(changeable_session)) -> RadioFacts:
    return teams.change_team(db, radio_id, change.searcher_ids, change.group_id)


@router.get("/groups")
def get_groups(db: Session = Depends(mission_session)) -> list[GroupFacts]:
    return teams.list_groups(db)


@router.post("/groups", status_code=201)
def post_group(new: GroupTeams, db: Session = Depends(changeable_session)) -> GroupFacts:
    return teams.make_group(db, new.radio_ids)


@router.put("/groups/{group_id}")
def put_group(group_id: int, change: GroupTeams, db: Session = Depends(changeable_session)) -> GroupFacts:
    return teams.change_group(db, group_id, change.radio_ids)


@router.get("/tracks")
def get_tracks(db: Session = Depends(mission_session)) -> list[Track]:
    return tracks.list_tracks(db)
