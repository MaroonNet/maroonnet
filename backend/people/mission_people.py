"""The people in the open mission: who is checked in, and what radio each carries.

A mission file holds a person as a first and last name (the searcher table), with a row in
searcher_checkin for each stretch they were present and a row in searcher_team_assignment
for each stretch they carried a radio. A row with no end time is still going.

A person is tied to the roster by first and last name only, until missiondb has a roster id.
"""

import re
from datetime import datetime
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, func, or_
from sqlmodel import Session, delete, select

from missiondb.models import (
    Mission, MissionStatus, Searcher, SearcherCheckin, SearcherTeamAssignment, Team, TeamGroupAssignment,
)
from missiondb.sqltypes import utcnow

from . import roster
from .roster import RosterPerson


class Event(BaseModel):
    """One line of a person's history."""

    time: datetime
    what: Literal["checked_in", "checked_out", "took_radio", "left_radio"]
    team_id: int | None  # the radio, for the two radio events


class PersonFacts(BaseModel):
    """A person of the open mission as the web app reads them."""

    id: int
    first_name: str
    last_name: str
    checked_in: bool
    in_time: datetime | None    # their latest check-in this session; none: not yet checked in
    out_time: datetime | None   # when that check-in ended, if it has
    in_roster: bool             # someone in the roster has this first and last name
    roster_id: int | None       # that roster person, when there is exactly one
    phone: str | None           # their phone number, from the roster
    team_id: int | None         # the radio they carry
    node_num: int | None        # that radio's node number
    group_id: int | None        # the group that radio is in
    shares: list[str]           # the names of the others carrying the same radio
    last_on_radio: bool         # nobody else carries their radio
    placeholder: bool           # a stand-in such as "Searcher #1"
    can_remove: bool            # a placeholder that has never carried a radio
    history: list[Event]        # oldest first


# A placeholder is an ordinary row with the first name "Searcher" and a last name such as
# "#3". missiondb has no mark for one, so the name is all that tells it apart.
PLACEHOLDER_FIRST_NAME = "Searcher"
PLACEHOLDER_LAST_NAME = re.compile(r"#(\d+)")


def placeholder_number(searcher: Searcher) -> int | None:
    """The 3 of "Searcher #3", or None for a real person."""
    number = PLACEHOLDER_LAST_NAME.fullmatch(searcher.lname)
    return int(number.group(1)) if number and searcher.fname == PLACEHOLDER_FIRST_NAME else None


# Where two events have the same time, the one that ends something comes first.
EVENT_ORDER = {"left_radio": 0, "checked_out": 1, "checked_in": 2, "took_radio": 3}

Roster = dict[tuple[str, str], list[RosterPerson]]


def roster_by_name() -> Roster:
    """The roster, read once, with its people under their first and last name in small letters."""
    by_name: Roster = {}
    for person in roster.list_people():
        by_name.setdefault(name_key(person.first_name, person.last_name), []).append(person)
    return by_name


def name_key(first_name: str, last_name: str) -> tuple[str, str]:
    return first_name.lower(), last_name.lower()


def full_name(searcher: Searcher) -> str:
    return f"{searcher.fname} {searcher.lname}"


def standing_time(db: Session) -> datetime | None:
    """The moment the session is read at. A paused or ended session is read as it stood at
    its end time; one in planning or active is read as it is now, which is None here."""
    mission = db.exec(select(Mission)).one()
    return mission.end_time if mission.status in (MissionStatus.PAUSED, MissionStatus.ENDED) else None


def going(start, end, at: datetime | None):
    """The condition that a stretch was going at this moment, or is still going now."""
    if at is None:
        return end.is_(None)
    return and_(start <= at, or_(end.is_(None), end >= at))


def list_people(db: Session) -> list[PersonFacts]:
    at = standing_time(db)
    known = roster_by_name()
    return [facts(db, searcher, at, known) for searcher in db.exec(select(Searcher).order_by(Searcher.searcher_id))]


def facts_of(db: Session, searcher: Searcher) -> PersonFacts:
    """One person's facts, as a route answers after changing them."""
    return facts(db, searcher, standing_time(db), roster_by_name())


