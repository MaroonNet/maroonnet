"""Schema checks for missiondb against a fresh SQLite file.

These are the rejections the 3NF v1.0 document says it tested against its DDL, run here
against the SQLModel tables so the two cannot drift apart unnoticed.
"""

import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from missiondb import create_db_engine, init_db
from missiondb.models import (
    DEFAULT_MESSAGE_TYPES,
    Location,
    Message,
    MessageDirection,
    MessageType,
    Mission,
    SearchArea,
    SearchGroup,
    SearchSector,
    SectorStatus,
    Team,
)

T0 = datetime(2026, 10, 23, 21, 15, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'mission.sqlite3'}")
    init_db(engine)
    return engine


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


def _team(session, node_num=0x1A2B3C4D, mac="aa:bb:cc:dd:ee:ff") -> Team:
    team = Team(node_num=node_num, mac_address=mac)
    session.add(team)
    session.commit()
    session.refresh(team)
    return team


def test_pragmas_are_on(session):
    assert session.exec(text("PRAGMA foreign_keys")).one()[0] == 1
    assert session.exec(text("PRAGMA journal_mode")).one()[0] == "wal"


def test_constraint_names_follow_convention(session):
    names = set()
    for (sql,) in session.exec(text("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")):
        names |= set(re.findall(r'CONSTRAINT "?(\w+)"?', sql))
    assert "ck_search_sector_status" in names
    assert "ck_message_direction" in names
    assert "ck_location_lat_range" in names
    assert "uq_team_node_num" in names
    assert not any("_ck_" in n for n in names)  # no doubled prefixes


def test_all_tables_exist(session):
    names = {
        row[0]
        for row in session.exec(text("SELECT name FROM sqlite_master WHERE type='table'"))
    }
    assert names >= {
        "mission", "search_area", "search_group", "team", "searcher", "search_sector",
        "search_sector_point", "sector_entry", "location", "message_type", "message",
    }
    assert "search_area_point" not in names  # held in 3NF v1.0


def test_message_types_seeded(session):
    rows = session.exec(select(MessageType)).all()
    assert {(r.type_code, r.description) for r in rows} == set(DEFAULT_MESSAGE_TYPES)


def test_timestamps_stored_as_iso_8601_utc(session):
    session.add(Mission(name="Lost hiker", start_time=T0))
    session.commit()
    raw = session.exec(text("SELECT start_time FROM mission")).one()[0]
    assert raw == "2026-10-23T21:15:00Z"
    mission = session.exec(select(Mission)).one()
    assert mission.start_time == T0
    assert mission.start_time.tzinfo is not None


def test_naive_timestamp_rejected(session):
    session.add(Mission(name="x", start_time=datetime(2026, 10, 23, 21, 15)))
    with pytest.raises(Exception, match="timezone-aware"):
        session.commit()


def test_completed_sector_needs_completed_time(session):
    session.add(SearchSector(status=SectorStatus.COMPLETED, created_time=T0))
    with pytest.raises(IntegrityError):
        session.commit()


def test_completed_time_needs_completed_status(session):
    session.add(SearchSector(status=SectorStatus.SEARCHING, created_time=T0, completed_time=T0))
    with pytest.raises(IntegrityError):
        session.commit()


def test_sector_status_default_is_drawn(session):
    session.add(SearchSector(created_time=T0))
    session.commit()
    assert session.exec(select(SearchSector)).one().status == SectorStatus.DRAWN


def test_duplicate_node_num_rejected(session):
    _team(session)
    session.add(Team(node_num=0x1A2B3C4D, mac_address="11:22:33:44:55:66"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_bad_direction_rejected(session):
    team = _team(session)
    with pytest.raises(IntegrityError):
        session.exec(
            text(
                "INSERT INTO message (team_id, time, direction, type_code, text) "
                "VALUES (:t, '2026-10-23T21:15:00Z', 'sideways', 'evidence', 'hi')"
            ).bindparams(t=team.team_id)
        )


def test_unknown_message_type_rejected(session):
    team = _team(session)
    session.add(
        Message(team_id=team.team_id, time=T0, direction=MessageDirection.IN,
                type_code="gossip", text="hi")
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_duplicate_team_and_time_location_rejected(session):
    team = _team(session)
    session.add(Location(team_id=team.team_id, time=T0, lat=39.74, lon=-104.99))
    session.commit()
    session.add(Location(team_id=team.team_id, time=T0, lat=39.75, lon=-104.98))
    with pytest.raises(IntegrityError):
        session.commit()


def test_location_out_of_range_rejected(session):
    team = _team(session)
    session.add(Location(team_id=team.team_id, time=T0, lat=95.0, lon=-104.99))
    with pytest.raises(IntegrityError):
        session.commit()


def test_location_for_unknown_team_rejected(session):
    session.add(Location(team_id=999, time=T0, lat=39.74, lon=-104.99))
    with pytest.raises(IntegrityError):
        session.commit()


def test_search_area_corners(session):
    session.add(Mission(name="m", start_time=T0))
    session.commit()
    session.add(SearchArea(mission_id=1, min_lat=40.0, min_lon=-105.0, max_lat=39.0, max_lon=-104.0))
    with pytest.raises(IntegrityError):
        session.commit()


def test_time_range_query_orders_correctly(session):
    team = _team(session)
    for i in (3, 1, 2):
        session.add(Location(team_id=team.team_id, time=T0 + timedelta(seconds=i), lat=39.0, lon=-105.0))
    session.commit()
    rows = session.exec(
        select(Location).where(Location.time <= T0 + timedelta(seconds=2)).order_by(Location.time)
    ).all()
    assert [r.time for r in rows] == [T0 + timedelta(seconds=1), T0 + timedelta(seconds=2)]
    assert session.get(Team, team.team_id).search_group is None
    group = SearchGroup()
    session.add(group)
    session.commit()
    team.search_group_id = group.search_group_id
    session.commit()
    assert session.get(SearchGroup, group.search_group_id).teams[0].node_num == 0x1A2B3C4D
