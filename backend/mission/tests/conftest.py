"""Mission files for the mission tests, built in temporary folders."""

import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from missiondb import create_db_engine
from missiondb.migrate import upgrade
from missiondb.models import Mission, MissionStatus
from server.main import app

BACKEND = Path(__file__).resolve().parents[2]
ARIZONA07_SEED = BACKEND / "missiondb" / "sample-missions" / "arizona07" / "arizona07-seed.sql"
ARIZONA07_ID = "952592f8-f48b-4310-aa51-3abcefc02005"


def utc(year, month, day, hour=0, minute=0, second=0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


def settle(path: Path) -> None:
    """Moves everything SQLite still holds in its side files into the one file, so a copy
    of that file is whole."""
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")


@pytest.fixture(scope="session")
def empty_file(tmp_path_factory) -> Path:
    """A mission file at the current schema with no mission in it. Built once for the whole
    run, because running the migrations is the slow part; each test copies it."""
    path = tmp_path_factory.mktemp("templates") / "empty.sqlite3"
    upgrade(f"sqlite:///{path}")
    settle(path)
    return path


@pytest.fixture(scope="session")
def arizona07_file(tmp_path_factory) -> Path:
    """Arizona07, built the way its README says. Built once; each test copies it."""
    path = tmp_path_factory.mktemp("templates") / "arizona07.sqlite3"
    upgrade(f"sqlite:///{path}", "0003")
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(ARIZONA07_SEED.read_text(encoding="utf-8"))
    upgrade(f"sqlite:///{path}")
    settle(path)
    return path


@pytest.fixture
def arizona07(missions_dir, arizona07_file) -> Path:
    """Arizona07 in the missions folder, under the file name its README gives it."""
    path = missions_dir / "arizona07" / "day-01.sqlite3"
    path.parent.mkdir(parents=True)
    shutil.copy(arizona07_file, path)
    return path


@pytest.fixture
def make_mission(missions_dir, empty_file):
    """Makes one session's file of a made-up mission in the missions folder."""

    def make(
        file: str,                      # where in the missions folder: "bear-creek/session-01.sqlite3"
        name: str = "Bear Creek",
        mission_id: str = "11111111-2222-3333-4444-555555555555",
        session: int = 1,
        status: str = "planning",
        time_zone: str = "America/Denver",
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Path:
        path = missions_dir / file
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(empty_file, path)
        engine = create_db_engine(f"sqlite:///{path}")
        with Session(engine) as db:
            db.add(Mission(
                mission_id=1, mission_uuid=mission_id, name=name, operational_period=session,
                status=MissionStatus(status), time_zone=time_zone, start_time=start, end_time=end,
            ))
            db.commit()
        engine.dispose()
        return path

    return make


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
