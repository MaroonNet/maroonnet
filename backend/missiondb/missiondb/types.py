"""Column types shared by the models."""

from datetime import datetime, timezone

from sqlalchemy.dialects.sqlite import DATETIME as SQLiteDateTime
from sqlalchemy.types import DateTime, TypeDecorator

# How a timestamp looks inside a SQLite file: 2026-10-23T21:15:00Z (ISO 8601, UTC, seconds).
# Lexical order equals time order, so range queries and ORDER BY work on the text.
_SQLITE_ISO_8601_UTC = SQLiteDateTime(
    storage_format="%(year)04d-%(month)02d-%(day)02dT%(hour)02d:%(minute)02d:%(second)02dZ",
    regexp=r"(\d+)-(\d+)-(\d+)T(\d+):(\d+):(\d+)Z",
)


class UTCDateTime(TypeDecorator):
    """A timezone-aware datetime that is always UTC.

    SQLite      stored as ISO 8601 text with a Z suffix (format above); sub-second precision
                is dropped, which matches the radios' one-second clock.
    PostgreSQL  TIMESTAMP WITH TIME ZONE.

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
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def utcnow() -> datetime:
    """The current time, timezone-aware, in UTC. Use this for every timestamp default."""
    return datetime.now(timezone.utc)
