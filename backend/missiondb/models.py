"""missiondb tables, from "Mission Database (missiondb): Third Normal Form" v1.2.

One SQLite file per mission day; the mission table holds one row. Table and column names
match the 3NF document so the document and the code can be read side by side.

SQLModel does not derive CHECK constraints from Python types, so every rule in the document's
Constraints section appears here explicitly in a __table_args__ tuple.

Rules that stay in application code because a table cannot express them portably:
  - a sector has at least three points;
  - a completed sector is never reopened (writers guard UPDATEs with status <> 'completed');
  - a sector that has been sent over the mesh is never edited, only completed and replaced.

Dialect-specific pieces (grep "sqlite"): the UTC text-format CHECKs apply to SQLite only;
the partial unique indexes carry both a sqlite_where and a postgresql_where.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Text,
    false,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, Relationship, SQLModel

from .sqltypes import UTC_TEXT_GLOB, UTCDateTime


class MissionBase(SQLModel):
    """Base class for every missiondb table.

    Carries its own MetaData instead of the global SQLModel.metadata, so that mapdb or any
    other SQLModel user in the same process cannot end up inside a mission file, and so that
    Alembic can target exactly these tables (target_metadata = MissionBase.metadata).

    Stable constraint names: Alembic needs a name to alter or drop a constraint later, and
    SQLite's batch migrations need names to recreate tables. A CheckConstraint below is given
    only the rule part of its name; the convention prefixes it, e.g. "corners" on search_area
    becomes ck_search_area_corners.
    """

    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_N_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


# --------------------------------------------------------------------------------------------
# Constraint helpers
# --------------------------------------------------------------------------------------------


def _lat(col: str) -> CheckConstraint:
    return CheckConstraint(f"{col} BETWEEN -90 AND 90", name=f"{col}_range")


def _lon(col: str) -> CheckConstraint:
    return CheckConstraint(f"{col} BETWEEN -180 AND 180", name=f"{col}_range")


def _no_fix(lat: str, lon: str) -> CheckConstraint:
    """A radio with no GPS fix reports 0,0 (protobuf's default for a missing number)."""
    return CheckConstraint(f"NOT ({lat} = 0 AND {lon} = 0)", name="no_fix")


def _utc_text(col: str) -> CheckConstraint:
    """SQLite only: the column must hold exactly YYYY-MM-DDTHH:MM:SSZ (or NULL)."""
    return CheckConstraint(
        f"{col} IS NULL OR {col} GLOB '{UTC_TEXT_GLOB}'", name=f"{col}_utc_text"
    ).ddl_if(dialect="sqlite")


def _max_bytes(col: str, limit: int) -> tuple[CheckConstraint, CheckConstraint]:
    """`col` is at most `limit` bytes of UTF-8: the limit a Meshtastic packet field has.
    SQLite counts characters in length(); casting to BLOB counts bytes. PostgreSQL has
    octet_length(). One constraint per dialect, same name, so Alembic sees one rule."""
    return (
        CheckConstraint(
            f"{col} IS NULL OR length(CAST({col} AS BLOB)) <= {limit}", name=f"{col}_bytes"
        ).ddl_if(dialect="sqlite"),
        CheckConstraint(
            f"{col} IS NULL OR octet_length({col}) <= {limit}", name=f"{col}_bytes"
        ).ddl_if(dialect="postgresql"),
    )


def _utc_column(*, primary_key: bool = False, nullable: bool = False) -> Column:
    return Column(UTCDateTime, primary_key=primary_key, nullable=nullable)


def _enum_column(enum_cls: type[Enum], *, name: str, default: Enum | None = None) -> Column:
    """Short text with a CHECK constraint, the same on SQLite and PostgreSQL (no native ENUM),
    so adding a value later is an ordinary migration."""
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
# Enumerations
# --------------------------------------------------------------------------------------------


class SectorStatus(str, Enum):
    DRAWN = "drawn"            # red on the map; may or may not have a group yet
    SEARCHING = "searching"    # a team of the assigned group has entered (application rule)
    COMPLETED = "completed"    # green: completed_time is set; the row is history from here on


class MessageDirection(str, Enum):
    IN = "in"    # from a radio to the command post
    OUT = "out"  # from the command post to a radio


# --------------------------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------------------------


class Mission(MissionBase, table=True):
    """Exactly one row per file. A mission is one or more operational periods (a shift of
    work; a day, a night, a start/stop), each its own file: same mission_uuid and name,
    operational_period 1, 2, 3... Rows carried from one period into the next keep their
    ids (see carryover.py), so the AAR can stitch periods by id."""

    __tablename__ = "mission"
    __table_args__ = (
        CheckConstraint("mission_id = 1", name="single_row"),
        CheckConstraint("operational_period >= 1", name="operational_period"),
        _utc_text("start_time"),
        _utc_text("end_time"),
    )

    mission_id: int | None = Field(default=None, primary_key=True)
    mission_uuid: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        sa_column=Column(Text, unique=True, nullable=False),
    )
    name: str = Field(sa_column=Column(Text, nullable=False))
    operational_period: int = Field(
        default=1, sa_column=Column(Integer, nullable=False, server_default=text("1"))
    )
    start_time: datetime = Field(sa_column=_utc_column())
    end_time: datetime | None = Field(default=None, sa_column=_utc_column(nullable=True))

    search_areas: list["SearchArea"] = Relationship(back_populates="mission")


