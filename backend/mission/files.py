"""Reading the missions folder: which missions are in it, and the sessions of each.

Everything is read from inside each file, never from a file's or a folder's name. A mission
is the files of one folder, and a file's session number is the one saved in it.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from missiondb import create_db_engine
from missiondb.models import Mission, MissionStatus

from .folders import missions_folder

FILE_PATTERN = "*.sqlite3"


class SessionFacts(BaseModel):
    number: int
    status: MissionStatus
    start_time: datetime | None  # none while the session is in planning
    end_time: datetime | None    # none until the session is paused or ended


class MissionFacts(BaseModel):
    """A mission as the list shows it. The status, session number and times are those of
    its latest session."""

    id: str
    name: str
    time_zone: str
    status: MissionStatus
    session: int
    start_time: datetime | None
    end_time: datetime | None
    sessions: list[SessionFacts]  # every session, first to latest


def file_url(path: Path) -> str:
    return f"sqlite:///{path}"


def read_mission_row(path: Path) -> Mission | None:
    """The mission row saved in this file, or None when the file is not a mission file this
    version of the app can read."""
    try:
        engine = create_db_engine(file_url(path))
    except (SQLAlchemyError, sqlite3.Error):
        return None
    try:
        with Session(engine) as db:
            row = db.exec(select(Mission)).first()
            if row is not None:
                db.expunge(row)  # lets the row be read after its session has closed
            return row
    except (SQLAlchemyError, sqlite3.Error):  # not a database, or not these tables
        return None
    finally:
        engine.dispose()


def session_files(folder: Path) -> list[tuple[Path, Mission]]:
    """Each session's file in a mission's folder with its mission row, first session first."""
    found = []
    for path in sorted(folder.glob(FILE_PATTERN)):
        row = read_mission_row(path)
        if row is not None:
            found.append((path, row))
    return sorted(found, key=lambda file: file[1].operational_period)


def facts_from(files: list[tuple[Path, Mission]]) -> MissionFacts:
    """The mission's facts, from its session files as session_files lists them."""
    latest = files[-1][1]
    return MissionFacts(
        id=latest.mission_uuid,
        name=latest.name,
        time_zone=latest.time_zone,
        status=latest.status,
        session=latest.operational_period,
        start_time=latest.start_time,
        end_time=latest.end_time,
        sessions=[
            SessionFacts(number=row.operational_period, status=row.status,
                         start_time=row.start_time, end_time=row.end_time)
            for _, row in files
        ],
    )


def mission_folders() -> list[tuple[Path, list[tuple[Path, Mission]]]]:
    """Every mission in the missions folder: its folder and its session files."""
    root = missions_folder()
    if not root.is_dir():
        return []
    missions = []
    for folder in sorted(root.iterdir()):
        if folder.is_dir() and (files := session_files(folder)):
            missions.append((folder, files))
    return missions


def list_missions() -> list[MissionFacts]:
    """Every mission, in order of name."""
    missions = [facts_from(files) for _, files in mission_folders()]
    return sorted(missions, key=lambda mission: mission.name.lower())
