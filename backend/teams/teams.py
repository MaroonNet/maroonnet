"""The radios, teams and groups of the open mission.

A mission file holds every radio as a row of the team table. A radio is a team while
someone carries it: a row of searcher_team_assignment that is still going. Which group a
radio is in is a row of team_group_assignment. Nothing is ever deleted: a change closes
the row that was going, by giving it an end time, and opens the next one at that same time.
"""

from datetime import datetime

from fastapi import HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from missiondb.models import (
    Location, SearchGroup, SearchSector, SearcherTeamAssignment, SectorAssignment, Team, TeamGroupAssignment,
    TeamKind,
)
from missiondb.sqltypes import utcnow
from people import mission_people
from people.mission_people import carriers, full_name, going, placeholder_number, standing_time


class Carrier(BaseModel):
    """A person carrying a radio."""

    id: int
    name: str
    placeholder: bool  # a stand-in such as "Searcher #1"


class Position(BaseModel):
    time: datetime
    lat: float
    lon: float
    elevation: float | None  # meters


class RadioFacts(BaseModel):
    """A radio of the open mission as the web app reads it. Its id is the number in its
    label: radio 4 is "Radio 4"."""

    id: int
    node_num: int
    kind: TeamKind
    people: list[Carrier]           # who carries it; with nobody, it is not a team
    group_id: int | None
    last_position: Position | None  # its newest position report


class HeldSector(BaseModel):
    id: int
    name: str


class GroupFacts(BaseModel):
    id: int
    radio_ids: list[int]       # its teams; a group with none stays listed
    sector: HeldSector | None  # the sector it holds


def label(radio: Team) -> str:
    return f"Radio {radio.team_id}"


def list_radios(db: Session) -> list[RadioFacts]:
    at = standing_time(db)
    return [radio_facts(db, radio, at) for radio in db.exec(select(Team).order_by(Team.team_id))]


def radio_facts(db: Session, radio: Team, at: datetime | None) -> RadioFacts:
    # The location table's key is (radio, time), so its newest row is found without a search.
    newest = db.exec(select(Location).where(Location.team_id == radio.team_id)
                     .order_by(Location.time.desc()).limit(1)).first()
    return RadioFacts(
        id=radio.team_id, node_num=radio.node_num, kind=radio.kind,
        people=[Carrier(id=person.searcher_id, name=full_name(person), placeholder=placeholder_number(person) is not None)
                for person in carriers(db, radio.team_id, at)],
        group_id=group_of(db, radio.team_id, at),
        last_position=Position(time=newest.time, lat=newest.lat, lon=newest.lon, elevation=newest.elevation)
        if newest else None,
    )


def group_of(db: Session, radio_id: int, at: datetime | None) -> int | None:
    """The group this radio is in at this moment, or now."""
    return db.exec(select(TeamGroupAssignment.search_group_id).where(
        TeamGroupAssignment.team_id == radio_id,
        going(TeamGroupAssignment.from_time, TeamGroupAssignment.to_time, at),
    ).order_by(TeamGroupAssignment.assignment_id.desc())).first()


def list_groups(db: Session) -> list[GroupFacts]:
    at = standing_time(db)
    return [group_facts(db, group_id, at) for group_id in db.exec(
        select(SearchGroup.search_group_id).order_by(SearchGroup.search_group_id))]


def group_facts(db: Session, group_id: int, at: datetime | None) -> GroupFacts:
    radio_ids = db.exec(select(Team.team_id).order_by(Team.team_id)).all()
    held = db.exec(
        select(SearchSector.search_sector_id, SearchSector.name)
        .join(SectorAssignment, SectorAssignment.search_sector_id == SearchSector.search_sector_id)
        .where(SectorAssignment.search_group_id == group_id,
               going(SectorAssignment.from_time, SectorAssignment.to_time, at))
        .order_by(SectorAssignment.assignment_id.desc())
    ).first()
    return GroupFacts(
        id=group_id,
        radio_ids=[radio_id for radio_id in radio_ids if group_of(db, radio_id, at) == group_id],
        sector=HeldSector(id=held[0], name=held[1]) if held else None,
    )


def find_radio(db: Session, radio_id: int) -> Team:
    radio = db.get(Team, radio_id)
    if radio is None:
        raise HTTPException(404, "No radio in this mission has this id.")
    return radio


def find_group(db: Session, group_id: int) -> SearchGroup:
    group = db.get(SearchGroup, group_id)
    if group is None:
        raise HTTPException(404, "No group in this mission has this id.")
    return group


def searcher_radio(db: Session, radio_id: int) -> Team:
    """A radio that can be a team: one whose kind is searcher."""
    radio = find_radio(db, radio_id)
    if radio.kind != TeamKind.SEARCHER:
        raise HTTPException(409, f"{label(radio)} is not a searcher radio, so it cannot be a team.")
    return radio


