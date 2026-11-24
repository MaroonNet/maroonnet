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
    DEFAULT_WAYPOINT_TYPES,
    Location,
    Message,
    MessageAddressing,
    MessageDirection,
    MessageType,
    Mission,
    MissionBase,
    MissionStatus,
    SearchArea,
    Searcher,
    SearcherCheckin,
    SearcherTeamAssignment,
    SearchGroup,
    SearchSector,
    SearchSectorPoint,
    SectorAssignment,
    SectorDispatch,
    SectorEntry,
    SectorStatus,
    Team,
    TeamGroupAssignment,
    TeamKind,
    Waypoint,
    WaypointType,
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
        "search_sector_point", "sector_entry", "sector_dispatch", "sector_assignment",
        "location", "message_type", "message", "waypoint_type", "waypoint", "searcher_checkin",
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
    assert "WHERE to_time IS NULL" in ddl
    assert "active BOOLEAN DEFAULT false" in ddl


def test_message_types_seeded(session):
    rows = session.exec(select(MessageType)).all()
    assert {(r.type_code, r.description) for r in rows} == set(DEFAULT_MESSAGE_TYPES)


# ---- timestamps -------------------------------------------------------------------------


def test_timestamps_stored_as_iso_8601_utc(session):
    session.add(Mission(name="Lost hiker", status=MissionStatus.ACTIVE, start_time=T0))
    session.commit()
    assert session.exec(text("SELECT start_time FROM mission")).one()[0] == "2026-10-23T21:15:00Z"
    mission = session.exec(select(Mission)).one()
    assert mission.start_time == T0 and mission.start_time.tzinfo is not None


def test_naive_timestamp_rejected(session):
    session.add(Mission(name="x", status=MissionStatus.ACTIVE, start_time=datetime(2026, 10, 23, 21, 15)))
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
    session.add(Mission(name="day 1", status=MissionStatus.ACTIVE, start_time=T0))
    session.commit()
    session.add(Mission(name="day 1 again", status=MissionStatus.ACTIVE, start_time=T0))
    with _rejects(session):
        session.commit()


def test_mission_uuid_generated_per_mission(session, tmp_path):
    m = Mission(name="day 1", status=MissionStatus.ACTIVE, start_time=T0)
    assert len(m.mission_uuid) == 36
    assert m.mission_uuid != Mission(name="other", status=MissionStatus.ACTIVE, start_time=T0).mission_uuid
    session.add(m)
    session.commit()
    day1_uuid = session.exec(select(Mission.mission_uuid)).one()
    # Day 2 is a second file carrying the same uuid, so the AAR can stitch the days.
    day2 = create_db_engine(f"sqlite:///{tmp_path / 'day2.sqlite3'}")
    init_db(day2)
    with Session(day2) as s2:
        s2.add(Mission(name="day 2", status=MissionStatus.ACTIVE, start_time=T0 + timedelta(days=1), mission_uuid=day1_uuid))
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


def test_sector_status_default_is_drawn(session):
    session.add(SearchSector(name="S1", created_time=T0))
    session.add(SearchSector(name="S2", created_time=T0))  # unassigned sectors are unlimited
    session.commit()
    assert all(s.status == SectorStatus.DRAWN for s in session.exec(select(SearchSector)))


def test_completed_sector_needs_completed_time(session):
    session.add(SearchSector(name="S1", status=SectorStatus.COMPLETED, created_time=T0))
    with _rejects(session):
        session.commit()


def test_completed_time_needs_completed_status(session):
    session.add(SearchSector(name="S1", status=SectorStatus.SEARCHING, created_time=T0, completed_time=T0))
    with _rejects(session):
        session.commit()


def _sector(session, name) -> SearchSector:
    sector = SearchSector(name=name, created_time=T0)
    session.add(sector)
    session.commit()
    session.refresh(sector)
    return sector


