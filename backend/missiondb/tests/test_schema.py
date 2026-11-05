"""Schema checks for missiondb against a fresh SQLite file, plus a PostgreSQL DDL compile.

Every rule the 3NF document states is exercised here, so the document, the models and the
engines cannot drift apart unnoticed.
"""

import re
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlmodel import Session, select

from missiondb import create_db_engine, init_db
from missiondb.models import (
    DEFAULT_MESSAGE_TYPES,
    Location,
    Message,
    MessageDirection,
    MessageType,
    Mission,
    MissionBase,
    SearchArea,
    Searcher,
    SearcherTeamAssignment,
    SearchGroup,
    SearchSector,
    SectorEntry,
    SectorStatus,
    Team,
    TeamGroupAssignment,
)

T0 = datetime(2026, 10, 23, 21, 15, 0, tzinfo=timezone.utc)
NODE = 0xDEADBEEF  # > 2**31: must survive a signed 32-bit INTEGER column


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "mission.sqlite3"


@pytest.fixture
def engine(db_path):
    engine = create_db_engine(f"sqlite:///{db_path}")
    init_db(engine)
    return engine


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


def _team(session, node_num=NODE) -> Team:
    team = Team(node_num=node_num)
    session.add(team)
    session.commit()
    session.refresh(team)
    return team


def _group(session) -> SearchGroup:
    group = SearchGroup()
    session.add(group)
    session.commit()
    session.refresh(group)
    return group


def _rejects(session):
    return pytest.raises(IntegrityError)


# ---- engine and file --------------------------------------------------------------------


def test_pragmas_are_on(session):
    assert session.exec(text("PRAGMA foreign_keys")).one()[0] == 1
    assert session.exec(text("PRAGMA journal_mode")).one()[0] == "wal"


def test_engine_can_disable_foreign_keys_for_migrations(db_path):
    engine = create_db_engine(f"sqlite:///{db_path}", enforce_foreign_keys=False)
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).one()[0] == 0


def test_engine_creates_parent_directory(tmp_path):
    path = tmp_path / "missions" / "m1" / "day1.sqlite3"
    engine = create_db_engine(f"sqlite:///{path}")
    init_db(engine)
    assert path.exists()


def test_init_db_is_idempotent(engine):
    init_db(engine)
    with Session(engine) as s:
        assert len(s.exec(select(MessageType)).all()) == len(DEFAULT_MESSAGE_TYPES)


# ---- schema shape -----------------------------------------------------------------------


def test_all_tables_exist(session):
    names = {
        row[0]
        for row in session.exec(text("SELECT name FROM sqlite_master WHERE type='table'"))
    }
    assert names == {
        "mission", "search_area", "search_group", "team", "searcher",
        "team_group_assignment", "searcher_team_assignment", "search_sector",
        "search_sector_point", "sector_entry", "location", "message_type", "message",
    }


def test_models_use_their_own_metadata():
    from sqlmodel import SQLModel

    assert "location" in MissionBase.metadata.tables
    assert "location" not in SQLModel.metadata.tables


def test_constraint_names_follow_convention(session):
    names = set()
    for (sql,) in session.exec(text("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")):
        names |= set(re.findall(r'CONSTRAINT "?(\w+)"?', sql))
    assert {"ck_search_sector_status", "ck_message_direction", "ck_location_lat_range",
            "ck_location_no_fix", "ck_mission_single_row", "uq_team_node_num",
            "ck_location_time_utc_text"} <= names
    assert not any("_ck_" in n for n in names)


def test_postgresql_ddl_compiles_for_every_table():
    dialect = postgresql.dialect()
    ddl = ""
    for table in MissionBase.metadata.sorted_tables:
        ddl += str(CreateTable(table).compile(dialect=dialect))
        for index in table.indexes:
            ddl += str(CreateIndex(index).compile(dialect=dialect))
    assert "node_num BIGINT" in ddl
    assert "TIMESTAMP WITH TIME ZONE" in ddl
    assert "GLOB" not in ddl  # the text-format checks are SQLite-only
    assert "WHERE status IN ('drawn', 'searching')" in ddl
    assert "active BOOLEAN DEFAULT false" in ddl


