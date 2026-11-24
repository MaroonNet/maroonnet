"""Moving the open session from one status to the next.

    planning --Start Mission--> active --End Session--> paused --End Mission--> ended

The database checks that the status and the two times agree (planning has no start time;
paused and ended have an end time), so each change sets them together in one save.
"""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import or_
from sqlmodel import Session, select

from missiondb.models import (
    Mission, MissionStatus, SearcherCheckin, SearcherTeamAssignment, SearchSector, SectorAssignment,
    SectorEntry, SectorStatus, TeamGroupAssignment,
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
    ended when End Mission was pressed. Every stretch still going is closed at the same time.
    Sectors are left as they are: a group still holds its sector while the session is
    paused, and the next session's file receives a sector being searched as partial."""
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
    it has. Every group is taken off its sector at the session's end time, so a mission
    that is over never shows a sector still being searched."""
    mission = mission_row(db)
    if mission.status == MissionStatus.PLANNING:
        raise HTTPException(409, "A mission in planning has not started, so it cannot be ended.")
    if mission.status == MissionStatus.ENDED:
        raise HTTPException(409, "The mission has already ended.")
    if mission.status == MissionStatus.ACTIVE:
        end_session(db, MissionStatus.ENDED)
    mission.status = MissionStatus.ENDED
    release_sectors(db, mission.end_time)
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
    """Undoes End Mission: the mission is paused and keeps its end time, and each group
    End Mission took off a sector is back on it."""
    mission = mission_row(db)
    if mission.status != MissionStatus.ENDED:
        raise HTTPException(409, "Only an ended mission can be reopened.")
    restore_sectors(db, mission.end_time)
    mission.status = MissionStatus.PAUSED
    db.commit()


def release_sectors(db: Session, at: datetime) -> None:
    """Takes every group off the sector it holds, at this time. A sector being searched
    becomes partial: searched in part, with nobody on it now."""
    for hold in db.exec(select(SectorAssignment).where(SectorAssignment.to_time.is_(None))):
        hold.to_time = at
        sector = db.get(SearchSector, hold.search_sector_id)
        if sector.status == SectorStatus.SEARCHING:
            sector.status = SectorStatus.PARTIAL


def restore_sectors(db: Session, ended_at: datetime) -> None:
    """Puts back each group whose hold on a sector ended at exactly this time, which are
    the holds End Mission ended. A partial sector is searching again if a team of the
    group had entered it during the hold; one held and not yet entered stays partial."""
    newest_first = (
        select(SectorAssignment).where(SectorAssignment.to_time == ended_at)
        .order_by(SectorAssignment.assignment_id.desc())
    )
    sectors_held, groups_holding = set(), set()
    for hold in db.exec(newest_first):
        # A sector has one group and a group one sector. If two holds ended in the same
        # second, only the newer is put back.
        if hold.search_sector_id in sectors_held or hold.search_group_id in groups_holding:
            continue
        sectors_held.add(hold.search_sector_id)
        groups_holding.add(hold.search_group_id)
        hold.to_time = None
        sector = db.get(SearchSector, hold.search_sector_id)
        if sector.status == SectorStatus.PARTIAL and entered_during(db, hold):
            sector.status = SectorStatus.SEARCHING


def entered_during(db: Session, hold: SectorAssignment) -> bool:
    """Whether a radio entered the hold's sector after the hold began, while that radio was
    in the group holding it."""
    in_group = TeamGroupAssignment
    entry = db.exec(
        select(SectorEntry)
        .join(in_group, in_group.team_id == SectorEntry.team_id)
        .where(
            SectorEntry.search_sector_id == hold.search_sector_id,
            SectorEntry.entered_time >= hold.from_time,
            in_group.search_group_id == hold.search_group_id,
            in_group.from_time <= SectorEntry.entered_time,
            or_(in_group.to_time.is_(None), in_group.to_time >= SectorEntry.entered_time),
        )
    ).first()
    return entry is not None


def change_time_zone(db: Session, time_zone: str) -> None:
    """Changes the zone the mission's times are shown in. No saved time changes. The change
    is saved in the open session's file; an earlier session's file keeps the zone it had."""
    mission = mission_row(db)
    if mission.status == MissionStatus.ENDED:
        raise HTTPException(409, "The mission has ended, so its time zone cannot be changed.")
    mission.time_zone = time_zone
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
