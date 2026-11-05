"""Engine and session plumbing for missiondb.

Everything that is SQLite-specific lives in this one file. Moving to PostgreSQL is a change to
MISSIONDB_URL plus the dialect-specific pieces listed in models.py (search for "sqlite").
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine, select

# One SQLite file per mission day, under a missions/ directory the app owns:
#     missions/<mission>/<day>.sqlite3
# The app chooses the path; this default is for development only. Override with
#     MISSIONDB_URL=sqlite:////absolute/path/to/file.sqlite3
#     MISSIONDB_URL=postgresql+psycopg://user:pass@host/missiondb
DEFAULT_URL = "sqlite:///missions/dev.sqlite3"

# How long a writer waits for a lock before failing. The bridge daemon and the FastAPI app are
# two processes writing the same file; 5 s (the sqlite3 default) is too short under WAL
# checkpoints and long imports from the field app.
SQLITE_BUSY_TIMEOUT_S = 30

_engine: Engine | None = None


def database_url() -> str:
    """The connection URL in use: MISSIONDB_URL if set, else DEFAULT_URL."""
    return os.environ.get("MISSIONDB_URL", DEFAULT_URL)


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _sqlite_file(url: str) -> Path | None:
    """The file behind a sqlite:/// URL, or None for :memory: and non-SQLite URLs."""
    if not _is_sqlite(url):
        return None
    path = url.removeprefix("sqlite:///")
    if path in ("", ":memory:") or path.startswith("file:"):
        return None
    return Path(path)


def _make_pragma_listener(enforce_foreign_keys: bool):
    def apply(dbapi_connection, _connection_record) -> None:
        """Run on every new SQLite connection.

        foreign_keys   SQLite ignores FOREIGN KEY constraints unless this is on. Without it the
                       relationships in the schema are documentation only.
        journal_mode   WAL lets the web app read while the bridge daemon writes.
        synchronous    NORMAL is the usual pairing with WAL: durable across application
                       crashes, a little faster than FULL.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute(f"PRAGMA foreign_keys={'ON' if enforce_foreign_keys else 'OFF'}")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return apply


def create_db_engine(
    url: str | None = None,
    *,
    echo: bool = False,
    enforce_foreign_keys: bool = True,
) -> Engine:
    """Build an engine for `url` (default: database_url()).

    enforce_foreign_keys=False is for Alembic only. SQLite cannot ALTER most things, so a
    migration drops and recreates a table ("move and copy"); with foreign keys enforced the
    DROP of any referenced table fails. The migration environment opens its engine with this
    off and runs PRAGMA foreign_key_check at the end. Application code never passes it.

    echo=True logs every statement with its parameters, i.e. searcher names and positions.
    Development only.

    Most code should call get_engine() instead of this.
    """
    url = url or database_url()
    connect_args: dict = {}
    if _is_sqlite(url):
        # FastAPI may hand a connection to a different thread than the one that opened it.
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = SQLITE_BUSY_TIMEOUT_S
        if (path := _sqlite_file(url)) is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, echo=echo, connect_args=connect_args)
    if _is_sqlite(url):
        event.listen(engine, "connect", _make_pragma_listener(enforce_foreign_keys))
    return engine


def get_engine() -> Engine:
    """The process-wide engine, created on first use."""
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session() -> Iterator[Session]:
    """Yield a Session and close it afterwards.

    FastAPI:   def route(session: Session = Depends(get_session)): ...
    Elsewhere: with Session(get_engine()) as session: ...

    Keep write transactions short: the file has one writer at a time.
    """
    with Session(get_engine()) as session:
        yield session


def init_db(engine: Engine | None = None) -> None:
    """Create every missiondb table and insert the starting message types.

    For development and tests only. The real schema is managed by Alembic migrations
    (target_metadata = MissionBase.metadata) so that an existing mission file can be upgraded
    in place.
    """
    from .models import DEFAULT_MESSAGE_TYPES, MessageType, MissionBase

    engine = engine or get_engine()
    MissionBase.metadata.create_all(engine)
    with Session(engine) as session:
        existing = set(session.exec(select(MessageType.type_code)).all())
        for code, description in DEFAULT_MESSAGE_TYPES:
            if code not in existing:
                session.add(MessageType(type_code=code, description=description))
        session.commit()