def test_message_types_seeded(session):
    rows = session.exec(select(MessageType)).all()
    assert {(r.type_code, r.description) for r in rows} == set(DEFAULT_MESSAGE_TYPES)


# ---- timestamps -------------------------------------------------------------------------


def test_timestamps_stored_as_iso_8601_utc(session):
    session.add(Mission(name="Lost hiker", start_time=T0))
    session.commit()
    assert session.exec(text("SELECT start_time FROM mission")).one()[0] == "2026-10-23T21:15:00Z"
    mission = session.exec(select(Mission)).one()
    assert mission.start_time == T0 and mission.start_time.tzinfo is not None


def test_naive_timestamp_rejected(session):
    session.add(Mission(name="x", start_time=datetime(2026, 10, 23, 21, 15)))
    with pytest.raises(StatementError, match="timezone-aware"):
        session.commit()


def test_sub_second_truncated_on_bind(session):
    team = _team(session)
    session.add(Location(team_id=team.team_id, time=T0 + timedelta(milliseconds=200),
                         rx_time=T0, lat=39.74, lon=-104.99))
    session.commit()
    assert session.exec(select(Location)).one().time == T0


def test_foreign_timestamp_formats_are_readable(engine, db_path):
    with Session(engine) as s:
        _team(s)
    raw = sqlite3.connect(db_path)
    raw.execute("PRAGMA foreign_keys=ON")
    # Only the exact storage format passes the SQLite CHECK on write ...
    for bad in ("2026-10-23 21:15:00", "2026-10-23T21:15:00.500Z", "2026-10-23T21:15:00+00:00"):
        with pytest.raises(sqlite3.IntegrityError):
            raw.execute("INSERT INTO location VALUES (1, ?, ?, 39.7, -105.0, NULL)", (bad, bad))
    raw.close()
    # ... but the reader still tolerates them in a file written by older or foreign tools.
    from missiondb.sqltypes import _SQLITE_ISO_8601_UTC

    proc = _SQLITE_ISO_8601_UTC.result_processor(engine.dialect, None)
    for shape in ("2026-10-23 21:15:00", "2026-10-23T21:15:00.500Z", "2026-10-23T21:15:00+00:00"):
        assert proc(shape).replace(tzinfo=timezone.utc) == T0


# ---- mission ----------------------------------------------------------------------------


def test_one_mission_row_per_file(session):
    session.add(Mission(name="day 1", start_time=T0))
    session.commit()
    session.add(Mission(name="day 1 again", start_time=T0))
    with _rejects(session):
        session.commit()


def test_mission_uuid_generated_per_mission(session, tmp_path):
    m = Mission(name="day 1", start_time=T0)
    assert len(m.mission_uuid) == 36
    assert m.mission_uuid != Mission(name="other", start_time=T0).mission_uuid
    session.add(m)
    session.commit()
    day1_uuid = session.exec(select(Mission.mission_uuid)).one()
    # Day 2 is a second file carrying the same uuid, so the AAR can stitch the days.
    day2 = create_db_engine(f"sqlite:///{tmp_path / 'day2.sqlite3'}")
    init_db(day2)
    with Session(day2) as s2:
        s2.add(Mission(name="day 2", start_time=T0 + timedelta(days=1), mission_uuid=day1_uuid))
        s2.commit()
        assert s2.exec(select(Mission.mission_uuid)).one() == day1_uuid


# ---- team, searcher, assignments --------------------------------------------------------


def test_node_num_above_signed_32_bit_roundtrips(session):
    team = _team(session, node_num=NODE)
    assert session.get(Team, team.team_id).node_num == NODE


def test_duplicate_node_num_rejected(session):
    _team(session)
    session.add(Team(node_num=NODE))
    with _rejects(session):
        session.commit()


