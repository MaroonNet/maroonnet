"""assignments and waypoints (3NF v1.2)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-19

Aligns missiondb with the Assignment Packet decision record v1.3 (Diego, Elijah) and adds
waypoints:
  - search_sector: name (<= 20 UTF-8 bytes, the packet's name, unique when set), note (local only),
    search_sector_id capped at 65,535 because it is the packet's assignment ID.
    Existing rows with no name are backfilled as S<id>.
  - search_sector_point: no (0, 0) corner (the phone drops such a packet).
  - sector_dispatch: one row per radio per send, with ack time and packet id.
  - waypoint_type + waypoint: points on the map that are not radio positions.
  - message_type: 'found'.
  - mission: operational_period (1, 2, 3...; files of one mission share mission_uuid).
  - sector_assignment: which group holds which sector, and when (history). The former
    search_sector.search_group_id becomes one assignment row per assigned sector
    (from_time = created_time, to_time = completed_time) and the column is dropped, with its
    partial unique index and the 'searching needs group' CHECK.

The *_utc_text and *_bytes CHECKs are dialect-specific: SQLite uses GLOB and
length(CAST(x AS BLOB)); PostgreSQL has a real timestamp type and octet_length().
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import missiondb.sqltypes
from missiondb.sqltypes import UTC_TEXT_GLOB

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _utc_text(col: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        f"{col} IS NULL OR {col} GLOB '{UTC_TEXT_GLOB}'", name=op.f(f"ck_%(table)s_{col}_utc_text")
    ).ddl_if(dialect="sqlite")


def _bytes_expr(col: str, limit: int, dialect: str) -> str:
    if dialect == "sqlite":
        return f"{col} IS NULL OR length(CAST({col} AS BLOB)) <= {limit}"
    return f"{col} IS NULL OR octet_length({col}) <= {limit}"


def upgrade() -> None:
    dialect = op.get_context().dialect.name

    # ---- waypoint_type ------------------------------------------------------------------
    waypoint_type = op.create_table(
        "waypoint_type",
        sa.Column("type_code", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("type_code", name=op.f("pk_waypoint_type")),
    )
    # Frozen here on purpose (see 0001): later additions to the models' default list are
    # their own migrations.
    op.bulk_insert(
        waypoint_type,
        [
            {"type_code": "find", "description": "Missing person located"},
            {"type_code": "evidence", "description": "Evidence or clue found"},
            {"type_code": "landing_zone", "description": "Helicopter landing zone"},
            {"type_code": "hazard", "description": "Hazard to searchers (ice, avalanche, rubble)"},
            {"type_code": "command_post", "description": "Command post"},
            {"type_code": "relay", "description": "Stationary relay radio"},
            {"type_code": "last_known_position", "description": "Subject's last known position"},
            {"type_code": "meeting_point", "description": "Rendezvous for searchers"},
        ],
    )

    # ---- sector_dispatch ----------------------------------------------------------------
    op.create_table(
        "sector_dispatch",
        sa.Column("dispatch_id", sa.Integer(), nullable=False),
        sa.Column("search_sector_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("sent_time", missiondb.sqltypes.UTCDateTime(timezone=True), nullable=False),
        sa.Column("ack_time", missiondb.sqltypes.UTCDateTime(timezone=True), nullable=True),
        sa.Column("packet_id", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "ack_time IS NULL OR ack_time >= sent_time", name=op.f("ck_sector_dispatch_ack_after_sent")
        ),
        sa.CheckConstraint(
            f"sent_time IS NULL OR sent_time GLOB '{UTC_TEXT_GLOB}'",
            name=op.f("ck_sector_dispatch_sent_time_utc_text"),
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            f"ack_time IS NULL OR ack_time GLOB '{UTC_TEXT_GLOB}'",
            name=op.f("ck_sector_dispatch_ack_time_utc_text"),
        ).ddl_if(dialect="sqlite"),
        sa.ForeignKeyConstraint(
            ["search_sector_id"], ["search_sector.search_sector_id"],
            name=op.f("fk_sector_dispatch_search_sector_id_search_sector"),
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["team.team_id"], name=op.f("fk_sector_dispatch_team_id_team")
        ),
        sa.PrimaryKeyConstraint("dispatch_id", name=op.f("pk_sector_dispatch")),
    )
    with op.batch_alter_table("sector_dispatch") as batch_op:
        batch_op.create_index("ix_sector_dispatch_search_sector_id", ["search_sector_id"])
        batch_op.create_index("ix_sector_dispatch_team_id", ["team_id"])

    # ---- waypoint -----------------------------------------------------------------------
    op.create_table(
        "waypoint",
        sa.Column("waypoint_id", sa.Integer(), nullable=False),
        sa.Column("type_code", sa.Text(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("elevation", sa.Float(), nullable=True),
        sa.Column("time", missiondb.sqltypes.UTCDateTime(timezone=True), nullable=False),
        sa.Column("created_time", missiondb.sqltypes.UTCDateTime(timezone=True), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("expire_time", missiondb.sqltypes.UTCDateTime(timezone=True), nullable=True),
        sa.Column("removed_time", missiondb.sqltypes.UTCDateTime(timezone=True), nullable=True),
        sa.CheckConstraint("lat BETWEEN -90 AND 90", name=op.f("ck_waypoint_lat_range")),
        sa.CheckConstraint("lon BETWEEN -180 AND 180", name=op.f("ck_waypoint_lon_range")),
        sa.CheckConstraint("NOT (lat = 0 AND lon = 0)", name=op.f("ck_waypoint_no_fix")),
        sa.CheckConstraint(_bytes_expr("name", 30, dialect), name=op.f("ck_waypoint_name_bytes")),
        sa.CheckConstraint(
            _bytes_expr("description", 100, dialect), name=op.f("ck_waypoint_description_bytes")
        ),
        sa.CheckConstraint(
            "removed_time IS NULL OR removed_time >= created_time",
            name=op.f("ck_waypoint_removed_after_created"),
        ),
        sa.CheckConstraint(
            "expire_time IS NULL OR expire_time >= created_time",
            name=op.f("ck_waypoint_expire_after_created"),
        ),
        *[
            sa.CheckConstraint(
                f"{c} IS NULL OR {c} GLOB '{UTC_TEXT_GLOB}'", name=op.f(f"ck_waypoint_{c}_utc_text")
            ).ddl_if(dialect="sqlite")
            for c in ("time", "created_time", "expire_time", "removed_time")
        ],
        sa.ForeignKeyConstraint(
            ["type_code"], ["waypoint_type.type_code"], name=op.f("fk_waypoint_type_code_waypoint_type")
        ),
        sa.ForeignKeyConstraint(["team_id"], ["team.team_id"], name=op.f("fk_waypoint_team_id_team")),
        sa.ForeignKeyConstraint(
            ["message_id"], ["message.message_id"], name=op.f("fk_waypoint_message_id_message")
        ),
        sa.PrimaryKeyConstraint("waypoint_id", name=op.f("pk_waypoint")),
    )
    with op.batch_alter_table("waypoint") as batch_op:
        batch_op.create_index("ix_waypoint_time", ["time"])

    # ---- search_sector: name, note, wire id, name length --------------------------------
    with op.batch_alter_table("search_sector") as batch_op:
        batch_op.add_column(sa.Column("name", sa.Text(), server_default=sa.text("''"), nullable=False))
        batch_op.add_column(sa.Column("note", sa.Text(), nullable=True))
        batch_op.create_check_constraint("wire_id", "search_sector_id BETWEEN 0 AND 65535")
        batch_op.create_check_constraint("name_bytes", _bytes_expr("name", 20, dialect))

    # Existing sectors were created before names existed: call them S<id>, which is how the
    # Arizona07 fixture refers to them. New sectors are named by the commander.
    op.execute(
        sa.text("UPDATE search_sector SET name = 'S' || CAST(search_sector_id AS TEXT) WHERE name = ''")
    )

    with op.batch_alter_table("search_sector") as batch_op:
        batch_op.create_index(
            "ux_search_sector_name", ["name"], unique=True,
            sqlite_where=sa.text("name <> ''"), postgresql_where=sa.text("name <> ''"),
        )

    # ---- search_sector_point: no (0, 0) corner ------------------------------------------
    with op.batch_alter_table("search_sector_point") as batch_op:
        batch_op.create_check_constraint("no_fix", "NOT (lat = 0 AND lon = 0)")

    # ---- mission: operational_period ----------------------------------------------------
    with op.batch_alter_table("mission") as batch_op:
        batch_op.add_column(
            sa.Column("operational_period", sa.Integer(), server_default=sa.text("1"), nullable=False)
        )
        batch_op.create_check_constraint("operational_period", "operational_period >= 1")

    # ---- sector_assignment: history of group <-> sector ---------------------------------
    op.create_table(
        "sector_assignment",
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("search_sector_id", sa.Integer(), nullable=False),
        sa.Column("search_group_id", sa.Integer(), nullable=False),
        sa.Column("from_time", missiondb.sqltypes.UTCDateTime(timezone=True), nullable=False),
        sa.Column("to_time", missiondb.sqltypes.UTCDateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "to_time IS NULL OR to_time >= from_time", name=op.f("ck_sector_assignment_ordered")
        ),
        sa.CheckConstraint(
            f"from_time IS NULL OR from_time GLOB '{UTC_TEXT_GLOB}'",
            name=op.f("ck_sector_assignment_from_time_utc_text"),
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            f"to_time IS NULL OR to_time GLOB '{UTC_TEXT_GLOB}'",
            name=op.f("ck_sector_assignment_to_time_utc_text"),
        ).ddl_if(dialect="sqlite"),
        sa.ForeignKeyConstraint(
            ["search_sector_id"], ["search_sector.search_sector_id"],
            name=op.f("fk_sector_assignment_search_sector_id_search_sector"),
        ),
        sa.ForeignKeyConstraint(
            ["search_group_id"], ["search_group.search_group_id"],
            name=op.f("fk_sector_assignment_search_group_id_search_group"),
        ),
        sa.PrimaryKeyConstraint("assignment_id", name=op.f("pk_sector_assignment")),
    )
    with op.batch_alter_table("sector_assignment") as batch_op:
        batch_op.create_index(
            "ux_sector_assignment_open_sector", ["search_sector_id"], unique=True,
            sqlite_where=sa.text("to_time IS NULL"), postgresql_where=sa.text("to_time IS NULL"),
        )
        batch_op.create_index(
            "ux_sector_assignment_open_group", ["search_group_id"], unique=True,
            sqlite_where=sa.text("to_time IS NULL"), postgresql_where=sa.text("to_time IS NULL"),
        )
        batch_op.create_index("ix_sector_assignment_search_group_id", ["search_group_id"])

    # Every sector that had a group becomes one assignment row. Assigned when drawn, released
    # when completed: the closest the old column can say.
    op.execute(sa.text(
        "INSERT INTO sector_assignment (search_sector_id, search_group_id, from_time, to_time) "
        "SELECT search_sector_id, search_group_id, created_time, completed_time "
        "FROM search_sector WHERE search_group_id IS NOT NULL ORDER BY search_sector_id"
    ))
    with op.batch_alter_table("search_sector") as batch_op:
        batch_op.drop_index("ux_search_sector_open_per_group")
        batch_op.drop_constraint(op.f("ck_search_sector_searching_needs_group"), type_="check")
        batch_op.drop_constraint(op.f("fk_search_sector_search_group_id_search_group"), type_="foreignkey")
        batch_op.drop_column("search_group_id")

    # ---- message_type: found ------------------------------------------------------------
    op.bulk_insert(
        sa.table("message_type", sa.column("type_code", sa.Text), sa.column("description", sa.Text)),
        [{"type_code": "found", "description": "Missing person located"}],
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM message_type WHERE type_code = 'found'"))
    with op.batch_alter_table("search_sector") as batch_op:
        batch_op.add_column(sa.Column("search_group_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_search_sector_search_group_id_search_group"),
            "search_group", ["search_group_id"], ["search_group_id"],
        )
    # The group of the open assignment, else the last assignment the sector had.
    op.execute(sa.text(
        "UPDATE search_sector SET search_group_id = ("
        "  SELECT search_group_id FROM sector_assignment a WHERE a.search_sector_id = search_sector.search_sector_id"
        "  ORDER BY (a.to_time IS NULL) DESC, a.from_time DESC LIMIT 1)"
    ))
    with op.batch_alter_table("search_sector") as batch_op:
        batch_op.create_check_constraint(
            "searching_needs_group", "status = 'drawn' OR search_group_id IS NOT NULL"
        )
        batch_op.create_index(
            "ux_search_sector_open_per_group", ["search_group_id"], unique=True,
            sqlite_where=sa.text("status IN ('drawn', 'searching')"),
            postgresql_where=sa.text("status IN ('drawn', 'searching')"),
        )
    with op.batch_alter_table("sector_assignment") as batch_op:
        batch_op.drop_index("ix_sector_assignment_search_group_id")
        batch_op.drop_index("ux_sector_assignment_open_group")
        batch_op.drop_index("ux_sector_assignment_open_sector")
    op.drop_table("sector_assignment")
    with op.batch_alter_table("mission") as batch_op:
        batch_op.drop_constraint(op.f("ck_mission_operational_period"), type_="check")
        batch_op.drop_column("operational_period")
    with op.batch_alter_table("search_sector_point") as batch_op:
        batch_op.drop_constraint(op.f("ck_search_sector_point_no_fix"), type_="check")
    with op.batch_alter_table("search_sector") as batch_op:
        batch_op.drop_index("ux_search_sector_name")
        batch_op.drop_constraint(op.f("ck_search_sector_name_bytes"), type_="check")
        batch_op.drop_constraint(op.f("ck_search_sector_wire_id"), type_="check")
        batch_op.drop_column("note")
        batch_op.drop_column("name")
    with op.batch_alter_table("waypoint") as batch_op:
        batch_op.drop_index("ix_waypoint_time")
    op.drop_table("waypoint")
    with op.batch_alter_table("sector_dispatch") as batch_op:
        batch_op.drop_index("ix_sector_dispatch_team_id")
        batch_op.drop_index("ix_sector_dispatch_search_sector_id")
    op.drop_table("sector_dispatch")
    op.drop_table("waypoint_type")
