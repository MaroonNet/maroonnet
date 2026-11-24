"""The web routes for missions and sessions.

    GET  /api/missions             every mission in the missions folder
    POST /api/missions             create one, in planning, and open it
    POST /api/missions/{id}/open   open one; every later request reads it
    GET  /api/mission              the open mission, or nothing
    PATCH /api/mission             change its time zone
    POST /api/mission/close        leave no mission open
    POST /api/mission/continue     the answer "Continue" for a session found still active
    POST /api/mission/start        Start Mission: planning to active
    POST /api/mission/end-session  End Session: active to paused
    POST /api/mission/end          End Mission: active or paused to ended
    POST /api/mission/resume       undo End Session: paused to active
    POST /api/mission/reopen       undo End Mission: ended to paused
    POST /api/mission/next-session start the session after a paused one, in a new file

Each route that changes the open mission answers with its facts as they now are.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlmodel import Session

from . import lifecycle
from .create import create_mission
from .files import MissionFacts, list_missions
from .next_session import start_next_session
from .open_mission import (
    OpenMission, OpenMissionFacts, answer_continue, close_mission, mission_session, open_folder,
    open_mission, open_mission_facts, require_open_mission,
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


class MissionChange(BaseModel):
    """What a request may change about the open mission: its time zone."""

    model_config = ConfigDict(extra="forbid")  # any other name is refused, not ignored
    time_zone: TimeZoneName


@router.patch("/mission")
def patch_mission(change: MissionChange, db: Session = Depends(mission_session)) -> OpenMissionFacts:
    lifecycle.change_time_zone(db, change.time_zone)
    return open_mission_facts()


@router.post("/mission/close", status_code=204)
def post_close() -> None:
    close_mission()


@router.post("/mission/continue")
def post_continue() -> OpenMissionFacts:
    answer_continue()
    return open_mission_facts()


@router.post("/mission/start")
def post_start(db: Session = Depends(mission_session)) -> OpenMissionFacts:
    lifecycle.start_mission(db)
    return open_mission_facts()


@router.post("/mission/end-session")
def post_end_session(db: Session = Depends(mission_session)) -> OpenMissionFacts:
    lifecycle.end_session(db)
    return open_mission_facts()


@router.post("/mission/end")
def post_end(db: Session = Depends(mission_session)) -> OpenMissionFacts:
    lifecycle.end_mission(db)
    return open_mission_facts()


@router.post("/mission/resume")
def post_resume(db: Session = Depends(mission_session)) -> OpenMissionFacts:
    lifecycle.resume_session(db)
    return open_mission_facts()


@router.post("/mission/reopen")
def post_reopen(db: Session = Depends(mission_session)) -> OpenMissionFacts:
    lifecycle.reopen_mission(db)
    return open_mission_facts()


class NextSession(BaseModel):
    keep_teams: bool  # true: keep teams as they ended; false: start with no teams


@router.post("/mission/next-session", status_code=201)
def post_next_session(choice: NextSession, last: OpenMission = Depends(require_open_mission)) -> OpenMissionFacts:
    start_next_session(last, choice.keep_teams)
    open_folder(last.folder)  # the new session is now the mission's latest, so it is the one opened
    return open_mission_facts()
