"""Open the next operational period of a mission as a new file.

A mission is one file per operational period (a shift of work). When the commander wraps a
period up and later sets up the next one, the command post calls open_next_period() with
the previous file, the path for the new one, and a CarryoverPolicy saying what to keep.

Two halves, deliberately separate:

  CarryoverPolicy   WHAT is carried. This is the command post's business (Elijah): change
                    the defaults, add a field, or build a policy from the commander's picks
                    in the UI. Nothing below depends on the specific choices.

  open_next_period  HOW it is carried. These rules hold whatever the policy says:
                    - both files are at the current schema (migrated if not);
                    - the new file is a fresh mission row: same uuid, name and time
                      zone, operational_period + 1, no end_time; it is 'active' from
                      start_time, or 'planning' with no start_time if asked;
                    - carried rows keep their ids, so sector 3 is the same shape in every
                      period's file, the phone's assignment id stays stable, and new rows
                      continue the numbering;
                    - a period's own history is never carried: location, message,
                      sector_entry, sector_dispatch, searcher_checkin, and the three
                      assignment tables;
                    - a carried 'searching' sector arrives 'partial' (searched in part; its
                      assignment stayed behind), a 'partial' one stays 'partial', and a
                      carried waypoint whose message or radio stayed behind is unlinked,
                      not dropped;
                    - the previous file is not modified (beyond migration), the new file
                      is refused if it already holds a mission, and foreign keys are
                      checked before returning.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, select

from .db import create_db_engine
from .migrate import current, head_revision, upgrade
from .models import (
    MessageType,
    Mission,
    MissionStatus,
    SearchArea,
    Searcher,
    SearchGroup,
    SearchSector,
    SearchSectorPoint,
    SectorStatus,
    Team,
    Waypoint,
    WaypointType,
)
from .sqltypes import utcnow

ALL = None  # for the id selections below: carry every row


@dataclass
class CarryoverPolicy:
    """What the next operational period starts with. Team decisions as of Nov 19, 2026;
    the command post owns this and may change it."""

    searchers: Iterable[int] | None = ALL   # ids to carry; None = all (the roster)
    teams: Iterable[int] | None = ALL       # ids to carry; None = all radios
    groups: Iterable[int] | None = ()       # ids to carry; default none (rebuilt each period)
    search_area: bool = True                # always static for a mission
    completed_sectors: bool = True          # history worth seeing on the map
    open_sectors: bool = True               # drawn, searching or partial; see the rules above
    waypoints: bool = True                  # every waypoint, removed ones included
    removed_waypoints: bool = True          # set False to carry only the ones still on the map
    custom_types: bool = True               # message_type / waypoint_type rows the team added
    start_time: datetime | None = None      # the new period's start; None = now
    planning: bool = False                  # True: open the period as 'planning', not started


@dataclass
class CarryoverReport:
    operational_period: int
    searchers: int = 0
    teams: int = 0
    groups: int = 0
    sectors: int = 0
    sector_points: int = 0
    sectors_reopened: list[int] = field(default_factory=list)  # were 'searching', now 'partial'
    waypoints: int = 0
    waypoints_unlinked: int = 0  # lost their message_id / team_id because those stayed behind


def _url(path_or_url: str | Path) -> str:
    s = str(path_or_url)
    return s if "://" in s else f"sqlite:///{s}"


def _copy(row, **overrides):
    """A new instance of the same model with the same column values (ids included)."""
    data = {k: getattr(row, k) for k in row.__table__.columns.keys()}
    data.update(overrides)
    return type(row)(**data)


def _selected(ids: Iterable[int] | None):
    return None if ids is None else set(ids)


def open_next_period(
    previous: str | Path,
    new: str | Path,
    policy: CarryoverPolicy | None = None,
    **policy_overrides,
) -> CarryoverReport:
    """Create `new` as the next operational period of the mission in `previous`.

    Pass a CarryoverPolicy, or keyword overrides of its fields:
        open_next_period(p1, p2, teams=[1, 2, 5], groups=[2])
    Raises FileExistsError if `new` already holds a mission.
    """
    policy = policy or CarryoverPolicy()
    for key, value in policy_overrides.items():
        if not hasattr(policy, key):
            raise TypeError(f"unknown carry-over option {key!r}")
        setattr(policy, key, value)

    prev_url, new_url = _url(previous), _url(new)
    if current(prev_url) != head_revision():
        upgrade(prev_url)
    upgrade(new_url)

    prev_engine = create_db_engine(prev_url)
    new_engine = create_db_engine(new_url)
    try:
        with Session(prev_engine) as src, Session(new_engine) as dst:
            if dst.exec(select(Mission)).first() is not None:
                raise FileExistsError(f"{new} already holds a mission")
            old = src.exec(select(Mission)).one()
            report = CarryoverReport(operational_period=old.operational_period + 1)
            dst.add(Mission(
                mission_id=1,
                mission_uuid=old.mission_uuid,
                name=old.name,
                operational_period=report.operational_period,
                time_zone=old.time_zone,
                status=MissionStatus.PLANNING if policy.planning else MissionStatus.ACTIVE,
                start_time=None if policy.planning else (policy.start_time or utcnow()),
            ))

            if policy.search_area:
                for area in src.exec(select(SearchArea)):
                    dst.add(_copy(area))

            if policy.custom_types:
                for model in (MessageType, WaypointType):
                    have = set(dst.exec(select(model.type_code)).all())
                    for row in src.exec(select(model)):
                        if row.type_code not in have:
                            dst.add(_copy(row))

            keep = _selected(policy.searchers)
            for s in src.exec(select(Searcher)):
                if keep is None or s.searcher_id in keep:
                    dst.add(_copy(s))
                    report.searchers += 1

            keep = _selected(policy.teams)
            carried_team_ids: set[int] = set()
            for t in src.exec(select(Team)):
                if keep is None or t.team_id in keep:
                    dst.add(_copy(t, active=False))  # kind is kept; the commander may change it
                    carried_team_ids.add(t.team_id)
                    report.teams += 1

            keep = _selected(policy.groups)
            for g in src.exec(select(SearchGroup)):
                if keep is None or g.search_group_id in keep:
                    dst.add(_copy(g))
                    report.groups += 1

            dst.flush()  # parents before children, for the foreign keys below

            carried_sector_ids: set[int] = set()
            for sector in src.exec(select(SearchSector)):
                completed = sector.status == SectorStatus.COMPLETED
                if completed and not policy.completed_sectors:
                    continue
                if not completed and not policy.open_sectors:
                    continue
                status = sector.status
                if status == SectorStatus.SEARCHING:
                    status = SectorStatus.PARTIAL
                    report.sectors_reopened.append(sector.search_sector_id)
                dst.add(_copy(sector, status=status))
                carried_sector_ids.add(sector.search_sector_id)
                report.sectors += 1
            dst.flush()
            for point in src.exec(select(SearchSectorPoint)):
                if point.search_sector_id in carried_sector_ids:
                    dst.add(_copy(point))
                    report.sector_points += 1

            if policy.waypoints:
                for w in src.exec(select(Waypoint)):
                    if w.removed_time is not None and not policy.removed_waypoints:
                        continue
                    team_id = w.team_id if w.team_id in carried_team_ids else None
                    if w.message_id is not None or team_id != w.team_id:
                        report.waypoints_unlinked += 1
                    dst.add(_copy(w, team_id=team_id, message_id=None))
                    report.waypoints += 1

            dst.commit()
            with new_engine.connect() as conn:
                violations = conn.execute(text("PRAGMA foreign_key_check")).fetchall()
            if violations:
                raise RuntimeError(f"carry-over left foreign key violations: {violations[:5]}")
            return report
    finally:
        prev_engine.dispose()
        new_engine.dispose()
