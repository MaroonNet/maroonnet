"""Sector export against a fresh mission database. Made-up sectors, no real mission data."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session

from mapdb import sectors
from missiondb import create_db_engine, init_db
from missiondb.models import SearchGroup, SearchSector, SearchSectorPoint, SectorStatus

T0 = datetime(2026, 10, 23, 21, 15, 0, tzinfo=timezone.utc)
SQUARE = [(31.50, -110.70), (31.50, -110.69), (31.51, -110.69), (31.51, -110.70)]  # lat, lon


@pytest.fixture
def engine(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'mission.sqlite3'}")
    init_db(engine)
    return engine


@pytest.fixture
def session(engine):
    """Three sectors: 1 completed, 2 completed, 3 still only drawn."""
    with Session(engine) as session:
        for sector_id, status in ((1, SectorStatus.COMPLETED), (2, SectorStatus.COMPLETED),
                                  (3, SectorStatus.DRAWN)):
            done = status is SectorStatus.COMPLETED
            session.add(SearchGroup(search_group_id=sector_id))
            session.add(SearchSector(
                search_sector_id=sector_id, search_group_id=sector_id, status=status,
                created_time=T0, completed_time=T0 + timedelta(hours=1) if done else None,
            ))
            session.flush()
            # stored out of order: the export must sort by point_order
            for order in (3, 1, 4, 2):
                lat, lon = SQUARE[order - 1]
                session.add(SearchSectorPoint(search_sector_id=sector_id, point_order=order,
                                              lat=lat, lon=lon + sector_id))
        session.commit()
        yield session


def test_completed_sectors_become_closed_polygons(session):
    collection = sectors.sectors_geojson(session, pod=0.5)
    assert [f["id"] for f in collection["features"]] == [1, 2]  # the drawn sector is left out
    ring = collection["features"][0]["geometry"]["coordinates"][0]
    assert ring == [[lon + 1, lat] for lat, lon in SQUARE] + [[SQUARE[0][1] + 1, SQUARE[0][0]]]
    assert collection["features"][0]["properties"] == {"id": 1, "status": "completed", "pod": 0.5}


def test_a_sector_can_have_its_own_pod_or_none(session):
    features = sectors.sectors_geojson(session, pod_by_sector={2: 0.8})["features"]
    assert "pod" not in features[0]["properties"]  # spm reports this one as ignored
    assert features[1]["properties"]["pod"] == 0.8
    features = sectors.sectors_geojson(session, pod=0.5, pod_by_sector={2: 0.8})["features"]
    assert [f["properties"]["pod"] for f in features] == [0.5, 0.8]


def test_other_statuses_on_request(session):
    collection = sectors.sectors_geojson(session, statuses=(SectorStatus.DRAWN,))
    assert [f["id"] for f in collection["features"]] == [3]


def test_a_pod_outside_0_to_1_is_refused(session):
    with pytest.raises(ValueError, match="between 0 and 1"):
        sectors.sectors_geojson(session, pod=50)


def test_command_writes_the_file(engine, session, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sectors, "get_engine", lambda: engine)
    out = tmp_path / "searched.geojson"
    sectors.main(["--pod", "0.5", "--pod-for", "2=0.8", "--out", str(out)])
    features = json.loads(out.read_text())["features"]
    assert [f["properties"]["pod"] for f in features] == [0.5, 0.8]
    assert "2 sectors written" in capsys.readouterr().out
