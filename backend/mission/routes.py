"""The web routes for missions and sessions.

    GET  /api/missions             every mission in the missions folder
    POST /api/missions             create one, in planning, and open it
    POST /api/missions/{id}/open   open one; every later request reads it
    GET  /api/mission              the open mission, or nothing
    POST /api/mission/close        leave no mission open
    POST /api/mission/start        Start Mission: planning to active

Each route that changes the open mission answers with its facts as they now are.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, StringConstraints
from sqlmodel import Session

from . import lifecycle
from .create import create_mission
from .files import MissionFacts, list_missions
from .open_mission import (
    OpenMissionFacts, close_mission, mission_session, open_folder, open_mission, open_mission_facts,
)
from .time_zone import TimeZoneName

router = APIRouter(prefix="/api")


class NewMission(BaseModel):
    # The spaces around the name are dropped, and what is left is 1 to 60 characters.
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    time_zone: TimeZoneName


@router.get("/missions")
def get_missions() -> list[MissionFacts]:
    return list_missions()


@router.post("/missions", status_code=201)
def post_mission(new: NewMission) -> OpenMissionFacts:
    open_folder(create_mission(new.name, new.time_zone))
    return open_mission_facts()


@router.post("/missions/{mission_id}/open")
def post_open(mission_id: str) -> OpenMissionFacts:
    open_mission(mission_id)
    return open_mission_facts()


@router.get("/mission")
def get_mission() -> OpenMissionFacts | None:
    return open_mission_facts()


@router.post("/mission/close", status_code=204)
def post_close() -> None:
    close_mission()


@router.post("/mission/start")
def post_start(db: Session = Depends(mission_session)) -> OpenMissionFacts:
    lifecycle.start_mission(db)
    return open_mission_facts()
