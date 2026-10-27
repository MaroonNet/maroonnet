"""missiondb tables, from "Mission Database (missiondb): Third Normal Form" v1.0 (Oct 23, 2026).

One SQLite file per mission; the mission table holds one row. Table and column names match
the 3NF document's Appendix A so the document and the code can be read side by side.

SQLModel does not derive CHECK constraints from Python types, so every rule in the document's
Section 4 appears here explicitly in a __table_args__ tuple. Three rules stay in application
code because a table cannot express them: a sector has at least three points; a group has at
most one sector in drawn or searching; a sent sector is never edited, only completed and
replaced.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Index, Text
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, Relationship, SQLModel

from .types import UTCDateTime

# Stable constraint names. Alembic needs a name to alter or drop a constraint later, and
# SQLite's batch migrations need names to recreate tables. A CheckConstraint below is given
# only the rule part of its name; the convention prefixes it, e.g. "corners" on search_area
# becomes ck_search_area_corners.
SQLModel.metadata.naming_convention = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _lat(col: str) -> CheckConstraint:
    return CheckConstraint(f"{col} BETWEEN -90 AND 90", name=f"{col}_range")


def _lon(col: str) -> CheckConstraint:
    return CheckConstraint(f"{col} BETWEEN -180 AND 180", name=f"{col}_range")


def _utc_column(*, primary_key: bool = False, nullable: bool = False) -> Column:
    return Column(UTCDateTime, primary_key=primary_key, nullable=nullable)


# --------------------------------------------------------------------------------------------
# Enumerations. Stored as short text with a CHECK constraint (native_enum=False), the same on
# SQLite and PostgreSQL, so adding a value later is an ordinary migration.
# --------------------------------------------------------------------------------------------


class SectorStatus(str, Enum):
    DRAWN = "drawn"            # red on the map
    SEARCHING = "searching"    # yellow: a team has entered
    COMPLETED = "completed"    # green: completed_time is set


class MessageDirection(str, Enum):
    IN = "in"    # from a radio to the command post
    OUT = "out"  # from the command post to a radio


def _enum_column(enum_cls: type[Enum], *, name: str, default: Enum | None = None) -> Column:
    return Column(
        SAEnum(
            enum_cls,
            native_enum=False,
            length=16,
            create_constraint=True,
            name=name,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        **({"server_default": default.value} if default is not None else {}),
    )


# --------------------------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------------------------


class Mission(SQLModel, table=True):
    __tablename__ = "mission"

    mission_id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(Text, nullable=False))
    start_time: datetime = Field(sa_column=_utc_column())
    end_time: datetime | None = Field(default=None, sa_column=_utc_column(nullable=True))

    search_areas: list["SearchArea"] = Relationship(back_populates="mission")


class SearchArea(SQLModel, table=True):
    """The commander's whole domain: a static rectangle in v1.

    search_area_point (3NF v1.0, held) is not built while the area is a rectangle. If it
    becomes a polygon it takes the same shape as search_sector_point.
    """

    __tablename__ = "search_area"
    __table_args__ = (
        _lat("min_lat"),
        _lon("min_lon"),
        _lat("max_lat"),
        _lon("max_lon"),
        CheckConstraint("min_lat < max_lat AND min_lon < max_lon", name="corners"),
    )

    search_area_id: int | None = Field(default=None, primary_key=True)
    mission_id: int = Field(foreign_key="mission.mission_id", nullable=False)
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    mission: Mission = Relationship(back_populates="search_areas")


class SearchGroup(SQLModel, table=True):
    """A set of teams (radios) that is assigned one search sector at a time."""

    __tablename__ = "search_group"

    search_group_id: int | None = Field(default=None, primary_key=True)

    teams: list["Team"] = Relationship(back_populates="search_group")
    search_sectors: list["SearchSector"] = Relationship(back_populates="search_group")


class Team(SQLModel, table=True):
    """One radio. Identified on the mesh by its Meshtastic node number."""

    __tablename__ = "team"

    team_id: int | None = Field(default=None, primary_key=True)
    node_num: int = Field(unique=True, nullable=False)
    mac_address: str = Field(sa_column=Column(Text, unique=True, nullable=False))
    active: bool = Field(
        default=False,
        sa_column=Column(
            Boolean(create_constraint=True, name="active"),
            nullable=False,
            server_default="0",
        ),
    )
    search_group_id: int | None = Field(default=None, foreign_key="search_group.search_group_id")

    search_group: SearchGroup | None = Relationship(back_populates="teams")
    searchers: list["Searcher"] = Relationship(back_populates="team")
    locations: list["Location"] = Relationship(back_populates="team")
    messages: list["Message"] = Relationship(back_populates="team")
    sector_entries: list["SectorEntry"] = Relationship(back_populates="team")


class Searcher(SQLModel, table=True):
    """A person. Carries at most one radio (team) at a time."""

    __tablename__ = "searcher"

    searcher_id: int | None = Field(default=None, primary_key=True)
    fname: str = Field(sa_column=Column(Text, nullable=False))
    lname: str = Field(sa_column=Column(Text, nullable=False))
    team_id: int | None = Field(default=None, foreign_key="team.team_id")

    team: Team | None = Relationship(back_populates="searchers")


class SearchSector(SQLModel, table=True):
    """A commander-drawn polygon assigned to one group. Completed sectors are replaced, not edited."""

    __tablename__ = "search_sector"
    __table_args__ = (
        CheckConstraint(
            "(status = 'completed') = (completed_time IS NOT NULL)",
            name="completed_time",
        ),
    )

    search_sector_id: int | None = Field(default=None, primary_key=True)
    search_group_id: int | None = Field(default=None, foreign_key="search_group.search_group_id")
    status: SectorStatus = Field(
        default=SectorStatus.DRAWN,
        sa_column=_enum_column(SectorStatus, name="status", default=SectorStatus.DRAWN),
    )
    created_time: datetime = Field(sa_column=_utc_column())
    completed_time: datetime | None = Field(default=None, sa_column=_utc_column(nullable=True))

    search_group: SearchGroup | None = Relationship(back_populates="search_sectors")
    points: list["SearchSectorPoint"] = Relationship(back_populates="search_sector")
    entries: list["SectorEntry"] = Relationship(back_populates="search_sector")


class SearchSectorPoint(SQLModel, table=True):
    """One vertex of a sector polygon. point_order starts at 1; a sector needs at least three."""

    __tablename__ = "search_sector_point"
    __table_args__ = (
        CheckConstraint("point_order >= 1", name="point_order"),
        _lat("lat"),
        _lon("lon"),
    )

    search_sector_id: int = Field(foreign_key="search_sector.search_sector_id", primary_key=True)
    point_order: int = Field(primary_key=True)
    lat: float
    lon: float

    search_sector: SearchSector = Relationship(back_populates="points")


class SectorEntry(SQLModel, table=True):
    """When a team first entered a sector. Turns the sector from drawn to searching."""

    __tablename__ = "sector_entry"

    team_id: int = Field(foreign_key="team.team_id", primary_key=True)
    search_sector_id: int = Field(foreign_key="search_sector.search_sector_id", primary_key=True)
    entered_time: datetime = Field(sa_column=_utc_column())

    team: Team = Relationship(back_populates="sector_entries")
    search_sector: SearchSector = Relationship(back_populates="entries")


class Location(SQLModel, table=True):
    """A position report from a radio. The AAR replays the mission from this table."""

    __tablename__ = "location"
    __table_args__ = (
        _lat("lat"),
        _lon("lon"),
        Index("ix_location_time", "time"),
        {"sqlite_with_rowid": False},  # key-only table: smaller and faster for (team_id, time)
    )

    team_id: int = Field(foreign_key="team.team_id", primary_key=True)
    time: datetime = Field(sa_column=_utc_column(primary_key=True))
    lat: float
    lon: float
    elevation: float | None = None

    team: Team = Relationship(back_populates="locations")


class MessageType(SQLModel, table=True):
    """Lookup table. Add a row to add a message type."""

    __tablename__ = "message_type"

    type_code: str = Field(sa_column=Column(Text, primary_key=True))
    description: str = Field(sa_column=Column(Text, nullable=False))


# The starting list from 3NF v1.0 Section 4. init_db() and the first migration insert these.
DEFAULT_MESSAGE_TYPES: tuple[tuple[str, str], ...] = (
    ("evidence", "Searcher reports a found item"),
    ("instruction", "Commander sends an order to a team"),
    ("out_of_sector", "Team has left its sector"),
    ("assignment", "Sector assigned to a group"),
)


class Message(SQLModel, table=True):
    __tablename__ = "message"
    __table_args__ = (Index("ix_message_time", "time"),)

    message_id: int | None = Field(default=None, primary_key=True)
    team_id: int = Field(foreign_key="team.team_id", nullable=False)
    time: datetime = Field(sa_column=_utc_column())
    direction: MessageDirection = Field(
        sa_column=_enum_column(MessageDirection, name="direction")
    )
    type_code: str = Field(
        sa_column=Column(Text, ForeignKey("message_type.type_code"), nullable=False)
    )
    text: str = Field(sa_column=Column(Text, nullable=False))

    team: Team = Relationship(back_populates="messages")