def facts(db: Session, searcher: Searcher, at: datetime | None, known: Roster) -> PersonFacts:
    searcher_id = searcher.searcher_id
    checkins = db.exec(select(SearcherCheckin).where(SearcherCheckin.searcher_id == searcher_id)
                       .order_by(SearcherCheckin.in_time, SearcherCheckin.checkin_id)).all()
    carries = db.exec(select(SearcherTeamAssignment).where(SearcherTeamAssignment.searcher_id == searcher_id)
                      .order_by(SearcherTeamAssignment.from_time, SearcherTeamAssignment.assignment_id)).all()

    present = db.exec(select(SearcherCheckin).where(
        SearcherCheckin.searcher_id == searcher_id, going(SearcherCheckin.in_time, SearcherCheckin.out_time, at),
    ).order_by(SearcherCheckin.checkin_id.desc())).first()
    latest = present or (checkins[-1] if checkins else None)

    carry = db.exec(select(SearcherTeamAssignment).where(
        SearcherTeamAssignment.searcher_id == searcher_id,
        going(SearcherTeamAssignment.from_time, SearcherTeamAssignment.to_time, at),
    ).order_by(SearcherTeamAssignment.assignment_id.desc())).first()
    team = db.get(Team, carry.team_id) if carry else None
    group_id = None
    shares: list[str] = []
    if team:
        group_id = db.exec(select(TeamGroupAssignment.search_group_id).where(
            TeamGroupAssignment.team_id == team.team_id,
            going(TeamGroupAssignment.from_time, TeamGroupAssignment.to_time, at),
        ).order_by(TeamGroupAssignment.assignment_id.desc())).first()
        shares = [full_name(other) for other in carriers(db, team.team_id, at) if other.searcher_id != searcher_id]

    matches = known.get(name_key(searcher.fname, searcher.lname), [])
    # With two roster people of one name, the app cannot tell which this is.
    one = matches[0] if len(matches) == 1 else None

    history = [Event(time=row.in_time, what="checked_in", team_id=None) for row in checkins]
    history += [Event(time=row.out_time, what="checked_out", team_id=None) for row in checkins if row.out_time]
    history += [Event(time=row.from_time, what="took_radio", team_id=row.team_id) for row in carries]
    history += [Event(time=row.to_time, what="left_radio", team_id=row.team_id) for row in carries if row.to_time]
    history.sort(key=lambda event: (event.time, EVENT_ORDER[event.what]))

    return PersonFacts(
        id=searcher_id, first_name=searcher.fname, last_name=searcher.lname,
        checked_in=present is not None,
        in_time=latest.in_time if latest else None, out_time=latest.out_time if latest else None,
        in_roster=bool(matches), roster_id=one.id if one else None, phone=one.phone if one else None,
        team_id=team.team_id if team else None, node_num=team.node_num if team else None, group_id=group_id,
        shares=shares, last_on_radio=team is not None and not shares,
        placeholder=placeholder_number(searcher) is not None,
        can_remove=placeholder_number(searcher) is not None and not carries,
        history=history,
    )


def carriers(db: Session, team_id: int, at: datetime | None) -> list[Searcher]:
    """The people carrying this radio at this moment, or now."""
    return db.exec(
        select(Searcher).join(SearcherTeamAssignment, SearcherTeamAssignment.searcher_id == Searcher.searcher_id)
        .where(SearcherTeamAssignment.team_id == team_id,
               going(SearcherTeamAssignment.from_time, SearcherTeamAssignment.to_time, at))
        .order_by(Searcher.searcher_id)
    ).all()


def find(db: Session, searcher_id: int) -> Searcher:
    searcher = db.get(Searcher, searcher_id)
    if searcher is None:
        raise HTTPException(404, "No one in this mission has this id.")
    return searcher


def named(db: Session, first_name: str, last_name: str) -> list[Searcher]:
    """The mission's people with this first and last name. Capital and small letters count
    as the same."""
    return db.exec(
        select(Searcher)
        .where(func.lower(Searcher.fname) == first_name.lower(), func.lower(Searcher.lname) == last_name.lower())
        .order_by(Searcher.searcher_id)
    ).all()


def open_checkin(db: Session, searcher_id: int) -> SearcherCheckin | None:
    return db.exec(select(SearcherCheckin).where(
        SearcherCheckin.searcher_id == searcher_id, SearcherCheckin.out_time.is_(None))).first()


def check_in_from_roster(db: Session, roster_id: int) -> PersonFacts:
    """Checks a roster person in. Their first and last name are copied into the mission;
    the middle initial and phone stay in the roster. A person the mission already holds
    under that name and who is not checked in, as one carried from the last session, is the
    row used."""
    person = roster.get_person(roster_id)
    rows = named(db, person.first_name, person.last_name)
    waiting = [row for row in rows if open_checkin(db, row.searcher_id) is None]
    if waiting:
        searcher = waiting[0]
    else:
        # Two roster people whose names differ only by the initial each get a row. Once
        # there is a checked-in row for each of them, another would be a repeat.
        if len(rows) >= len(roster.people_named(person.first_name, person.last_name)):
            raise HTTPException(409, f"{person.first_name} {person.last_name} is already checked in.")
        searcher = Searcher(fname=person.first_name, lname=person.last_name)
        db.add(searcher)
        db.flush()  # gives the new row its id
    db.add(SearcherCheckin(searcher_id=searcher.searcher_id, in_time=utcnow()))
    db.commit()
    return facts_of(db, searcher)