def test_group_holds_one_sector_at_a_time(session):
    group = _group(session)
    s1, s2 = _sector(session, "S1"), _sector(session, "S2")
    session.add(SectorAssignment(search_sector_id=s1.search_sector_id,
                                 search_group_id=group.search_group_id, from_time=T0))
    session.commit()
    session.add(SectorAssignment(search_sector_id=s2.search_sector_id,
                                 search_group_id=group.search_group_id, from_time=T0))
    with _rejects(session):
        session.commit()
    session.rollback()
    # Reassignment: close the open assignment, open the next, one transaction.
    current = session.exec(select(SectorAssignment)).one()
    current.to_time = T0 + timedelta(hours=2)
    session.add(SectorAssignment(search_sector_id=s2.search_sector_id,
                                 search_group_id=group.search_group_id,
                                 from_time=T0 + timedelta(hours=2)))
    session.commit()
    history = session.exec(select(SectorAssignment).order_by(SectorAssignment.from_time)).all()
    assert [(a.search_sector_id, a.to_time is None) for a in history] == [
        (s1.search_sector_id, False), (s2.search_sector_id, True)]
    assert session.get(SearchSector, s2.search_sector_id).assignments[0].search_group.search_group_id == group.search_group_id


def test_sector_held_by_one_group_at_a_time(session):
    g1, g2 = _group(session), _group(session)
    s1 = _sector(session, "S1")
    session.add(SectorAssignment(search_sector_id=s1.search_sector_id, search_group_id=g1.search_group_id, from_time=T0))
    session.commit()
    session.add(SectorAssignment(search_sector_id=s1.search_sector_id, search_group_id=g2.search_group_id, from_time=T0))
    with _rejects(session):
        session.commit()


def test_mission_operational_period(session):
    session.add(Mission(name="m", status=MissionStatus.ACTIVE, start_time=T0))
    session.commit()
    assert session.exec(select(Mission)).one().operational_period == 1
    session.exec(text("DELETE FROM mission"))
    session.add(Mission(mission_id=1, name="m", status=MissionStatus.ACTIVE, start_time=T0, operational_period=0))
    with _rejects(session):
        session.commit()


def test_sector_entry_reentry_is_a_no_op(session):
    team, group = _team(session), _group(session)
    sector = SearchSector(name="S1", created_time=T0)
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
    session.add(Mission(name="m", status=MissionStatus.ACTIVE, start_time=T0))
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


# ---- assignment packet alignment (record v1.3) ------------------------------------------


def test_sector_id_is_the_wire_id(session):
    session.add(SearchSector(search_sector_id=65535, name="S65535", created_time=T0))
    session.commit()
    session.add(SearchSector(search_sector_id=65536, name="too big", created_time=T0))
    with _rejects(session):
        session.commit()


def test_sector_name_limited_to_20_bytes(session):
    session.add(SearchSector(name="Sector B2", created_time=T0))
    session.commit()
    session.add(SearchSector(name="x" * 21, created_time=T0))
    with _rejects(session):
        session.commit()
    session.rollback()
    session.add(SearchSector(name="é" * 11, created_time=T0))  # 11 chars, 22 bytes
    with _rejects(session):
        session.commit()


def test_sector_corner_at_origin_rejected(session):
    sector = SearchSector(name="S9", created_time=T0)
    session.add(sector)
    session.commit()
    session.add(SearchSectorPoint(search_sector_id=sector.search_sector_id, point_order=1, lat=0.0, lon=0.0))
    with _rejects(session):
        session.commit()


def test_dispatch_records_each_radio_and_ack(session):
    team, group = _team(session), _group(session)
    sector = SearchSector(name="S4", created_time=T0)
    session.add(sector)
    session.commit()
    session.add(SectorDispatch(search_sector_id=sector.search_sector_id, team_id=team.team_id,
                               sent_time=T0, packet_id=0xFFFFFFFF))
    session.commit()
    d = session.exec(select(SectorDispatch)).one()
    assert d.ack_time is None and d.packet_id == 0xFFFFFFFF
    d.ack_time = T0 - timedelta(seconds=1)
    with _rejects(session):
        session.commit()
    session.rollback()
    # a re-send is a second row for the same sector and radio
    session.add(SectorDispatch(search_sector_id=sector.search_sector_id, team_id=team.team_id,
                               sent_time=T0 + timedelta(minutes=2)))
    session.commit()
    assert len(session.exec(select(SectorDispatch)).all()) == 2


# ---- waypoints -------------------------------------------------------------------------


def test_waypoint_types_seeded(session):
    rows = session.exec(select(WaypointType)).all()
    assert {(r.type_code, r.description) for r in rows} == set(DEFAULT_WAYPOINT_TYPES)
    assert "found" in {t for (t,) in [(m.type_code,) for m in session.exec(select(MessageType)).all()]}


