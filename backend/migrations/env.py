"""Alembic environment for missiondb.

Run from backend/:
    uv run alembic upgrade head                       # bring the file at MISSIONDB_URL up to date
    uv run alembic revision --autogenerate -m "..."   # after editing missiondb/models.py
    uv run alembic current / history

The target is MissionBase.metadata only, never the global SQLModel metadata, so tables from
other packages in this process cannot end up in a mission file.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

from missiondb.db import create_db_engine, database_url
from missiondb.models import MissionBase

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = MissionBase.metadata


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it (alembic upgrade head --sql)."""
    url = database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_is_sqlite(url),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = database_url()
    sqlite = _is_sqlite(url)
    # Foreign keys OFF for the migration connection: SQLite cannot ALTER most things, so a
    # change is "move and copy" (batch mode), which drops and recreates the table; with
    # foreign keys enforced the DROP of any referenced table fails. Integrity is checked
    # explicitly at the end instead.
    engine = create_db_engine(url, enforce_foreign_keys=False)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=sqlite,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        if sqlite:
            violations = connection.execute(text("PRAGMA foreign_key_check")).fetchall()
            if violations:
                raise RuntimeError(f"foreign key violations after migration: {violations[:10]}")
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
