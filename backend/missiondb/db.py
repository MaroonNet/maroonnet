"""Engine and session plumbing for missiondb.

Everything that is SQLite-specific lives in this one file, so moving to PostgreSQL later
is a change here (and the MISSIONDB_URL value), not in the models or the callers.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

# One file per command post for now. Override with the MISSIONDB_URL environment variable,
# e.g.  MISSIONDB_URL=sqlite:////Users/me/missions/2026-10-23.sqlite3
#       MISSIONDB_URL=postgresql+psycopg://user:pass@host/missiondb
DEFAULT_URL = "sqlite:///missiondb.sqlite3"

_engine: Engine | None = None


def database_url() -> str:
    """The connection URL in use: MISSIONDB_URL if set, else DEFAULT_URL."""
    return os.environ.get("MISSIONDB_URL", DEFAULT_URL)


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _apply_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    """Run on every new SQLite connection.

    foreign_keys   SQLite ignores FOREIGN KEY constraints unless this is on. Without it the
                   relationships in the schema are documentation only.
    journal_mode   WAL lets the web app read while the bridge daemon writes.
    synchronous    NORMAL is the usual pairing with WAL: durable across application crashes,
                   a little faster than FULL.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def create_db_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    """Build an engine for `url` (default: database_url()).

    Use this directly when you need a second engine, e.g. a temporary file in a test.
    Most code should call get_engine() instead.
    """
    url = url or database_url()
    connect_args: dict = {}
    if _is_sqlite(url):
        # FastAPI may hand a connection to a different thread than the one that opened it.
        connect_args["check_same_thread"] = False
    engine = create_engine(url, echo=echo, connect_args=connect_args)
    if _is_sqlite(url):
        event.listen(engine, "connect", _apply_sqlite_pragmas)
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
    """
    with Session(get_engine()) as session:
        yield session


def init_db(engine: Engine | None = None) -> None:
    """Create every table from the models and insert the starting message types.

    For development and tests only. The real schema is managed by Alembic migrations so that
    an existing mission file can be upgraded in place.
    """
    from .models import DEFAULT_MESSAGE_TYPES, MessageType

    engine = engine or get_engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        existing = {code for (code,) in session.exec(select(MessageType.type_code))}
        for code, description in DEFAULT_MESSAGE_TYPES:
            if code not in existing:
                session.add(MessageType(type_code=code, description=description))
        session.commit()