def test_waypoint_from_commander_and_from_message(session):
    team = _team(session)
    session.add(Waypoint(type_code="command_post", lat=39.74, lon=-104.99, time=T0,
                         created_time=T0, name="CP", note="moved closer at 14:00"))
    msg = Message(team_id=team.team_id, time=T0 + timedelta(hours=2), rx_time=T0 + timedelta(hours=2),
                  direction=MessageDirection.IN, type_code="found", text="subject located")
    session.add(msg)
    session.commit()
    session.add(Waypoint(type_code="find", lat=39.75, lon=-104.98, time=msg.time,
                         created_time=msg.rx_time, team_id=team.team_id, message_id=msg.message_id))
    session.commit()
    found = session.exec(select(Waypoint).where(Waypoint.type_code == "find")).one()
    assert found.message.text == "subject located" and found.team.node_num == NODE


def test_waypoint_rules(session):
    base = dict(type_code="hazard", lat=39.74, lon=-104.99, time=T0, created_time=T0)
    for bad, label in (
        (dict(base, lat=0.0, lon=0.0), "no fix"),
        (dict(base, type_code="treasure"), "unknown type"),
        (dict(base, name="n" * 31), "name > 30 bytes"),
        (dict(base, description="d" * 101), "description > 100 bytes"),
        (dict(base, removed_time=T0 - timedelta(seconds=1)), "removed before created"),
        (dict(base, expire_time=T0 - timedelta(seconds=1)), "expires before created"),
    ):
        session.add(Waypoint(**bad))
        with _rejects(session):
            session.commit()
        session.rollback()


def test_waypoint_move_is_close_and_readd(session):
    first = Waypoint(type_code="command_post", lat=39.74, lon=-104.99, time=T0, created_time=T0, name="CP")
    session.add(first)
    session.commit()
    first.removed_time = T0 + timedelta(hours=5)
    session.add(Waypoint(type_code="command_post", lat=39.70, lon=-104.95, time=T0 + timedelta(hours=5),
                         created_time=T0 + timedelta(hours=5), name="CP"))
    session.commit()
    rows = session.exec(select(Waypoint).order_by(Waypoint.created_time)).all()
    assert [r.removed_time is None for r in rows] == [False, True]


def test_sector_names_unique_when_set(session):
    session.add(SearchSector(name="S1", created_time=T0))
    session.add(SearchSector(created_time=T0))   # unnamed rows may repeat
    session.add(SearchSector(created_time=T0))
    session.commit()
    session.add(SearchSector(name="S1", created_time=T0))
    with _rejects(session):
        session.commit()


# ---- 3NF v1.3: mission status, radio kinds, partial sectors, acks, check-in -------------------


def test_mission_starts_in_planning_without_a_start_time(session):
    session.add(Mission(name="m"))
    session.commit()
    m = session.exec(select(Mission)).one()
    assert (m.status, m.start_time, m.end_time, m.time_zone) == (MissionStatus.PLANNING, None, None, "UTC")


def test_mission_status_and_times_move_together(session):
    m = Mission(name="m", time_zone="America/Phoenix")
    session.add(m)
    session.commit()

    m.status = MissionStatus.ACTIVE                      # started but no start_time
    with _rejects(session):
        session.commit()
    session.rollback()
    m = session.exec(select(Mission)).one()
    m.status, m.start_time = MissionStatus.ACTIVE, T0
    session.commit()

    m.status = MissionStatus.ENDED                       # ended but no end_time
    with _rejects(session):
        session.commit()
    session.rollback()
    m = session.exec(select(Mission)).one()
    m.status, m.end_time = MissionStatus.PAUSED, T0 + timedelta(hours=8)
    session.commit()
    m.status = MissionStatus.ENDED                       # paused -> ended keeps the end_time
    session.commit()

    m.status, m.end_time = MissionStatus.ACTIVE, None    # a mistaken End, undone
    session.commit()
    m.end_time = T0 + timedelta(hours=9)                 # active with an end_time
    with _rejects(session):
        session.commit()


def test_mission_planning_with_a_start_time_rejected(session):
    session.add(Mission(name="m", start_time=T0))
    with _rejects(session):
        session.commit()


def test_mission_time_zone_not_empty(session):
    session.add(Mission(name="m", time_zone=""))
    with _rejects(session):
        session.commit()


