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