class SearchArea(MissionBase, table=True):
    """The commander's whole domain: a static rectangle in v1.

    search_area_point (3NF, held) is not built while the area is a rectangle. If it becomes
    a polygon it takes the same shape as search_sector_point.
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


class SearchGroup(MissionBase, table=True):
    """A set of teams (radios) that is assigned at most one open search sector at a time."""

    __tablename__ = "search_group"

    search_group_id: int | None = Field(default=None, primary_key=True)

    team_assignments: list["TeamGroupAssignment"] = Relationship(back_populates="search_group")
    sector_assignments: list["SectorAssignment"] = Relationship(back_populates="search_group")


class Team(MissionBase, table=True):
    """One radio. Identified on the mesh by its Meshtastic node number (unsigned 32-bit, so
    BigInteger: half of all node numbers exceed a signed 32-bit INTEGER on PostgreSQL).

    Which group the radio is in, and who carries it, are history tables
    (team_group_assignment, searcher_team_assignment), not columns here.
    """

    __tablename__ = "team"

    team_id: int | None = Field(default=None, primary_key=True)
    node_num: int = Field(sa_column=Column(BigInteger, unique=True, nullable=False))
    active: bool = Field(
        default=False,
        sa_column=Column(
            Boolean(create_constraint=True, name="active"),
            nullable=False,
            server_default=false(),
        ),
    )

    group_assignments: list["TeamGroupAssignment"] = Relationship(back_populates="team")
    searcher_assignments: list["SearcherTeamAssignment"] = Relationship(back_populates="team")
    locations: list["Location"] = Relationship(back_populates="team")
    messages: list["Message"] = Relationship(back_populates="team")
    sector_entries: list["SectorEntry"] = Relationship(back_populates="team")
    dispatches: list["SectorDispatch"] = Relationship(back_populates="team")
    waypoints: list["Waypoint"] = Relationship(back_populates="team")


class Searcher(MissionBase, table=True):
    """A person. Which radio they carry, and when, is searcher_team_assignment."""

    __tablename__ = "searcher"

    searcher_id: int | None = Field(default=None, primary_key=True)
    fname: str = Field(sa_column=Column(Text, nullable=False))
    lname: str = Field(sa_column=Column(Text, nullable=False))

    team_assignments: list["SearcherTeamAssignment"] = Relationship(back_populates="searcher")


class TeamGroupAssignment(MissionBase, table=True):
    """A radio's membership in a group over time. to_time NULL = current.

    Moving a radio to another group = set to_time on the open row and insert a new one, in
    one transaction. The partial unique index allows one open row per team.
    """

    __tablename__ = "team_group_assignment"
    __table_args__ = (
        CheckConstraint("to_time IS NULL OR to_time >= from_time", name="ordered"),
        _utc_text("from_time"),
        _utc_text("to_time"),
        Index(
            "ux_team_group_assignment_open",
            "team_id",
            unique=True,
            sqlite_where=text("to_time IS NULL"),
            postgresql_where=text("to_time IS NULL"),
        ),
    )

    assignment_id: int | None = Field(default=None, primary_key=True)
    team_id: int = Field(foreign_key="team.team_id", nullable=False)
    search_group_id: int = Field(foreign_key="search_group.search_group_id", nullable=False)
    from_time: datetime = Field(sa_column=_utc_column())
    to_time: datetime | None = Field(default=None, sa_column=_utc_column(nullable=True))

    team: Team = Relationship(back_populates="group_assignments")
    search_group: SearchGroup = Relationship(back_populates="team_assignments")


class SearcherTeamAssignment(MissionBase, table=True):
    """Who carried which radio, and when. to_time NULL = current.

    A searcher carries at most one radio at a time (partial unique index); a radio may be
    shared by several searchers.
    """

    __tablename__ = "searcher_team_assignment"
    __table_args__ = (
        CheckConstraint("to_time IS NULL OR to_time >= from_time", name="ordered"),
        _utc_text("from_time"),
        _utc_text("to_time"),
        Index(
            "ux_searcher_team_assignment_open",
            "searcher_id",
            unique=True,
            sqlite_where=text("to_time IS NULL"),
            postgresql_where=text("to_time IS NULL"),
        ),
    )

    assignment_id: int | None = Field(default=None, primary_key=True)
    searcher_id: int = Field(foreign_key="searcher.searcher_id", nullable=False)
    team_id: int = Field(foreign_key="team.team_id", nullable=False)
    from_time: datetime = Field(sa_column=_utc_column())
    to_time: datetime | None = Field(default=None, sa_column=_utc_column(nullable=True))

    searcher: Searcher = Relationship(back_populates="team_assignments")
    team: Team = Relationship(back_populates="searcher_assignments")


class SearchSector(MissionBase, table=True):
    """A commander-drawn polygon. Drawn freely, assigned to a group later or never.

    Which group holds it, and when, is sector_assignment (history, like the other assignment
    tables). A group holds at most one sector and a sector at most one group at a time; both
    are partial unique indexes on sector_assignment. Reassigning = close the open assignment
    and open the next, in one transaction. Carried into the next operational period, a sector
    keeps its id, name, points and status but arrives with no open assignment.

    On the mesh (Assignment Packet record v1.3) a sector is one port-256 packet carrying an
    assignment ID (0-65,535), a name of at most 20 UTF-8 bytes and 3-24 corners. The
    search_sector_id IS the assignment ID; the same ID sent again is a re-send, never new
    geometry (a sent sector is completed and replaced, not edited). Who it was sent to, and
    when, is sector_dispatch.
    """

    __tablename__ = "search_sector"
    __table_args__ = (
        CheckConstraint("search_sector_id BETWEEN 0 AND 65535", name="wire_id"),
        *_max_bytes("name", 20),
        CheckConstraint(
            "(status = 'completed') = (completed_time IS NOT NULL)", name="completed_time"
        ),
        _utc_text("created_time"),
        _utc_text("completed_time"),
        # Names are unique within a file (the command post auto-names S<id>); the empty
        # name is allowed on more than one unsaved row.
        Index(
            "ux_search_sector_name",
            "name",
            unique=True,
            sqlite_where=text("name <> ''"),
            postgresql_where=text("name <> ''"),
        ),
    )

    search_sector_id: int | None = Field(default=None, primary_key=True)
    name: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=text("''")))
    status: SectorStatus = Field(
        default=SectorStatus.DRAWN,
        sa_column=_enum_column(SectorStatus, name="status", default=SectorStatus.DRAWN),
    )
    created_time: datetime = Field(sa_column=_utc_column())
    completed_time: datetime | None = Field(default=None, sa_column=_utc_column(nullable=True))
    note: str | None = Field(default=None, sa_column=Column(Text, nullable=True))  # local only

    assignments: list["SectorAssignment"] = Relationship(back_populates="search_sector")
    points: list["SearchSectorPoint"] = Relationship(back_populates="search_sector")
    entries: list["SectorEntry"] = Relationship(back_populates="search_sector")
    dispatches: list["SectorDispatch"] = Relationship(back_populates="search_sector")


class SectorAssignment(MissionBase, table=True):
    """Which group holds which sector, and when. to_time NULL = current.

    One open assignment per sector and one per group (a group cannot be in two places).
    Completing a sector closes its assignment in the same transaction. Not carried between
    operational periods: the next period's commander assigns afresh.
    """

    __tablename__ = "sector_assignment"
    __table_args__ = (
        CheckConstraint("to_time IS NULL OR to_time >= from_time", name="ordered"),
        _utc_text("from_time"),
        _utc_text("to_time"),
        Index(
            "ux_sector_assignment_open_sector",
            "search_sector_id",
            unique=True,
            sqlite_where=text("to_time IS NULL"),
            postgresql_where=text("to_time IS NULL"),
        ),
        Index(
            "ux_sector_assignment_open_group",
            "search_group_id",
            unique=True,
            sqlite_where=text("to_time IS NULL"),
            postgresql_where=text("to_time IS NULL"),
        ),
        Index("ix_sector_assignment_search_group_id", "search_group_id"),
    )

    assignment_id: int | None = Field(default=None, primary_key=True)
    search_sector_id: int = Field(foreign_key="search_sector.search_sector_id", nullable=False)
    search_group_id: int = Field(foreign_key="search_group.search_group_id", nullable=False)
    from_time: datetime = Field(sa_column=_utc_column())
    to_time: datetime | None = Field(default=None, sa_column=_utc_column(nullable=True))

    search_sector: SearchSector = Relationship(back_populates="assignments")
    search_group: SearchGroup = Relationship(back_populates="sector_assignments")


class SearchSectorPoint(MissionBase, table=True):
    """One vertex of a sector polygon. point_order starts at 1; a sector needs three to
    twenty-four (the 24 is the packet limit and stays in application code). A (0,0) corner
    makes the phone drop the whole packet, so the database refuses it too."""

    __tablename__ = "search_sector_point"
    __table_args__ = (
        CheckConstraint("point_order >= 1", name="point_order"),
        _lat("lat"),
        _lon("lon"),
        _no_fix("lat", "lon"),
    )

    search_sector_id: int = Field(foreign_key="search_sector.search_sector_id", primary_key=True)
    point_order: int = Field(primary_key=True)
    lat: float
    lon: float

    search_sector: SearchSector = Relationship(back_populates="points")


class SectorEntry(MissionBase, table=True):
    """When a team first entered a sector. Turns the sector from drawn to searching.
    Re-entry is a no-op: writers insert with ON CONFLICT DO NOTHING."""

    __tablename__ = "sector_entry"
    __table_args__ = (_utc_text("entered_time"),)

    team_id: int = Field(foreign_key="team.team_id", primary_key=True)
    search_sector_id: int = Field(foreign_key="search_sector.search_sector_id", primary_key=True)
    entered_time: datetime = Field(sa_column=_utc_column())

    team: Team = Relationship(back_populates="sector_entries")
    search_sector: SearchSector = Relationship(back_populates="entries")


class SectorDispatch(MissionBase, table=True):
    """One send of a sector to one radio, as the command post does it: one direct packet per
    radio in the group, acknowledgement requested. A re-send is a new row with the same
    search_sector_id. ack_time stays NULL until the radio acknowledges."""

    __tablename__ = "sector_dispatch"
    __table_args__ = (
        CheckConstraint("ack_time IS NULL OR ack_time >= sent_time", name="ack_after_sent"),
        _utc_text("sent_time"),
        _utc_text("ack_time"),
        Index("ix_sector_dispatch_search_sector_id", "search_sector_id"),
        Index("ix_sector_dispatch_team_id", "team_id"),
    )

    dispatch_id: int | None = Field(default=None, primary_key=True)
    search_sector_id: int = Field(foreign_key="search_sector.search_sector_id", nullable=False)
    team_id: int = Field(foreign_key="team.team_id", nullable=False)
    sent_time: datetime = Field(sa_column=_utc_column())
    ack_time: datetime | None = Field(default=None, sa_column=_utc_column(nullable=True))
    packet_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )  # Meshtastic packet id (unsigned 32-bit) when the sender reports one

    search_sector: SearchSector = Relationship(back_populates="dispatches")
    team: Team = Relationship(back_populates="dispatches")


class Location(MissionBase, table=True):
    """A position report from a radio. The AAR replays the mission from this table.

    time     the radio's GPS clock: when the searcher was there.
    rx_time  the command post's clock: when the report arrived. Late minus lost is the
             difference between the two.

    One row per radio per second: the (team_id, time) key drops mesh rebroadcasts. Writers
    insert with ON CONFLICT DO NOTHING; a second, different report inside the same second is
    discarded by design (the GPS updates once a second).
    """

    __tablename__ = "location"
    __table_args__ = (
        _lat("lat"),
        _lon("lon"),
        _no_fix("lat", "lon"),
        _utc_text("time"),
        _utc_text("rx_time"),
        Index("ix_location_time", "time"),
        {"sqlite_with_rowid": False},  # key-only table: smaller and faster for (team_id, time)
    )

    team_id: int = Field(foreign_key="team.team_id", primary_key=True)
    time: datetime = Field(sa_column=_utc_column(primary_key=True))
    rx_time: datetime = Field(sa_column=_utc_column())
    lat: float
    lon: float
    elevation: float | None = None

    team: Team = Relationship(back_populates="locations")


class MessageType(MissionBase, table=True):
    """Lookup table. Add a row to add a message type."""

    __tablename__ = "message_type"

    type_code: str = Field(sa_column=Column(Text, primary_key=True))
    description: str = Field(sa_column=Column(Text, nullable=False))


# The starting list from the 3NF document. init_db() and the first migration insert these.
DEFAULT_MESSAGE_TYPES: tuple[tuple[str, str], ...] = (
    ("evidence", "Searcher reports a found item"),
    ("found", "Missing person located"),
    ("instruction", "Commander sends an order to a team"),
    ("out_of_sector", "Team has left its sector"),
    ("assignment", "Sector assigned to a group"),
)


class Message(MissionBase, table=True):
    """A text message to or from one radio.

    Known gaps, deferred by the team (Nov 3, 2026) until mesh messaging is designed: no
    packet id, so an inbound message heard twice is stored twice; no group recipient, so an
    outbound message to a whole group is one row per radio.
    """

    __tablename__ = "message"
    __table_args__ = (
        _utc_text("time"),
        _utc_text("rx_time"),
        Index("ix_message_time", "time"),
    )

    message_id: int | None = Field(default=None, primary_key=True)
    team_id: int = Field(foreign_key="team.team_id", nullable=False)
    time: datetime = Field(sa_column=_utc_column())
    rx_time: datetime = Field(sa_column=_utc_column())
    direction: MessageDirection = Field(
        sa_column=_enum_column(MessageDirection, name="direction")
    )
    type_code: str = Field(
        sa_column=Column(Text, ForeignKey("message_type.type_code"), nullable=False)
    )
    text: str = Field(sa_column=Column(Text, nullable=False))

    team: Team = Relationship(back_populates="messages")


class WaypointType(MissionBase, table=True):
    """Lookup table: the kinds of point a commander wants to see on the map. Add a row to
    add a kind."""

    __tablename__ = "waypoint_type"

    type_code: str = Field(sa_column=Column(Text, primary_key=True))
    description: str = Field(sa_column=Column(Text, nullable=False))


DEFAULT_WAYPOINT_TYPES: tuple[tuple[str, str], ...] = (
    ("find", "Missing person located"),
    ("evidence", "Evidence or clue found"),
    ("landing_zone", "Helicopter landing zone"),
    ("hazard", "Hazard to searchers (ice, avalanche, rubble)"),
    ("command_post", "Command post"),
    ("relay", "Stationary relay radio"),
    ("last_known_position", "Subject's last known position"),
    ("meeting_point", "Rendezvous for searchers"),
)


class Waypoint(MissionBase, table=True):
    """A point on the map that is not a radio position: a find, evidence, a landing zone,
    the command post. The commander's "VIP location data", kept apart from message noise.

    Where it comes from: placed by the commander (team_id and message_id NULL), or derived
    from a tagged message (message_id set, team_id = the radio that sent it, lat/lon from
    that radio's location at message.time). name, description, icon and expire_time are
    Meshtastic's own waypoint fields (port 8), so a row can be sent over the mesh as-is
    if the team ever decides to; note is local only.

    A moved or corrected waypoint is closed (removed_time) and re-added, like assignments,
    so the AAR can replay it appearing, moving and disappearing.
    """

    __tablename__ = "waypoint"
    __table_args__ = (
        _lat("lat"),
        _lon("lon"),
        _no_fix("lat", "lon"),
        *_max_bytes("name", 30),
        *_max_bytes("description", 100),
        CheckConstraint("removed_time IS NULL OR removed_time >= created_time", name="removed_after_created"),
        CheckConstraint("expire_time IS NULL OR expire_time >= created_time", name="expire_after_created"),
        _utc_text("time"),
        _utc_text("created_time"),
        _utc_text("expire_time"),
        _utc_text("removed_time"),
        Index("ix_waypoint_time", "time"),
    )

    waypoint_id: int | None = Field(default=None, primary_key=True)
    type_code: str = Field(
        sa_column=Column(Text, ForeignKey("waypoint_type.type_code"), nullable=False)
    )
    lat: float
    lon: float
    elevation: float | None = None
    time: datetime = Field(sa_column=_utc_column())  # when the thing happened or was seen
    created_time: datetime = Field(sa_column=_utc_column())  # when the row was saved
    team_id: int | None = Field(default=None, foreign_key="team.team_id")
    message_id: int | None = Field(default=None, foreign_key="message.message_id")
    name: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=text("''")))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    icon: str | None = Field(default=None, sa_column=Column(Text, nullable=True))  # emoji
    note: str | None = Field(default=None, sa_column=Column(Text, nullable=True))  # local only
    expire_time: datetime | None = Field(default=None, sa_column=_utc_column(nullable=True))
    removed_time: datetime | None = Field(default=None, sa_column=_utc_column(nullable=True))

    team: Team | None = Relationship(back_populates="waypoints")
    message: Message | None = Relationship()
