"""Opening the next operational period from the Arizona07 fixture."""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlmodel import Session, select

from missiondb import create_db_engine
from missiondb.carryover import CarryoverPolicy, open_next_period
from missiondb.migrate import current, head_revision, upgrade
from missiondb.models import (
    Message,
    MessageDirection,
    Mission,
    SearchSector,
    SectorAssignment,
    SectorStatus,
    Team,
    Waypoint,
)

BACKEND = Path(__file__).resolve().parents[2]
SEED = BACKEND / "missiondb" / "tests" / "fixtures" / "arizona07-v1-seed.sql"
T_END = datetime(2025, 4, 14, 10, 25, tzinfo=timezone.utc)   # Arizona07 mission end


@pytest.fixture
def period1(tmp_path):
    """Arizona07 built the documented way, left at 0001 on purpose: carry-over must migrate it."""
    path = tmp_path / "op-01.sqlite3"
    upgrade(f"sqlite:///{path}", "0001")
    with sqlite3.connect(path) as conn:
        conn.executescript(SEED.read_text())
    return path


def _add_period1_extras(path):
    """A searching sector with an open assignment, a find waypoint from a message, and a
    removed waypoint, so every carry-over rule has something to act on."""
    engine = create_db_engine(f"sqlite:///{path}")
    with Session(engine) as s:
        s5 = s.get(SearchSector, 5)
        s5.status = SectorStatus.SEARCHING
        s.add(SectorAssignment(search_sector_id=5, search_group_id=2, from_time=T_END - timedelta(hours=1)))
        msg = Message(team_id=1, time=T_END - timedelta(hours=2), rx_time=T_END - timedelta(hours=2),
                      direction=MessageDirection.IN, type_code="found", text="subject located")
        s.add(msg)
        s.commit()
        s.add(Waypoint(type_code="find", lat=31.51, lon=-110.65333, time=msg.time, created_time=msg.rx_time,
                       team_id=1, message_id=msg.message_id, name="Find"))
        s.add(Waypoint(type_code="command_post", lat=31.5057, lon=-110.6762, time=T_END - timedelta(hours=7),
                       created_time=T_END - timedelta(hours=7), name="CP", removed_time=T_END - timedelta(hours=3)))
        s.add(Waypoint(type_code="command_post", lat=31.5060, lon=-110.6760, time=T_END - timedelta(hours=3),
                       created_time=T_END - timedelta(hours=3), name="CP", team_id=6))
        s.commit()
    engine.dispose()


def test_open_next_period(period1, tmp_path):
    upgrade(f"sqlite:///{period1}")
    _add_period1_extras(period1)
    period2 = tmp_path / "op-02.sqlite3"
    start = T_END + timedelta(hours=10)

    report = open_next_period(period1, period2, teams=[1, 2, 3, 4, 5], groups=[2], start_time=start)

    assert report.operational_period == 2
    assert (report.searchers, report.teams, report.groups, report.sectors, report.sector_points) == (16, 5, 1, 5, 25)
    assert report.sectors_reopened == [5]
    assert report.waypoints == 3 and report.waypoints_unlinked == 2  # find lost its message; CP lost radio 6
    assert current(f"sqlite:///{period2}") == head_revision()

    with sqlite3.connect(period2) as c:
        m = c.execute("SELECT mission_uuid, name, operational_period, start_time, end_time FROM mission").fetchone()
        assert m[1:] == ("Arizona07", 2, "2025-04-14T20:25:00Z", None)
        with sqlite3.connect(period1) as p1:
            assert m[0] == p1.execute("SELECT mission_uuid FROM mission").fetchone()[0]
        assert c.execute("SELECT search_sector_id, name, status FROM search_sector ORDER BY 1").fetchall() == [
            (1, "S1", "completed"), (2, "S2", "completed"), (3, "S3", "completed"),
            (4, "S4", "completed"), (5, "S5", "drawn")]
        assert c.execute("SELECT team_id FROM team ORDER BY 1").fetchall() == [(1,), (2,), (3,), (4,), (5,)]
        assert c.execute("SELECT search_group_id FROM search_group").fetchall() == [(2,)]
        for t in ("location", "message", "sector_entry", "sector_dispatch", "sector_assignment",
                  "team_group_assignment", "searcher_team_assignment"):
            assert c.execute(f"SELECT count(*) FROM {t}").fetchone()[0] == 0, t
        wps = c.execute("SELECT type_code, team_id, message_id, removed_time IS NULL FROM waypoint ORDER BY waypoint_id").fetchall()
        assert wps == [("find", 1, None, 1), ("command_post", None, None, 0), ("command_post", None, None, 1)]
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
        # numbering continues: the next sector drawn is S6 with id 6
        c.execute("INSERT INTO search_sector (name, status, created_time) VALUES ('S6', 'drawn', '2025-04-14T21:00:00Z')")
        assert c.execute("SELECT max(search_sector_id) FROM search_sector").fetchone()[0] == 6
        c.rollback()


def test_open_next_period_migrates_an_old_file(period1, tmp_path):
    assert current(f"sqlite:///{period1}") == "0001"
    open_next_period(period1, tmp_path / "op-02.sqlite3")
    assert current(f"sqlite:///{period1}") == head_revision()


def test_open_next_period_refuses_to_overwrite(period1, tmp_path):
    period2 = tmp_path / "op-02.sqlite3"
    open_next_period(period1, period2)
    with pytest.raises(FileExistsError):
        open_next_period(period1, period2)


def test_previous_file_untouched_except_migration(period1, tmp_path):
    upgrade(f"sqlite:///{period1}")
    with sqlite3.connect(period1) as c:
        before = {t: c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                  for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    open_next_period(period1, tmp_path / "op-02.sqlite3")
    with sqlite3.connect(period1) as c:
        after = {t: c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                 for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert after == before
    with Session(create_db_engine(f"sqlite:///{period1}")) as s:
        assert s.exec(select(Mission)).one().operational_period == 1
        assert s.get(Team, 6) is not None


def test_policy_object_and_overrides_agree(period1, tmp_path):
    """The command post may pass a CarryoverPolicy or keyword overrides; same result."""
    upgrade(f"sqlite:///{period1}")
    _add_period1_extras(period1)
    a = open_next_period(period1, tmp_path / "a.sqlite3",
                         CarryoverPolicy(teams=[1, 2], groups=[2], removed_waypoints=False))
    b = open_next_period(period1, tmp_path / "b.sqlite3", teams=[1, 2], groups=[2], removed_waypoints=False)
    assert a == b
    assert (a.teams, a.groups, a.waypoints) == (2, 1, 2)   # the removed CP pin stayed behind
    with pytest.raises(TypeError):
        open_next_period(period1, tmp_path / "c.sqlite3", radios=[1])


def test_policy_can_leave_sectors_behind(period1, tmp_path):
    """Mechanics hold whatever the policy says: points follow their sectors, ids are kept."""
    report = open_next_period(period1, tmp_path / "op-02.sqlite3", completed_sectors=False)
    assert report.sectors == 1 and report.sector_points == 3   # only S5 (drawn, a triangle)
    with sqlite3.connect(tmp_path / "op-02.sqlite3") as c:
        assert c.execute("SELECT search_sector_id, name FROM search_sector").fetchall() == [(5, "S5")]
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
