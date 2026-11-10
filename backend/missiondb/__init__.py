"""MaroonNet mission database (missiondb).

Public surface:
    get_engine()   the process-wide SQLAlchemy engine (SQLite by default)
    get_session()  a Session generator, usable as a FastAPI dependency
    init_db()      create tables from the models (dev and tests; Alembic owns real schemas)
    models         the tables; MissionBase.metadata is the schema
"""

from .db import DEFAULT_URL, create_db_engine, database_url, get_engine, get_session, init_db
from .models import MissionBase

__all__ = [
    "DEFAULT_URL",
    "MissionBase",
    "create_db_engine",
    "database_url",
    "get_engine",
    "get_session",
    "init_db",
]
