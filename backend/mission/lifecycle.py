"""Moving the open session from one status to the next.

    planning --Start Mission--> active --End Session--> paused --End Mission--> ended

The database checks that the status and the two times agree (planning has no start time;
paused and ended have an end time), so each change sets them together in one save.
"""

from datetime import datetime

from fastapi import HTTPException
from sqlmodel import Session, select

from missiondb.models import (
    Mission, MissionStatus, SearcherCheckin, SearcherTeamAssignment, TeamGroupAssignment,
)
from missiondb.sqltypes import utcnow

# The tables that hold a row for each stretch of time, with an empty end time while the
# stretch is still going: who carries which radio, which radio is in which group, and who is
# checked in. With each: the name of its end time, and whose row it is. Ending a session
# closes the rows still going, and resuming it opens them again.
STRETCH_TABLES = (
    (SearcherTeamAssignment, "to_time", "searcher_id"),
    (TeamGroupAssignment, "to_time", "team_id"),
    (SearcherCheckin, "out_time", "searcher_id"),
)


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


def end_session(db: Session, ending: MissionStatus = MissionStatus.PAUSED) -> None:
    """Ends the active session now: paused when the mission goes on in a next session,
    ended when End Mission was pressed. Every stretch still going is closed at the same time."""
    mission = mission_row(db)
    if mission.status != MissionStatus.ACTIVE:
        raise HTTPException(409, "Only an active session can be ended.")
    now = utcnow()
    close_stretches(db, now)
    mission.status = ending
    mission.end_time = now
    db.commit()


def end_mission(db: Session) -> None:
    """Ends the mission. An active session is ended first; a paused one keeps the end time
    it has."""
    mission = mission_row(db)
    if mission.status == MissionStatus.PLANNING:
        raise HTTPException(409, "A mission in planning has not started, so it cannot be ended.")
    if mission.status == MissionStatus.ENDED:
        raise HTTPException(409, "The mission has already ended.")
    if mission.status == MissionStatus.ACTIVE:
        end_session(db, MissionStatus.ENDED)
        return
    mission.status = MissionStatus.ENDED
    db.commit()


def resume_session(db: Session) -> None:
    """Undoes End Session: the session is active again with no end time, and the stretches
    that ended at exactly the session's end time, which are the ones its ending closed, are
    going again."""
    mission = mission_row(db)
    if mission.status != MissionStatus.PAUSED:
        raise HTTPException(409, "Only a paused session can be resumed.")
    open_stretches(db, mission.end_time)
    mission.status = MissionStatus.ACTIVE
    mission.end_time = None
    db.commit()


def reopen_mission(db: Session) -> None:
    """Undoes End Mission: the mission is paused, and keeps its end time."""
    mission = mission_row(db)
    if mission.status != MissionStatus.ENDED:
        raise HTTPException(409, "Only an ended mission can be reopened.")
    mission.status = MissionStatus.PAUSED
    db.commit()


def close_stretches(db: Session, now: datetime) -> None:
    for table, end, _ in STRETCH_TABLES:
        for row in db.exec(select(table).where(getattr(table, end).is_(None))):
            setattr(row, end, now)


def open_stretches(db: Session, ended_at: datetime) -> None:
    for table, end, owner in STRETCH_TABLES:
        # Newest first. A person or radio has one stretch going at a time, so if two of
        # theirs ended in the same second, only the newer is opened.
        newest_first = select(table).where(getattr(table, end) == ended_at).order_by(table.__table__.primary_key.columns[0].desc())
        opened = set()
        for row in db.exec(newest_first):
            if getattr(row, owner) not in opened:
                opened.add(getattr(row, owner))
                setattr(row, end, None)