def test_team_has_one_open_group_assignment(session):
    team, g1, g2 = _team(session), _group(session), _group(session)
    session.add(TeamGroupAssignment(team_id=team.team_id, search_group_id=g1.search_group_id,
                                    from_time=T0))
    session.commit()
    session.add(TeamGroupAssignment(team_id=team.team_id, search_group_id=g2.search_group_id,
                                    from_time=T0 + timedelta(hours=1)))
    with _rejects(session):
        session.commit()
    session.rollback()
    # Moving the radio: close the open row, then open the next one.
    current = session.exec(select(TeamGroupAssignment)).one()
    current.to_time = T0 + timedelta(hours=1)
    session.add(TeamGroupAssignment(team_id=team.team_id, search_group_id=g2.search_group_id,
                                    from_time=T0 + timedelta(hours=1)))
    session.commit()
    history = session.exec(select(TeamGroupAssignment).order_by(TeamGroupAssignment.from_time)).all()
    assert [(a.search_group_id, a.to_time is None) for a in history] == [
        (g1.search_group_id, False), (g2.search_group_id, True)]


def test_searcher_carries_one_radio_at_a_time(session):
    t1, t2 = _team(session, NODE), _team(session, NODE + 1)
    s = Searcher(fname="Ada", lname="Lovelace")
    session.add(s)
    session.commit()
    session.add(SearcherTeamAssignment(searcher_id=s.searcher_id, team_id=t1.team_id, from_time=T0))
    session.commit()
    session.add(SearcherTeamAssignment(searcher_id=s.searcher_id, team_id=t2.team_id, from_time=T0))
    with _rejects(session):
        session.commit()


def test_assignment_end_before_start_rejected(session):
    team, group = _team(session), _group(session)
    session.add(TeamGroupAssignment(team_id=team.team_id, search_group_id=group.search_group_id,
                                    from_time=T0, to_time=T0 - timedelta(seconds=1)))
    with _rejects(session):
        session.commit()


# ---- sectors ----------------------------------------------------------------------------


def test_sector_status_default_is_drawn_and_group_optional(session):
    session.add(SearchSector(created_time=T0))
    session.add(SearchSector(created_time=T0))  # unassigned sectors are unlimited
    session.commit()
    assert all(s.status == SectorStatus.DRAWN for s in session.exec(select(SearchSector)))


def test_completed_sector_needs_completed_time(session):
    group = _group(session)
    session.add(SearchSector(search_group_id=group.search_group_id,
                             status=SectorStatus.COMPLETED, created_time=T0))
    with _rejects(session):
        session.commit()


def test_completed_time_needs_completed_status(session):
    group = _group(session)
    session.add(SearchSector(search_group_id=group.search_group_id,
                             status=SectorStatus.SEARCHING, created_time=T0, completed_time=T0))
    with _rejects(session):
        session.commit()


def test_searching_sector_needs_a_group(session):
    session.add(SearchSector(status=SectorStatus.SEARCHING, created_time=T0))
    with _rejects(session):
        session.commit()


def test_group_has_at_most_one_open_sector(session):
    group = _group(session)
    gid = group.search_group_id
    session.add(SearchSector(search_group_id=gid, status=SectorStatus.COMPLETED,
                             created_time=T0, completed_time=T0))
    session.add(SearchSector(search_group_id=gid, created_time=T0))
    session.commit()
    session.add(SearchSector(search_group_id=gid, status=SectorStatus.SEARCHING, created_time=T0))
    with _rejects(session):
        session.commit()
    session.rollback()
    # Reassignment: complete the open one and assign the next, in one transaction.
    open_sector = session.exec(select(SearchSector).where(SearchSector.status == SectorStatus.DRAWN)).one()
    open_sector.status = SectorStatus.COMPLETED
    open_sector.completed_time = T0 + timedelta(hours=2)
    session.add(SearchSector(search_group_id=gid, created_time=T0 + timedelta(hours=2)))
    session.commit()
    assert len(session.exec(select(SearchSector)).all()) == 3