def make_team(db: Session, radio_id: int, searcher_ids: list[int], group_id: int | None) -> RadioFacts:
    """Makes a team: puts these people on a radio that has nobody, in this group or none."""
    radio = searcher_radio(db, radio_id)
    if carriers(db, radio_id, None):
        raise HTTPException(409, f"{label(radio)} is already a team.")
    if not searcher_ids:
        raise HTTPException(409, "A team needs at least one searcher.")
    return set_team(db, radio, searcher_ids, group_id)


def change_team(db: Session, radio_id: int, searcher_ids: list[int], group_id: int | None) -> RadioFacts:
    """Sets who is on a radio and which group it is in. With nobody left on it, the radio is
    no longer a team and leaves its group."""
    return set_team(db, searcher_radio(db, radio_id), searcher_ids, group_id)


def set_team(db: Session, radio: Team, searcher_ids: list[int], group_id: int | None) -> RadioFacts:
    """Makes the radio's people and group what is asked. Every check comes before the first
    change, and the changes are saved together, so a refused request changes nothing."""
    radio_id = radio.team_id
    wanted = set(searcher_ids)
    on_it = {person.searcher_id for person in carriers(db, radio_id, None)}
    for searcher_id in sorted(wanted - on_it):
        can_join(db, searcher_id)
    if not wanted:
        group_id = None
    elif group_id is not None:
        find_group(db, group_id)

    now = utcnow()
    for carry in db.exec(select(SearcherTeamAssignment).where(
            SearcherTeamAssignment.team_id == radio_id, SearcherTeamAssignment.to_time.is_(None))):
        if carry.searcher_id not in wanted:
            carry.to_time = now
    for searcher_id in sorted(wanted - on_it):
        db.add(SearcherTeamAssignment(searcher_id=searcher_id, team_id=radio_id, from_time=now))
    put_in_group(db, radio_id, group_id, now)
    db.commit()
    return radio_facts(db, radio, None)


def can_join(db: Session, searcher_id: int) -> None:
    """Refuses a person who cannot be put on a radio: one who is not checked in, or who
    already carries one."""
    person = mission_people.find(db, searcher_id)
    if mission_people.open_checkin(db, searcher_id) is None:
        raise HTTPException(409, f"{full_name(person)} is not checked in.")
    carried = db.exec(select(SearcherTeamAssignment.team_id).where(
        SearcherTeamAssignment.searcher_id == searcher_id, SearcherTeamAssignment.to_time.is_(None))).first()
    if carried is not None:
        raise HTTPException(409, f"{full_name(person)} already carries Radio {carried}.")


def put_in_group(db: Session, radio_id: int, group_id: int | None, now: datetime) -> None:
    """Moves a radio to this group, or to none. A radio already there is left as it is."""
    row = db.exec(select(TeamGroupAssignment).where(
        TeamGroupAssignment.team_id == radio_id, TeamGroupAssignment.to_time.is_(None))).first()
    if (row.search_group_id if row else None) == group_id:
        return
    if row:
        row.to_time = now
        db.flush()  # the old row is closed before the new one opens: a radio has one open row
    if group_id is not None:
        db.add(TeamGroupAssignment(team_id=radio_id, search_group_id=group_id, from_time=now))


def make_group(db: Session, radio_ids: list[int]) -> GroupFacts:
    """Makes the next group from these teams. A team that was in another group moves."""
    if not radio_ids:
        raise HTTPException(409, "A group is made with at least one team.")
    teams_only(db, radio_ids)
    group = SearchGroup()
    db.add(group)
    db.flush()  # gives the new group its id
    return set_group(db, group.search_group_id, radio_ids)


def change_group(db: Session, group_id: int, radio_ids: list[int]) -> GroupFacts:
    """Sets which teams are in a group. A team left out has no group; a team added from
    another group moves. A group left with none stays."""
    find_group(db, group_id)
    teams_only(db, radio_ids)
    return set_group(db, group_id, radio_ids)


def teams_only(db: Session, radio_ids: list[int]) -> None:
    """Refuses a radio that is not a team."""
    for radio_id in radio_ids:
        radio = find_radio(db, radio_id)
        if not carriers(db, radio_id, None):
            raise HTTPException(409, f"{label(radio)} has nobody on it, so it cannot be in a group.")


def set_group(db: Session, group_id: int, radio_ids: list[int]) -> GroupFacts:
    now = utcnow()
    in_it = db.exec(select(TeamGroupAssignment.team_id).where(
        TeamGroupAssignment.search_group_id == group_id, TeamGroupAssignment.to_time.is_(None))).all()
    for radio_id in in_it:
        if radio_id not in radio_ids:
            put_in_group(db, radio_id, None, now)
    for radio_id in radio_ids:
        put_in_group(db, radio_id, group_id, now)
    db.commit()
    return group_facts(db, group_id, None)
