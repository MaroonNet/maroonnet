"""The Alembic migrations must produce exactly the schema the models describe.

If this fails after a model change, run `alembic revision --autogenerate` and review the
result; if it fails after editing a migration by hand, the migration is wrong.
"""

import re
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from missiondb import create_db_engine, init_db
from missiondb.models import DEFAULT_MESSAGE_TYPES

BACKEND = Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    return cfg


def _schema(path: Path) -> dict[str, str]:
    """sqlite_master with whitespace, quoting and constraint order normalised."""
    out = {}
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'alembic%'"
        ).fetchall()
    for name, sql in rows:
        sql = re.sub(r"\s+", " ", sql).replace('"', "").strip()
        sql = re.sub(r"DEFAULT \(([^()]*)\)", r"DEFAULT \1", sql)  # SQLite rebuilds wrap defaults
        m = re.match(r"(CREATE TABLE \w+) \((.*)\)(.*)$", sql)
        if m:
            parts = sorted(p.strip() for p in re.split(r", (?=(?:[A-Za-z_]+ |CONSTRAINT ))", m.group(2)))
            sql = f"{m.group(1)} ({'; '.join(parts)}){m.group(3).strip()}"
        out[name] = sql
    return out


@pytest.fixture
def migrated(tmp_path, monkeypatch):
    path = tmp_path / "migrated.sqlite3"
    monkeypatch.setenv("MISSIONDB_URL", f"sqlite:///{path}")
    command.upgrade(_alembic_config(), "head")
    return path


def test_upgrade_head_matches_create_all(migrated, tmp_path):
    reference = tmp_path / "create_all.sqlite3"
    init_db(create_db_engine(f"sqlite:///{reference}"))
    assert _schema(migrated) == _schema(reference)


def test_upgrade_head_seeds_message_types(migrated):
    with sqlite3.connect(migrated) as conn:
        rows = set(conn.execute("SELECT type_code, description FROM message_type").fetchall())
    assert rows == set(DEFAULT_MESSAGE_TYPES)


def test_autogenerate_finds_no_drift(migrated, monkeypatch):
    """Models and head migration agree: a fresh autogenerate would be empty."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from missiondb.models import MissionBase

    engine = create_db_engine(f"sqlite:///{migrated}", enforce_foreign_keys=False)
    with engine.connect() as conn:
        ctx = MigrationContext.configure(
            conn, opts={"compare_type": True, "compare_server_default": True, "render_as_batch": True}
        )
        assert compare_metadata(ctx, MissionBase.metadata) == []


def test_downgrade_base_removes_everything(migrated):
    command.downgrade(_alembic_config(), "base")
    assert _schema(migrated) == {}


SEED = BACKEND / "missiondb" / "tests" / "fixtures" / "arizona07-v1-seed.sql"


def test_arizona07_seed_loads_at_0001_and_upgrades_to_head(tmp_path, monkeypatch):
    """The committed fixture's documented build path: upgrade 0001, load the seed, upgrade head.
    Every new migration must keep this working."""
    path = tmp_path / "arizona07.sqlite3"
    monkeypatch.setenv("MISSIONDB_URL", f"sqlite:///{path}")
    cfg = _alembic_config()
    command.upgrade(cfg, "0001")
    with sqlite3.connect(path) as conn:
        conn.executescript(SEED.read_text())
    before = _row_counts(path)
    command.upgrade(cfg, "head")
    after = _row_counts(path)
    before["message_type"] += 1  # 0002 adds 'found'
    assert {t: n for t, n in after.items() if t in before} == before, "rows lost or gained"
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT name FROM search_sector ORDER BY search_sector_id").fetchall() == [
            ("S1",), ("S2",), ("S3",), ("S4",), ("S5",)]
        assert "found" in {r[0] for r in conn.execute("SELECT type_code FROM message_type")}
        assert conn.execute("SELECT operational_period FROM mission").fetchone() == (1,)
        # the old search_sector.search_group_id values became assignment history
        assert conn.execute(
            "SELECT search_sector_id, search_group_id, to_time IS NULL FROM sector_assignment ORDER BY 1"
        ).fetchall() == [(1, 1, 0), (2, 3, 0), (3, 2, 0), (4, 3, 0)]
        assert "search_group_id" not in [r[1] for r in conn.execute("PRAGMA table_info(search_sector)")]
    assert _schema(path) == _schema(_create_all(tmp_path))


def test_arizona07_downgrade_restores_group_column(tmp_path, monkeypatch):
    path = tmp_path / "arizona07.sqlite3"
    monkeypatch.setenv("MISSIONDB_URL", f"sqlite:///{path}")
    cfg = _alembic_config()
    command.upgrade(cfg, "0001")
    with sqlite3.connect(path) as conn:
        conn.executescript(SEED.read_text())
        before = conn.execute("SELECT search_sector_id, search_group_id FROM search_sector ORDER BY 1").fetchall()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0001")
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT search_sector_id, search_group_id FROM search_sector ORDER BY 1").fetchall() == before


def _row_counts(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as conn:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'alembic%'")]
        return {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}


def _create_all(tmp_path: Path) -> Path:
    reference = tmp_path / "create_all.sqlite3"
    init_db(create_db_engine(f"sqlite:///{reference}"))
    return reference