def test_sector_entry_reentry_is_a_no_op(session):
    team, group = _team(session), _group(session)
    sector = SearchSector(search_group_id=group.search_group_id, created_time=T0)
    session.add(sector)
    session.commit()
    stmt = sqlite_insert(SectorEntry.__table__).values(
        team_id=team.team_id, search_sector_id=sector.search_sector_id, entered_time=T0
    ).on_conflict_do_nothing()
    session.exec(stmt)
    stmt = sqlite_insert(SectorEntry.__table__).values(
        team_id=team.team_id, search_sector_id=sector.search_sector_id,
        entered_time=T0 + timedelta(minutes=5),
    ).on_conflict_do_nothing()
    session.exec(stmt)
    session.commit()
    entries = session.exec(select(SectorEntry)).all()
    assert len(entries) == 1 and entries[0].entered_time == T0


# ---- location ---------------------------------------------------------------------------


def test_location_requires_both_clocks(session):
    team = _team(session)
    with pytest.raises(Exception):
        session.add(Location(team_id=team.team_id, time=T0, lat=39.74, lon=-104.99))
        session.commit()


def test_duplicate_team_and_time_location_rejected(session):
    team = _team(session)
    session.add(Location(team_id=team.team_id, time=T0, rx_time=T0, lat=39.74, lon=-104.99))
    session.commit()
    session.add(Location(team_id=team.team_id, time=T0, rx_time=T0, lat=39.75, lon=-104.98))
    with _rejects(session):
        session.commit()


def test_rebroadcast_dropped_with_on_conflict_do_nothing(session):
    team = _team(session)
    for _ in range(2):
        stmt = sqlite_insert(Location.__table__).values(
            team_id=team.team_id, time=T0, rx_time=T0 + timedelta(seconds=8),
            lat=39.74, lon=-104.99,
        ).on_conflict_do_nothing()
        session.exec(stmt)
    session.commit()
    assert len(session.exec(select(Location)).all()) == 1


def test_location_out_of_range_rejected(session):
    team = _team(session)
    session.add(Location(team_id=team.team_id, time=T0, rx_time=T0, lat=95.0, lon=-104.99))
    with _rejects(session):
        session.commit()


def test_location_without_gps_fix_rejected(session):
    team = _team(session)
    session.add(Location(team_id=team.team_id, time=T0, rx_time=T0, lat=0.0, lon=0.0))
    with _rejects(session):
        session.commit()


def test_location_for_unknown_team_rejected(session):
    session.add(Location(team_id=999, time=T0, rx_time=T0, lat=39.74, lon=-104.99))
    with _rejects(session):
        session.commit()


def test_time_range_query_orders_correctly(session):
    team = _team(session)
    for i in (3, 1, 2):
        session.add(Location(team_id=team.team_id, time=T0 + timedelta(seconds=i),
                             rx_time=T0 + timedelta(seconds=i + 8), lat=39.0, lon=-105.0))
    session.commit()
    rows = session.exec(
        select(Location).where(Location.time <= T0 + timedelta(seconds=2)).order_by(Location.time)
    ).all()
    assert [r.time for r in rows] == [T0 + timedelta(seconds=1), T0 + timedelta(seconds=2)]


# ---- search area and messages -----------------------------------------------------------


def test_search_area_corners(session):
    session.add(Mission(name="m", start_time=T0))
    session.commit()
    session.add(SearchArea(mission_id=1, min_lat=40.0, min_lon=-105.0, max_lat=39.0, max_lon=-104.0))
    with _rejects(session):
        session.commit()


def test_bad_direction_rejected(session):
    team = _team(session)
    with _rejects(session):
        session.exec(text(
            "INSERT INTO message (team_id, time, rx_time, direction, type_code, text) "
            "VALUES (:t, '2026-10-23T21:15:00Z', '2026-10-23T21:15:00Z', 'sideways', 'evidence', 'hi')"
        ).bindparams(t=team.team_id))


def test_unknown_message_type_rejected(session):
    team = _team(session)
    session.add(Message(team_id=team.team_id, time=T0, rx_time=T0,
                        direction=MessageDirection.IN, type_code="gossip", text="hi"))
    with _rejects(session):
        session.commit()


def test_relationships_navigate(session):
    team, group = _team(session), _group(session)
    session.add(TeamGroupAssignment(team_id=team.team_id, search_group_id=group.search_group_id,
                                    from_time=T0))
    session.commit()
    assert session.get(SearchGroup, group.search_group_id).team_assignments[0].team.node_num == NODE
