"""Column types shared by the models.

Named sqltypes, not types: a module called types.py shadows the standard library's `types`
module for any interpreter started inside this directory and breaks `typing` before
SQLAlchemy even loads.
"""

from datetime import datetime, timezone

from sqlalchemy.dialects.sqlite import DATETIME as SQLiteDateTime
from sqlalchemy.types import DateTime, TypeDecorator

# How a timestamp is written inside a SQLite file: 2026-10-23T21:15:00Z (ISO 8601, UTC, whole
# seconds). Lexical order equals time order, so range queries and ORDER BY work on the text.
#
# Reading is deliberately looser than writing. Any writer that bypasses the ORM (a sqlite3
# cursor using datetime('now'), a CSV import) may produce "2026-10-23 21:15:00",
# ".500Z" fractions or "+00:00" suffixes; one such row must not make every read of the table
# raise. All of these are read as UTC. The strict shape is still enforced on write by the
# UTC_TEXT_GLOB check constraint in models.py.
_SQLITE_ISO_8601_UTC = SQLiteDateTime(
    storage_format="%(year)04d-%(month)02d-%(day)02dT%(hour)02d:%(minute)02d:%(second)02dZ",
    regexp=r"(\d+)-(\d+)-(\d+)[T ](\d+):(\d+):(\d+)(?:\.\d+)?(?:Z|\+00:00)?",
)

# SQLite GLOB pattern matching exactly the storage format above. Used by models.py to reject
# any other shape at insert time (SQLite only; PostgreSQL has a real timestamp type).
UTC_TEXT_GLOB = "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z"


class UTCDateTime(TypeDecorator):
    """A timezone-aware datetime that is always UTC, at whole-second precision.

    SQLite      stored as ISO 8601 text with a Z suffix (format above).
    PostgreSQL  TIMESTAMP WITH TIME ZONE.

    Sub-second precision is dropped on every dialect, not only SQLite, so that behaviour that
    depends on time equality (the location table's (team_id, time) key) is the same wherever
    the file lives. The radios' clock is one second anyway.

    Writing a naive datetime raises, so a local time can never slip in by accident. The UI
    converts to local time for display only.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(_SQLITE_ISO_8601_UTC)
        return dialect.type_descriptor(DateTime(timezone=True))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                "missiondb timestamps must be timezone-aware; use datetime.now(timezone.utc)"
            )
        return value.astimezone(timezone.utc).replace(microsecond=0)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def utcnow() -> datetime:
    """The current time, timezone-aware, in UTC, whole seconds. Use for every timestamp default."""
    return datetime.now(timezone.utc).replace(microsecond=0)
