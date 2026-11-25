"""The web route for the Communication Log of the open mission.

    GET  /api/mission/log    its messages, one line for each send, and its sector events

Nothing is written: the app does not send messages yet.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from mission.open_mission import mission_session

from . import log
from .log import Line

router = APIRouter(prefix="/api/mission")


@router.get("/log")
def get_log(db: Session = Depends(mission_session)) -> list[Line]:
    return log.read_log(db)
