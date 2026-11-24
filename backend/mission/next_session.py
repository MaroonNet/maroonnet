"""Starting the next session of the open mission.

The next session is a new file beside the last one. missiondb's carry-over makes it and
brings the radios, people, search area, sectors and waypoints. It does not bring who was on
which radio or which radio was in which group, so when the commander keeps the teams, those
rows are written again here, as they stood when the last session ended.
"""

from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import or_
from sqlmodel import Session, select

from missiondb import create_db_engine
from missiondb.carryover import ALL, open_next_period
from missiondb.models import Mission, MissionStatus, SearcherTeamAssignment, TeamGroupAssignment
from missiondb.sqltypes import utcnow

from .create import session_file_name
from .files import file_url
from .open_mission import OpenMission


def start_next_session(last: OpenMission, keep_teams: bool) -> Path:
    """Makes the file of the session after the open one, started now, and answers with it.
    The carry-over does not look at the last session's status, so it is checked here."""
    with Session(last.engine) as db:
        mission = db.exec(select(Mission)).one()
        if mission.status != MissionStatus.PAUSED:
            raise HTTPException(409, "The next session can be started only from a paused session.")
        carries, groups = teams_at(db, mission.end_time) if keep_teams else ([], [])
        number = mission.operational_period + 1

    new_file = last.folder / session_file_name(number)
    if new_file.exists():
        raise HTTPException(409, f"{new_file.name} is already in the mission's folder.")

    now = utcnow()
    try:
        open_next_period(last.file, new_file, groups=ALL if keep_teams else (), start_time=now)
        engine = create_db_engine(file_url(new_file))
        try:
            with Session(engine) as db:
                for searcher_id, team_id in carries:
                    db.add(SearcherTeamAssignment(searcher_id=searcher_id, team_id=team_id, from_time=now))
                for team_id, group_id in groups:
                    db.add(TeamGroupAssignment(team_id=team_id, search_group_id=group_id, from_time=now))
                db.commit()
        finally:
            engine.dispose()
    except Exception:
        # Half a session is worse than none: take away what was made, so it can be tried again.
        for leftover in last.folder.glob(f"{new_file.name}*"):
            leftover.unlink()
        raise
    return new_file


def teams_at(db: Session, end_time) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """The teams as they stood at this time: each (person, radio) and each (radio, group)
    whose row was still going then."""

    def going(table):
        return or_(table.to_time.is_(None), table.to_time >= end_time)

    carries = db.exec(
        select(SearcherTeamAssignment.searcher_id, SearcherTeamAssignment.team_id)
        .where(SearcherTeamAssignment.from_time <= end_time, going(SearcherTeamAssignment))
        .order_by(SearcherTeamAssignment.assignment_id)
    ).all()
    groups = db.exec(
        select(TeamGroupAssignment.team_id, TeamGroupAssignment.search_group_id)
        .where(TeamGroupAssignment.from_time <= end_time, going(TeamGroupAssignment))
        .order_by(TeamGroupAssignment.assignment_id)
    ).all()
    # A person carries one radio and a radio is in one group. If two of their rows were
    # going in that same second, the newer one stands.
    return list(dict(carries).items()), list(dict(groups).items())