def test_team_kind(session):
    assert _team(session).kind == TeamKind.SEARCHER
    session.add(Team(node_num=NODE + 1, kind=TeamKind.COMMAND_POST))
    session.add(Team(node_num=NODE + 2, kind=TeamKind.RELAY))
    session.commit()
    with _rejects(session):
        session.execute(text("INSERT INTO team (node_num, kind) VALUES (7, 'dormant')"))


def test_partial_sector_has_no_completed_time_and_can_resume(session):
    s = _sector(session, "S1")
    s.status = SectorStatus.PARTIAL
    session.commit()
    s.completed_time = T0
    with _rejects(session):
        session.commit()
    session.rollback()
    s = session.get(SearchSector, s.search_sector_id)
    s.status = SectorStatus.SEARCHING                    # a group goes back in
    session.commit()
    s.status, s.completed_time = SectorStatus.COMPLETED, T0
    session.commit()


def test_message_ack_and_packet_id(session):
    team = _team(session)
    m = Message(team_id=team.team_id, time=T0, rx_time=T0, direction=MessageDirection.OUT,
                type_code="instruction", text="return to CP", packet_id=0xFFFFFFFF)
    session.add(m)
    session.commit()
    assert (m.addressing, m.batch_id, m.ack_time) == (MessageAddressing.DIRECT, None, None)
    m.ack_time = T0 + timedelta(seconds=9)
    session.commit()
    assert session.get(Message, m.message_id).packet_id == 0xFFFFFFFF
    m.ack_time = T0 - timedelta(seconds=1)
    with _rejects(session):
        session.commit()


def test_broadcast_is_one_row_per_radio_sharing_a_batch(session):
    a = _team(session)
    b = Team(node_num=NODE + 1)
    session.add(b)
    session.commit()
    first = Message(team_id=a.team_id, time=T0, rx_time=T0, direction=MessageDirection.OUT,
                    type_code="instruction", text="all teams return", addressing=MessageAddressing.BROADCAST,
                    batch_id=1)
    session.add(first)
    session.add(Message(team_id=b.team_id, time=T0, rx_time=T0, direction=MessageDirection.OUT,
                        type_code="instruction", text="all teams return",
                        addressing=MessageAddressing.BROADCAST, batch_id=1,
                        ack_time=T0 + timedelta(seconds=5)))
    session.commit()
    acked = session.exec(text("SELECT count(*), count(ack_time) FROM message WHERE batch_id = 1")).one()
    assert tuple(acked) == (2, 1)
    # a shared send needs a batch_id, and a direct message must not have one
    with _rejects(session):
        session.execute(text(
            "INSERT INTO message (team_id, time, rx_time, direction, type_code, text, addressing) "
            f"VALUES ({a.team_id}, '2026-10-23T21:15:00Z', '2026-10-23T21:15:00Z', 'out', 'instruction', 'x', 'multicast')"))
    session.rollback()
    with _rejects(session):
        session.execute(text(
            "INSERT INTO message (team_id, time, rx_time, direction, type_code, text, batch_id) "
            f"VALUES ({a.team_id}, '2026-10-23T21:15:00Z', '2026-10-23T21:15:00Z', 'out', 'instruction', 'x', 9)"))


def test_searcher_check_in_and_out(session):
    person = Searcher(fname="Ada", lname="Lovelace")
    session.add(person)
    session.commit()
    first = SearcherCheckin(searcher_id=person.searcher_id, in_time=T0)
    session.add(first)
    session.commit()
    session.add(SearcherCheckin(searcher_id=person.searcher_id, in_time=T0 + timedelta(hours=1)))
    with _rejects(session):                              # already checked in
        session.commit()
    session.rollback()
    first = session.get(SearcherCheckin, first.checkin_id)
    first.out_time = T0 + timedelta(hours=6)             # checked out
    session.commit()
    session.add(SearcherCheckin(searcher_id=person.searcher_id, in_time=T0 + timedelta(hours=20)))
    session.commit()                                     # back the next day: a new row
    assert len(session.get(Searcher, person.searcher_id).checkins) == 2
    first.out_time = T0 - timedelta(hours=1)
    with _rejects(session):
        session.commit()


def test_new_waypoint_types_seeded(session):
    codes = set(session.exec(select(WaypointType.type_code)).all())
    assert {"point_last_seen", "other", "last_known_position"} <= codes
