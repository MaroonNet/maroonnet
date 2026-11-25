"""The sector tests use the mission tests' made-up mission files, with a few helpers of their own."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from mission.tests.conftest import (  # noqa: F401  (pytest finds these helpers by name)
    arizona07, arizona07_file, client, clock, empty_file, make_mission, open_bear_creek,
)

# Bear Creek's search area, and a square sector well inside it. Corners are latitude, longitude.
BEAR_CREEK_AREA = {"min_lat": 39.9, "min_lon": -105.7, "max_lat": 40.1, "max_lon": -105.5}
SQUARE = [(40.0, -105.6), (40.05, -105.6), (40.05, -105.55), (40.0, -105.55)]


def corners(*points: tuple[float, float]) -> dict:
    """A request body for a sector's shape."""
    return {"corners": [{"lat": lat, "lon": lon} for lat, lon in points]}


@pytest.fixture
def bear_creek(client, open_bear_creek):
    """Opens Bear Creek in the status asked for, with its search area saved, and answers with
    its file. The area is written straight into the file, since a paused or ended session
    refuses to save one."""

    def make(status: str = "planning") -> Path:
        path = open_bear_creek(status)
        write(path, f"""
            INSERT INTO search_area (mission_id, min_lat, min_lon, max_lat, max_lon)
            VALUES (1, {BEAR_CREEK_AREA['min_lat']}, {BEAR_CREEK_AREA['min_lon']},
                    {BEAR_CREEK_AREA['max_lat']}, {BEAR_CREEK_AREA['max_lon']});
        """)
        return path

    return make


def write(path: Path, sql: str) -> None:
    """Writes rows straight into a mission file, for a state no route makes yet."""
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(sql)
        connection.commit()


def add_sector(path: Path, sector_id: int, status: str = "drawn") -> None:
    """Writes a square sector straight into a mission file."""
    completed = "'2026-11-20T18:00:00Z'" if status == "completed" else "NULL"
    points = ", ".join(f"({sector_id}, {order}, {lat}, {lon})" for order, (lat, lon) in enumerate(SQUARE, start=1))
    write(path, f"""
        INSERT INTO search_sector (search_sector_id, name, status, created_time, completed_time)
        VALUES ({sector_id}, 'S{sector_id}', '{status}', '2026-11-20T16:00:00Z', {completed});
        INSERT INTO search_sector_point (search_sector_id, point_order, lat, lon) VALUES {points};
    """)


def assign(path: Path, sector_id: int, released: bool = False) -> None:
    """Gives a sector to group 1, as D7's Assign will. released: the group has since let it go."""
    to_time = "'2026-11-20T17:00:00Z'" if released else "NULL"
    write(path, f"""
        INSERT OR IGNORE INTO search_group (search_group_id) VALUES (1);
        INSERT INTO sector_assignment (search_sector_id, search_group_id, from_time, to_time)
        VALUES ({sector_id}, 1, '2026-11-20T16:30:00Z', {to_time});
    """)
