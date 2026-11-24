"""The web routes for missions and sessions.

    GET  /api/missions             every mission in the missions folder
    POST /api/missions/{id}/open   open one; every later request reads it
    GET  /api/mission              the open mission, or nothing
    POST /api/mission/close        leave no mission open
"""

from fastapi import APIRouter

from .files import MissionFacts, list_missions
from .open_mission import OpenMissionFacts, close_mission, open_mission, open_mission_facts

router = APIRouter(prefix="/api")


@router.get("/missions")
def get_missions() -> list[MissionFacts]:
    return list_missions()


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
