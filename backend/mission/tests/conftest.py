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


BEAR_CREEK_ID = "11111111-2222-3333-4444-555555555555"
START = utc(2026, 11, 20, 15)   # when the made-up mission's session started
NOW = utc(2026, 11, 20, 23, 30)  # what the clock reads when a test presses a button


@pytest.fixture
def clock(monkeypatch):
    """Stops the backend's clock at NOW. A test moves it with clock.set(...)."""
    from mission import lifecycle, next_session

    class Clock:
        def set(self, time: datetime) -> None:
            for module in (lifecycle, next_session):  # each reads the time through its own utcnow
                monkeypatch.setattr(module, "utcnow", lambda: time)

    stopped = Clock()
    stopped.set(NOW)
    return stopped


@pytest.fixture
def open_bear_creek(client, make_mission, clock):
    """Makes Bear Creek with one session in the status asked for, opens it, and answers
    with its file."""

    def make(status: str = "planning", **facts) -> Path:
        times = {
            "planning": {},
            "active": {"start": START},
            "paused": {"start": START, "end": utc(2026, 11, 20, 22)},
            "ended": {"start": START, "end": utc(2026, 11, 20, 22)},
        }[status]
        path = make_mission("bear-creek/session-01.sqlite3", status=status, **(times | facts))
        client.post(f"/api/missions/{BEAR_CREEK_ID}/open")
        return path

    return make


def rows(path: Path, sql: str) -> list[tuple]:
    """What a query finds in a mission file."""
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute(sql).fetchall()


def add_teams(path: Path) -> None:
    """Puts people on radios in a mission file: searchers 1 and 2 carry radio 1, which is in
    group 1; searcher 3 carries radio 2, which is in no group. All three are checked in.
    Each table also has one row that ended at 4 pm, before the session's end."""
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript("""
            INSERT INTO team (team_id, node_num) VALUES (1, 101), (2, 102);
            INSERT INTO searcher (searcher_id, fname, lname) VALUES (1, 'Ana', 'Ruiz'), (2, 'Ben', 'Cho'), (3, 'Cy', 'Dunn');
            INSERT INTO search_group (search_group_id) VALUES (1);
            INSERT INTO searcher_team_assignment (searcher_id, team_id, from_time, to_time) VALUES
                (3, 1, '2026-11-20T15:00:00Z', '2026-11-20T16:00:00Z'),
                (1, 1, '2026-11-20T15:00:00Z', NULL),
                (2, 1, '2026-11-20T15:00:00Z', NULL),
                (3, 2, '2026-11-20T16:00:00Z', NULL);
            INSERT INTO team_group_assignment (team_id, search_group_id, from_time, to_time) VALUES
                (2, 1, '2026-11-20T15:00:00Z', '2026-11-20T16:00:00Z'),
                (1, 1, '2026-11-20T15:00:00Z', NULL);
            INSERT INTO searcher_checkin (searcher_id, in_time, out_time) VALUES
                (3, '2026-11-20T14:00:00Z', '2026-11-20T16:00:00Z'),
                (1, '2026-11-20T15:00:00Z', NULL),
                (2, '2026-11-20T15:00:00Z', NULL),
                (3, '2026-11-20T16:00:00Z', NULL);
        """)
        connection.commit()


def add_sectors(path: Path) -> None:
    """Puts sectors in a mission file that add_teams has filled, each held a different way:

        S1  searching  held by group 1, whose radio 1 entered it after the group took it
        S2  drawn      held by group 2, not yet entered
        S3  partial    held by group 3 a second time, and not yet entered this time
        S4  drawn      held by nobody
        S5  completed  group 1 held it until 3:05 pm
    """
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript("""
            INSERT INTO search_group (search_group_id) VALUES (2), (3);
            INSERT INTO search_sector (search_sector_id, name, status, created_time, completed_time) VALUES
                (1, 'S1', 'searching', '2026-11-20T15:00:00Z', NULL),
                (2, 'S2', 'drawn', '2026-11-20T15:00:00Z', NULL),
                (3, 'S3', 'partial', '2026-11-20T15:00:00Z', NULL),
                (4, 'S4', 'drawn', '2026-11-20T15:00:00Z', NULL),
                (5, 'S5', 'completed', '2026-11-20T15:00:00Z', '2026-11-20T15:05:00Z');
            INSERT INTO sector_assignment (search_sector_id, search_group_id, from_time, to_time) VALUES
                (5, 1, '2026-11-20T15:01:00Z', '2026-11-20T15:05:00Z'),
                (3, 3, '2026-11-20T15:01:00Z', '2026-11-20T15:08:00Z'),
                (1, 1, '2026-11-20T15:10:00Z', NULL),
                (2, 2, '2026-11-20T15:10:00Z', NULL),
                (3, 3, '2026-11-20T15:20:00Z', NULL);
            INSERT INTO sector_entry (team_id, search_sector_id, entered_time) VALUES
                (1, 1, '2026-11-20T15:30:00Z');
        """)
        connection.commit()
