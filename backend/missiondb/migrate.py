"""Run Alembic from code, so the command post and tests do not shell out.

    from missiondb.migrate import upgrade, current
    upgrade("sqlite:///missions/arizona07/op-02.sqlite3")      # to head
    current("sqlite:///missions/arizona07/op-02.sqlite3")      # -> "0002"
"""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from .db import create_db_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]  # backend/, which holds alembic.ini


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return cfg


def head_revision() -> str:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def upgrade(url: str, revision: str = "head") -> None:
    """Bring the database at `url` to `revision`. env.py reads MISSIONDB_URL, so it is set
    for the duration of the call and restored afterwards."""
    previous = os.environ.get("MISSIONDB_URL")
    os.environ["MISSIONDB_URL"] = url
    try:
        command.upgrade(alembic_config(), revision)
    finally:
        if previous is None:
            del os.environ["MISSIONDB_URL"]
        else:
            os.environ["MISSIONDB_URL"] = previous


def current(url: str) -> str | None:
    """The revision stamped in the database at `url`, or None for an empty file."""
    engine = create_db_engine(url)
    try:
        with engine.connect() as conn:
            return MigrationContext.configure(conn).get_current_revision()
    finally:
        engine.dispose()
