"""Moving the open session from one status to the next.

    planning --Start Mission--> active --End Session--> paused --End Mission--> ended

The database checks that the status and the two times agree (planning has no start time;
paused and ended have an end time), so each change sets them together in one save.
"""

from fastapi import HTTPException
from sqlmodel import Session, select

from missiondb.models import Mission, MissionStatus
from missiondb.sqltypes import utcnow


def mission_row(db: Session) -> Mission:
    """The file's one mission row."""
    return db.exec(select(Mission)).one()


def start_mission(db: Session) -> None:
    mission = mission_row(db)
    if mission.status != MissionStatus.PLANNING:
        raise HTTPException(409, "Only a mission in planning can be started.")
    mission.status = MissionStatus.ACTIVE
    mission.start_time = utcnow()
    db.commit()
