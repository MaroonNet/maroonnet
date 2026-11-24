"""mission status, radio kinds, partial sectors, message acks, check-in (3NF v1.3)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-24

From the Nov 24 schema review (Corey, Elijah):
  - search_sector.status: 'partial' (searched in part, nobody on it now).
  - mission: status (planning, active, paused, ended), time_zone (IANA name, default UTC),
    and start_time becomes nullable (a mission being planned has not started).
    Existing rows: end_time set -> 'ended', otherwise 'active'.
  - team: kind (searcher, command_post, relay, aerial). Existing rows are 'searcher'.
  - message: addressing (direct, multicast, broadcast) with a batch_id shared by the rows of
    one send, ack_time and packet_id (as on sector_dispatch). Existing rows are 'direct'.
  - searcher_checkin: when a searcher was present for the period (check-in / check-out).
  - waypoint_type: 'point_last_seen' and 'other'.

The *_utc_text CHECKs are SQLite-only, as in 0001 and 0002.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import missiondb.sqltypes
from missiondb.sqltypes import UTC_TEXT_GLOB

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_WAYPOINT_TYPES = (
    ("point_last_seen", "Where a witness last saw the subject"),
    ("other", "Anything else worth marking"),
)


def _utc_glob(col: str) -> str:
    return f"{col} IS NULL OR {col} GLOB '{UTC_TEXT_GLOB}'"


def upgrade() -> None:
    sqlite = op.get_context().dialect.name == "sqlite"

    # ---- search_sector: 'partial' -------------------------------------------------------
    with op.batch_alter_table("search_sector") as batch_op:
        batch_op.drop_constraint(op.f("ck_search_sector_status"), type_="check")
        batch_op.create_check_constraint(
            op.f("ck_search_sector_status"),
            "status IN ('drawn', 'searching', 'partial', 'completed')",
        )

    # ---- mission: status, time_zone, nullable start_time --------------------------------
    with op.batch_alter_table("mission") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(length=16), server_default="planning", nullable=False)
        )
        batch_op.add_column(
            sa.Column("time_zone", sa.Text(), server_default=sa.text("'UTC'"), nullable=False)
        )
        batch_op.alter_column(
            "start_time", existing_type=missiondb.sqltypes.UTCDateTime(timezone=True), nullable=True
        )
    # Every file written before this migration has a start_time, so none is 'planning'.
    op.execute(sa.text(
        "UPDATE mission SET status = CASE WHEN end_time IS NOT NULL THEN 'ended' ELSE 'active' END"
    ))
    with op.batch_alter_table("mission") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_mission_status"), "status IN ('planning', 'active', 'paused', 'ended')"
        )
        batch_op.create_check_constraint(
            op.f("ck_mission_start_time"), "(status = 'planning') = (start_time IS NULL)"
        )
        batch_op.create_check_constraint(
            op.f("ck_mission_end_time"),
            "(status IN ('paused', 'ended')) = (end_time IS NOT NULL)",
        )
        batch_op.create_check_constraint(op.f("ck_mission_time_zone"), "time_zone <> ''")

    # ---- team: kind ---------------------------------------------------------------------
    with op.batch_alter_table("team") as batch_op:
        batch_op.add_column(
            sa.Column("kind", sa.String(length=16), server_default="searcher", nullable=False)
        )
        batch_op.create_check_constraint(
            op.f("ck_team_kind"), "kind IN ('searcher', 'command_post', 'relay', 'aerial')"
        )

    # ---- message: addressing, batch_id, ack_time, packet_id -----------------------------
    with op.batch_alter_table("message") as batch_op:
        batch_op.add_column(
            sa.Column("addressing", sa.String(length=16), server_default="direct", nullable=False)
        )
        batch_op.add_column(sa.Column("batch_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("ack_time", missiondb.sqltypes.UTCDateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("packet_id", sa.BigInteger(), nullable=True))
        batch_op.create_check_constraint(
            op.f("ck_message_addressing"), "addressing IN ('direct', 'multicast', 'broadcast')"
        )
        batch_op.create_check_constraint(
            op.f("ck_message_ack_after_sent"), "ack_time IS NULL OR ack_time >= time"
        )
        batch_op.create_check_constraint(
            op.f("ck_message_batch_id"), "(addressing = 'direct') = (batch_id IS NULL)"
        )
        if sqlite:
            batch_op.create_check_constraint(
                op.f("ck_message_ack_time_utc_text"), _utc_glob("ack_time")
            )
        batch_op.create_index("ix_message_batch_id", ["batch_id"])

    # ---- searcher_checkin ---------------------------------------------------------------
    op.create_table(
        "searcher_checkin",
        sa.Column("checkin_id", sa.Integer(), nullable=False),
        sa.Column("searcher_id", sa.Integer(), nullable=False),
        sa.Column("in_time", missiondb.sqltypes.UTCDateTime(timezone=True), nullable=False),
        sa.Column("out_time", missiondb.sqltypes.UTCDateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "out_time IS NULL OR out_time >= in_time", name=op.f("ck_searcher_checkin_ordered")
        ),
        sa.CheckConstraint(
            _utc_glob("in_time"), name=op.f("ck_searcher_checkin_in_time_utc_text")
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            _utc_glob("out_time"), name=op.f("ck_searcher_checkin_out_time_utc_text")
        ).ddl_if(dialect="sqlite"),
        sa.ForeignKeyConstraint(
            ["searcher_id"], ["searcher.searcher_id"],
            name=op.f("fk_searcher_checkin_searcher_id_searcher"),
        ),
        sa.PrimaryKeyConstraint("checkin_id", name=op.f("pk_searcher_checkin")),
    )
    with op.batch_alter_table("searcher_checkin") as batch_op:
        batch_op.create_index(
            "ux_searcher_checkin_open", ["searcher_id"], unique=True,
            sqlite_where=sa.text("out_time IS NULL"), postgresql_where=sa.text("out_time IS NULL"),
        )
        batch_op.create_index("ix_searcher_checkin_searcher_id", ["searcher_id"])

    # ---- waypoint_type: point_last_seen, other ------------------------------------------
    # Frozen here on purpose (see 0001). Skips a code a team already added by hand.
    for code, description in _NEW_WAYPOINT_TYPES:
        op.execute(
            sa.text(
                "INSERT INTO waypoint_type (type_code, description) SELECT :code, :description "
                "WHERE NOT EXISTS (SELECT 1 FROM waypoint_type WHERE type_code = :code)"
            ).bindparams(code=code, description=description)
        )


def downgrade() -> None:
    sqlite = op.get_context().dialect.name == "sqlite"

    # The two waypoint types go unless a waypoint still uses them.
    for code, _ in _NEW_WAYPOINT_TYPES:
        op.execute(
            sa.text(
                "DELETE FROM waypoint_type WHERE type_code = :code "
                "AND NOT EXISTS (SELECT 1 FROM waypoint WHERE waypoint.type_code = :code)"
            ).bindparams(code=code)
        )

    with op.batch_alter_table("searcher_checkin") as batch_op:
        batch_op.drop_index("ix_searcher_checkin_searcher_id")
        batch_op.drop_index("ux_searcher_checkin_open")
    op.drop_table("searcher_checkin")

    with op.batch_alter_table("message") as batch_op:
        batch_op.drop_index("ix_message_batch_id")
        if sqlite:
            batch_op.drop_constraint(op.f("ck_message_ack_time_utc_text"), type_="check")
        batch_op.drop_constraint(op.f("ck_message_batch_id"), type_="check")
        batch_op.drop_constraint(op.f("ck_message_ack_after_sent"), type_="check")
        batch_op.drop_constraint(op.f("ck_message_addressing"), type_="check")
        batch_op.drop_column("packet_id")
        batch_op.drop_column("ack_time")
        batch_op.drop_column("batch_id")
        batch_op.drop_column("addressing")

    with op.batch_alter_table("team") as batch_op:
        batch_op.drop_constraint(op.f("ck_team_kind"), type_="check")
        batch_op.drop_column("kind")

    with op.batch_alter_table("mission") as batch_op:
        batch_op.drop_constraint(op.f("ck_mission_time_zone"), type_="check")
        batch_op.drop_constraint(op.f("ck_mission_end_time"), type_="check")
        batch_op.drop_constraint(op.f("ck_mission_start_time"), type_="check")
        batch_op.drop_constraint(op.f("ck_mission_status"), type_="check")
    # 0002 requires a start_time: a mission still being planned gets the time of the downgrade.
    op.execute(sa.text(
        "UPDATE mission SET start_time = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE start_time IS NULL"
        if sqlite else
        "UPDATE mission SET start_time = now() WHERE start_time IS NULL"
    ))
    with op.batch_alter_table("mission") as batch_op:
        batch_op.alter_column(
            "start_time", existing_type=missiondb.sqltypes.UTCDateTime(timezone=True), nullable=False
        )
        batch_op.drop_column("time_zone")
        batch_op.drop_column("status")

    # 0002 has no 'partial': the nearest it can say is 'searching' with no open assignment.
    op.execute(sa.text("UPDATE search_sector SET status = 'searching' WHERE status = 'partial'"))
    with op.batch_alter_table("search_sector") as batch_op:
        batch_op.drop_constraint(op.f("ck_search_sector_status"), type_="check")
        batch_op.create_check_constraint(
            op.f("ck_search_sector_status"), "status IN ('drawn', 'searching', 'completed')"
        )
