"""The open mission.

The backend remembers one open mission: the one last picked from the list. Every route that
reads or saves mission data reaches it through the functions in this file, so the planned
change to "every request names its mission" is made here and nowhere else.

A mission is opened at its latest session, and that session's file is the one read and saved.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from missiondb import create_db_engine
from missiondb.models import Mission, MissionStatus
from settings.settings_file import change_settings, read_settings

from .files import MissionFacts, facts_from, file_url, mission_folders, session_files


@dataclass
class OpenMission:
    mission_id: str
    folder: Path    # the mission's folder
    file: Path      # the open session's file
    engine: Engine  # the connection to that file


class OpenMissionFacts(MissionFacts):
    """The open mission as the web app reads it."""

    asks_to_continue: bool = False


_open: OpenMission | None = None


def open_mission(mission_id: str) -> OpenMission:
    """Opens the mission with this id at its latest session, in place of the one that was
    open, and saves it as the last mission opened."""
    for folder, files in mission_folders():
        if files[-1][1].mission_uuid == mission_id:
            return open_folder(folder)
    raise HTTPException(404, "No mission has this id.")


def open_folder(folder: Path) -> OpenMission:
    """Opens the mission kept in this folder, at its latest session."""
    global _open
    files = session_files(folder)
    file, row = files[-1]
    close_mission(forget=False)
    _open = OpenMission(row.mission_uuid, folder, file, create_db_engine(file_url(file)))
    change_settings({"last_mission": row.mission_uuid})
    return _open


def close_mission(forget: bool = True) -> None:
    """Leaves no mission open. forget=False keeps it saved as the last mission opened, as
    when the backend stops."""
    global _open
    if _open is not None:
        _open.engine.dispose()
        _open = None
    if forget:
        change_settings({"last_mission": None})


def reopen_last_mission() -> None:
    """Run when the backend starts: opens the mission that was open when it last ran. If
    that mission is no longer in the missions folder, none is open."""
    last = read_settings().last_mission
    if last is None:
        return
    try:
        open_mission(last)
    except HTTPException:
        print(f"MISSION the last mission opened ({last}) is no longer in the missions folder", flush=True)


def get_open_mission() -> OpenMission | None:
    return _open


def require_open_mission() -> OpenMission:
    """The open mission. With none open the request is refused, with a line saying so."""
    if _open is None:
        raise HTTPException(409, "No mission is open.")
    return _open


def open_mission_facts() -> OpenMissionFacts | None:
    """The open mission's facts, read from its files now, or None with none open."""
    if _open is None:
        return None
    facts = facts_from(session_files(_open.folder))
    return OpenMissionFacts(**facts.model_dump())


def mission_session() -> Iterator[Session]:
    """A database session on the open mission, for a route that reads.

        def route(db: Session = Depends(mission_session)): ...
    """
    with Session(require_open_mission().engine) as db:
        yield db


def changeable_session() -> Iterator[Session]:
    """A database session on the open mission, for a route that saves. A paused or ended
    session cannot be changed, so the request is refused unless the session is in planning
    or active."""
    with Session(require_open_mission().engine) as db:
        status = db.exec(select(Mission.status)).one()
        if status not in (MissionStatus.PLANNING, MissionStatus.ACTIVE):
            raise HTTPException(409, f"This session is {status.value}, so nothing in it can be changed.")
        yield db
