"""MaroonNet mission database (missiondb).

Public surface:
    get_engine()   the process-wide SQLAlchemy engine (SQLite by default)
    get_session()  a Session generator, usable as a FastAPI dependency
    init_db()      create tables from the models (dev and tests; Alembic owns real schemas)
"""

from .db import DEFAULT_URL, create_db_engine, database_url, get_engine, get_session, init_db

__all__ = [
    "DEFAULT_URL",
    "create_db_engine",
    "database_url",
    "get_engine",
    "get_session",
    "init_db",
]
