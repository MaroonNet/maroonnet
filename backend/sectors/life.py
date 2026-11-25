"""The rest of a sector's life, after it is drawn.

    drawn --assign--> assigned --a team enters--> searching --complete--> completed
                         |                            |
                      release                      release
                         v                            v
                       drawn                       partial --assign--> assigned ...

Which group holds a sector is a row of sector_assignment that is still going. "Assigned" is
not a saved status: it is a drawn or partial sector with such a row. Nothing here saves;
the route that calls it saves everything together.
"""

from datetime import datetime

from fastapi import HTTPException
from sqlmodel import Session, select

from mission.lifecycle import mission_row
from missiondb.models import MissionStatus, SearchSector, SectorAssignment, SectorEntry, SectorStatus
from missiondb.sqltypes import utcnow
from teams import teams


def open_hold(db: Session, sector_id: int) -> SectorAssignment | None:
    """The row saying which group holds this sector now, or None."""
    return db.exec(select(SectorAssignment).where(
        SectorAssignment.search_sector_id == sector_id, SectorAssignment.to_time.is_(None))).first()


def assign(db: Session, sector: SearchSector, group_id: int) -> None:
    """Gives a sector no group holds to a group that has teams. A group holds one sector at
    a time, so the one it held is released first. Nothing is sent to a radio."""
    if sector.status == SectorStatus.COMPLETED:
        raise HTTPException(409, f"{sector.name} is completed, so it cannot be assigned.")
    held = open_hold(db, sector.search_sector_id)
    if held:
        raise HTTPException(409, f"Group {held.search_group_id} holds {sector.name}. Release it first.")
    teams.find_group(db, group_id)
    if not teams.group_facts(db, group_id, None).radio_ids:
        raise HTTPException(409, f"Group {group_id} has no teams, so it cannot be given a sector.")

    now = utcnow()
    busy_with = db.exec(select(SectorAssignment).where(
        SectorAssignment.search_group_id == group_id, SectorAssignment.to_time.is_(None))).first()
    if busy_with:
        end_hold(db, busy_with, now)
        db.flush()  # the old row is closed before the new one opens: a group has one open row
    db.add(SectorAssignment(search_sector_id=sector.search_sector_id, search_group_id=group_id, from_time=now))


def release(db: Session, sector: SearchSector) -> None:
    """Takes the group off a sector, with no new sector for the group."""
    end_hold(db, held_or_refuse(db, sector), utcnow())


def end_hold(db: Session, hold: SectorAssignment, now: datetime) -> None:
    """Ends a group's hold. A sector being searched is left partial; one nobody entered
    keeps the status it had, drawn or partial."""
    hold.to_time = now
    sector = db.get(SearchSector, hold.search_sector_id)
    if sector.status == SectorStatus.SEARCHING:
        sector.status = SectorStatus.PARTIAL


def mark_entered(db: Session, sector: SearchSector, radio_id: int) -> None:
    """The commander says this team has entered the sector its group holds. Temporary: it
    stands in for the radio's position until radios report."""
    if mission_row(db).status != MissionStatus.ACTIVE:
        raise HTTPException(409, "The mission has not started, so no team has entered a sector.")
    hold = held_or_refuse(db, sector)
    radio = teams.find_radio(db, radio_id)
    if teams.group_of(db, radio_id, None) != hold.search_group_id:
        raise HTTPException(409, f"{teams.label(radio)} is not in Group {hold.search_group_id}, which holds {sector.name}.")
    team_entered(db, radio_id, sector, utcnow())


def team_entered(db: Session, radio_id: int, sector: SearchSector, at: datetime) -> None:
    """Records that a radio is inside a sector. The Mark entered button and, later, a
    radio's position both come through here. missiondb keeps a team's first entry only. If
    the radio's group holds the sector, the sector is being searched."""
    if db.get(SectorEntry, (radio_id, sector.search_sector_id)) is None:
        db.add(SectorEntry(team_id=radio_id, search_sector_id=sector.search_sector_id, entered_time=at))
    hold = open_hold(db, sector.search_sector_id)
    waiting = sector.status in (SectorStatus.DRAWN, SectorStatus.PARTIAL)
    if hold and waiting and teams.group_of(db, radio_id, None) == hold.search_group_id:
        sector.status = SectorStatus.SEARCHING


def complete(db: Session, sector: SearchSector) -> None:
    """Marks a sector a group holds as completed, and ends the group's hold at the same
    time, so the record says which group completed it. A completed sector is final."""
    if mission_row(db).status != MissionStatus.ACTIVE:
        raise HTTPException(409, "The mission has not started, so a sector cannot be completed.")
    hold = held_or_refuse(db, sector, " Assign it first.")
    now = utcnow()
    hold.to_time = now
    sector.status = SectorStatus.COMPLETED
    sector.completed_time = now


def held_or_refuse(db: Session, sector: SearchSector, advice: str = "") -> SectorAssignment:
    if sector.status == SectorStatus.COMPLETED:
        raise HTTPException(409, f"{sector.name} is completed.")
    hold = open_hold(db, sector.search_sector_id)
    if hold is None:
        raise HTTPException(409, f"No group holds {sector.name}.{advice}")
    return hold