def check_in(db: Session, searcher_id: int) -> PersonFacts:
    """Checks in a person the mission already holds: one carried from the last session, or
    one who checked out and came back. Each time is a new row."""
    searcher = find(db, searcher_id)
    if open_checkin(db, searcher_id):
        raise HTTPException(409, f"{full_name(searcher)} is already checked in.")
    db.add(SearcherCheckin(searcher_id=searcher_id, in_time=utcnow()))
    db.commit()
    return facts_of(db, searcher)


def check_out(db: Session, searcher_id: int) -> PersonFacts:
    """Checks a person out now and takes them off their radio. A radio left with nobody on
    it is no longer a team, so it leaves its group."""
    searcher = find(db, searcher_id)
    checkin = open_checkin(db, searcher_id)
    if checkin is None:
        raise HTTPException(409, f"{full_name(searcher)} is not checked in.")
    now = utcnow()
    checkin.out_time = now
    carry = db.exec(select(SearcherTeamAssignment).where(
        SearcherTeamAssignment.searcher_id == searcher_id, SearcherTeamAssignment.to_time.is_(None))).first()
    if carry:
        carry.to_time = now
        db.flush()
        if not carriers(db, carry.team_id, None):
            in_group = db.exec(select(TeamGroupAssignment).where(
                TeamGroupAssignment.team_id == carry.team_id, TeamGroupAssignment.to_time.is_(None))).first()
            if in_group:
                in_group.to_time = now
    db.commit()
    return facts_of(db, searcher)


def add_placeholder(db: Session) -> PersonFacts:
    """Adds the next "Searcher #n", checked in. The number is the next after the highest
    in this mission."""
    numbers = [placeholder_number(searcher) or 0 for searcher in db.exec(select(Searcher))]
    searcher = Searcher(fname=PLACEHOLDER_FIRST_NAME, lname=f"#{max(numbers, default=0) + 1}")
    db.add(searcher)
    db.flush()  # gives the new row its id
    db.add(SearcherCheckin(searcher_id=searcher.searcher_id, in_time=utcnow()))
    db.commit()
    return facts_of(db, searcher)


def replace_placeholder(db: Session, searcher_id: int, roster_id: int) -> PersonFacts:
    """Gives a placeholder's row a roster person's name. The row is the same row, so the
    person has the placeholder's radio, check-in and history. Nothing records that the row
    was once a placeholder."""
    searcher = find(db, searcher_id)
    if placeholder_number(searcher) is None:
        raise HTTPException(409, f"{full_name(searcher)} is not a placeholder.")
    person = roster.get_person(roster_id)
    # Each roster person of this name may have one row; see check_in_from_roster.
    rows = named(db, person.first_name, person.last_name)
    if len(rows) >= len(roster.people_named(person.first_name, person.last_name)):
        raise HTTPException(409, f"{person.first_name} {person.last_name} is already in this mission.")
    searcher.fname, searcher.lname = person.first_name, person.last_name
    db.commit()
    return facts_of(db, searcher)


def remove_placeholder(db: Session, searcher_id: int) -> None:
    """Deletes a placeholder and its check-ins. One that has carried a radio is part of
    that radio's history, so it stays and is checked out like anyone else."""
    searcher = find(db, searcher_id)
    if placeholder_number(searcher) is None:
        raise HTTPException(409, "Only a placeholder can be removed.")
    carried = db.exec(select(SearcherTeamAssignment).where(SearcherTeamAssignment.searcher_id == searcher_id)).first()
    if carried:
        raise HTTPException(409, f"{full_name(searcher)} has carried a radio, so it cannot be removed. Check it out instead.")
    db.exec(delete(SearcherCheckin).where(SearcherCheckin.searcher_id == searcher_id))
    db.delete(searcher)
    db.commit()


def save_to_roster(db: Session, searcher_id: int) -> PersonFacts:
    """Adds a mission person to the roster, by their first and last name. The mission file
    has no initial or phone, so those are filled in later from Manage Roster."""
    searcher = find(db, searcher_id)
    if placeholder_number(searcher) is not None:
        raise HTTPException(409, "A placeholder cannot be saved to the roster.")
    roster.add_person(roster.PersonDetails(first_name=searcher.fname, last_name=searcher.lname))
    return facts_of(db, searcher)


def checked_in_as(db: Session, first_name: str, last_name: str) -> bool:
    """Whether someone of this name is checked in now."""
    return any(open_checkin(db, row.searcher_id) for row in named(db, first_name, last_name))


def rename(db: Session, old: RosterPerson, new: roster.PersonDetails) -> None:
    """A roster person's name was changed: their row in this session follows, when it is
    plain which row that is. A paused or ended session is left as it is."""
    status = db.exec(select(Mission.status)).one()
    rows = named(db, old.first_name, old.last_name)
    if status in (MissionStatus.PLANNING, MissionStatus.ACTIVE) and len(rows) == 1:
        rows[0].fname, rows[0].lname = new.first_name, new.last_name
        db.commit()
