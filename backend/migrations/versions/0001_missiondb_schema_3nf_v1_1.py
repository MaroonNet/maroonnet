"""missiondb schema 3NF v1.1

Initial schema, matching backend/missiondb/models.py at commit e714f77 (PR #14).
The *_utc_text CHECKs are SQLite-only (ddl_if): PostgreSQL has a native timestamp type.

Revision ID: 0001
Revises: 
Create Date: 2026-11-10 09:55:31.375718

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import missiondb.sqltypes
from missiondb.models import DEFAULT_MESSAGE_TYPES


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('message_type',
    sa.Column('type_code', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('type_code', name=op.f('pk_message_type'))
    )
    op.create_table('mission',
    sa.Column('mission_id', sa.Integer(), nullable=False),
    sa.Column('mission_uuid', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('start_time', missiondb.sqltypes.UTCDateTime(timezone=True), nullable=False),
    sa.Column('end_time', missiondb.sqltypes.UTCDateTime(timezone=True), nullable=True),
    sa.CheckConstraint("end_time IS NULL OR end_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'", name=op.f('ck_mission_end_time_utc_text')).ddl_if(dialect='sqlite'),
    sa.CheckConstraint("start_time IS NULL OR start_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'", name=op.f('ck_mission_start_time_utc_text')).ddl_if(dialect='sqlite'),
    sa.CheckConstraint('mission_id = 1', name=op.f('ck_mission_single_row')),
    sa.PrimaryKeyConstraint('mission_id', name=op.f('pk_mission')),
    sa.UniqueConstraint('mission_uuid', name=op.f('uq_mission_mission_uuid'))
    )
    op.create_table('search_group',
    sa.Column('search_group_id', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('search_group_id', name=op.f('pk_search_group'))
    )
    op.create_table('searcher',
    sa.Column('searcher_id', sa.Integer(), nullable=False),
    sa.Column('fname', sa.Text(), nullable=False),
    sa.Column('lname', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('searcher_id', name=op.f('pk_searcher'))
    )
    op.create_table('team',
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('node_num', sa.BigInteger(), nullable=False),
    sa.Column('active', sa.Boolean(create_constraint=True, name='active'), server_default=sa.text('0'), nullable=False),
    sa.PrimaryKeyConstraint('team_id', name=op.f('pk_team')),
    sa.UniqueConstraint('node_num', name=op.f('uq_team_node_num'))
    )
    op.create_table('location',
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('time', missiondb.sqltypes.UTCDateTime(timezone=True), nullable=False),
    sa.Column('rx_time', missiondb.sqltypes.UTCDateTime(timezone=True), nullable=False),
    sa.Column('lat', sa.Float(), nullable=False),
    sa.Column('lon', sa.Float(), nullable=False),
    sa.Column('elevation', sa.Float(), nullable=True),
    sa.CheckConstraint("rx_time IS NULL OR rx_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'", name=op.f('ck_location_rx_time_utc_text')).ddl_if(dialect='sqlite'),
    sa.CheckConstraint("time IS NULL OR time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'", name=op.f('ck_location_time_utc_text')).ddl_if(dialect='sqlite'),
    sa.CheckConstraint('NOT (lat = 0 AND lon = 0)', name=op.f('ck_location_no_fix')),
    sa.CheckConstraint('lat BETWEEN -90 AND 90', name=op.f('ck_location_lat_range')),
    sa.CheckConstraint('lon BETWEEN -180 AND 180', name=op.f('ck_location_lon_range')),
    sa.ForeignKeyConstraint(['team_id'], ['team.team_id'], name=op.f('fk_location_team_id_team')),
    sa.PrimaryKeyConstraint('team_id', 'time', name=op.f('pk_location')),
    sqlite_with_rowid=False
    )
    with op.batch_alter_table('location', schema=None) as batch_op:
        batch_op.create_index('ix_location_time', ['time'], unique=False)

    op.create_table('message',
    sa.Column('message_id', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('time', missiondb.sqltypes.UTCDateTime(timezone=True), nullable=False),
    sa.Column('rx_time', missiondb.sqltypes.UTCDateTime(timezone=True), nullable=False),
    sa.Column('direction', sa.Enum('in', 'out', name='direction', native_enum=False, create_constraint=True, length=16), nullable=False),
    sa.Column('type_code', sa.Text(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.CheckConstraint("rx_time IS NULL OR rx_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'", name=op.f('ck_message_rx_time_utc_text')).ddl_if(dialect='sqlite'),
    sa.CheckConstraint("time IS NULL OR time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'", name=op.f('ck_message_time_utc_text')).ddl_if(dialect='sqlite'),
    sa.ForeignKeyConstraint(['team_id'], ['team.team_id'], name=op.f('fk_message_team_id_team')),
    sa.ForeignKeyConstraint(['type_code'], ['message_type.type_code'], name=op.f('fk_message_type_code_message_type')),
    sa.PrimaryKeyConstraint('message_id', name=op.f('pk_message'))
    )
    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.create_index('ix_message_time', ['time'], unique=False)

    op.create_table('search_area',
    sa.Column('search_area_id', sa.Integer(), nullable=False),
    sa.Column('mission_id', sa.Integer(), nullable=False),
    sa.Column('min_lat', sa.Float(), nullable=False),
    sa.Column('min_lon', sa.Float(), nullable=False),
    sa.Column('max_lat', sa.Float(), nullable=False),
    sa.Column('max_lon', sa.Float(), nullable=False),
    sa.CheckConstraint('max_lat BETWEEN -90 AND 90', name=op.f('ck_search_area_max_lat_range')),
    sa.CheckConstraint('max_lon BETWEEN -180 AND 180', name=op.f('ck_search_area_max_lon_range')),
    sa.CheckConstraint('min_lat < max_lat AND min_lon < max_lon', name=op.f('ck_search_area_corners')),
    sa.CheckConstraint('min_lat BETWEEN -90 AND 90', name=op.f('ck_search_area_min_lat_range')),
    sa.CheckConstraint('min_lon BETWEEN -180 AND 180', name=op.f('ck_search_area_min_lon_range')),
    sa.ForeignKeyConstraint(['mission_id'], ['mission.mission_id'], name=op.f('fk_search_area_mission_id_mission')),
    sa.PrimaryKeyConstraint('search_area_id', name=op.f('pk_search_area'))
    )
    op.create_table('search_sector',
    sa.Column('search_sector_id', sa.Integer(), nullable=False),
    sa.Column('search_group_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.Enum('drawn', 'searching', 'completed', name='status', native_enum=False, create_constraint=True, length=16), server_default='drawn', nullable=False),
    sa.Column('created_time', missiondb.sqltypes.UTCDateTime(timezone=True), nullable=False),
    sa.Column('completed_time', missiondb.sqltypes.UTCDateTime(timezone=True), nullable=True),
    sa.CheckConstraint("(status = 'completed') = (completed_time IS NOT NULL)", name=op.f('ck_search_sector_completed_time')),
    sa.CheckConstraint("completed_time IS NULL OR completed_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'", name=op.f('ck_search_sector_completed_time_utc_text')).ddl_if(dialect='sqlite'),
    sa.CheckConstraint("created_time IS NULL OR created_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'", name=op.f('ck_search_sector_created_time_utc_text')).ddl_if(dialect='sqlite'),
    sa.CheckConstraint("status = 'drawn' OR search_group_id IS NOT NULL", name=op.f('ck_search_sector_searching_needs_group')),
    sa.ForeignKeyConstraint(['search_group_id'], ['search_group.search_group_id'], name=op.f('fk_search_sector_search_group_id_search_group')),
    sa.PrimaryKeyConstraint('search_sector_id', name=op.f('pk_search_sector'))
    )
    with op.batch_alter_table('search_sector', schema=None) as batch_op:
        batch_op.create_index('ux_search_sector_open_per_group', ['search_group_id'], unique=True, sqlite_where=sa.text("status IN ('drawn', 'searching')"), postgresql_where=sa.text("status IN ('drawn', 'searching')"))

    op.create_table('searcher_team_assignment',
    sa.Column('assignment_id', sa.Integer(), nullable=False),
    sa.Column('searcher_id', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('from_time', missiondb.sqltypes.UTCDateTime(timezone=True), nullable=False),
    sa.Column('to_time', missiondb.sqltypes.UTCDateTime(timezone=True), nullable=True),
    sa.CheckConstraint("from_time IS NULL OR from_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'", name=op.f('ck_searcher_team_assignment_from_time_utc_text')).ddl_if(dialect='sqlite'),
    sa.CheckConstraint("to_time IS NULL OR to_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'", name=op.f('ck_searcher_team_assignment_to_time_utc_text')).ddl_if(dialect='sqlite'),
    sa.CheckConstraint('to_time IS NULL OR to_time >= from_time', name=op.f('ck_searcher_team_assignment_ordered')),
    sa.ForeignKeyConstraint(['searcher_id'], ['searcher.searcher_id'], name=op.f('fk_searcher_team_assignment_searcher_id_searcher')),
    sa.ForeignKeyConstraint(['team_id'], ['team.team_id'], name=op.f('fk_searcher_team_assignment_team_id_team')),
    sa.PrimaryKeyConstraint('assignment_id', name=op.f('pk_searcher_team_assignment'))
    )
    with op.batch_alter_table('searcher_team_assignment', schema=None) as batch_op:
        batch_op.create_index('ux_searcher_team_assignment_open', ['searcher_id'], unique=True, sqlite_where=sa.text('to_time IS NULL'), postgresql_where=sa.text('to_time IS NULL'))

    op.create_table('team_group_assignment',
    sa.Column('assignment_id', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('search_group_id', sa.Integer(), nullable=False),
    sa.Column('from_time', missiondb.sqltypes.UTCDateTime(timezone=True), nullable=False),
    sa.Column('to_time', missiondb.sqltypes.UTCDateTime(timezone=True), nullable=True),
    sa.CheckConstraint("from_time IS NULL OR from_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'", name=op.f('ck_team_group_assignment_from_time_utc_text')).ddl_if(dialect='sqlite'),
    sa.CheckConstraint("to_time IS NULL OR to_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'", name=op.f('ck_team_group_assignment_to_time_utc_text')).ddl_if(dialect='sqlite'),
    sa.CheckConstraint('to_time IS NULL OR to_time >= from_time', name=op.f('ck_team_group_assignment_ordered')),
    sa.ForeignKeyConstraint(['search_group_id'], ['search_group.search_group_id'], name=op.f('fk_team_group_assignment_search_group_id_search_group')),
    sa.ForeignKeyConstraint(['team_id'], ['team.team_id'], name=op.f('fk_team_group_assignment_team_id_team')),
    sa.PrimaryKeyConstraint('assignment_id', name=op.f('pk_team_group_assignment'))
    )
    with op.batch_alter_table('team_group_assignment', schema=None) as batch_op:
        batch_op.create_index('ux_team_group_assignment_open', ['team_id'], unique=True, sqlite_where=sa.text('to_time IS NULL'), postgresql_where=sa.text('to_time IS NULL'))

    op.create_table('search_sector_point',
    sa.Column('search_sector_id', sa.Integer(), nullable=False),
    sa.Column('point_order', sa.Integer(), nullable=False),
    sa.Column('lat', sa.Float(), nullable=False),
    sa.Column('lon', sa.Float(), nullable=False),
    sa.CheckConstraint('lat BETWEEN -90 AND 90', name=op.f('ck_search_sector_point_lat_range')),
    sa.CheckConstraint('lon BETWEEN -180 AND 180', name=op.f('ck_search_sector_point_lon_range')),
    sa.CheckConstraint('point_order >= 1', name=op.f('ck_search_sector_point_point_order')),
    sa.ForeignKeyConstraint(['search_sector_id'], ['search_sector.search_sector_id'], name=op.f('fk_search_sector_point_search_sector_id_search_sector')),
    sa.PrimaryKeyConstraint('search_sector_id', 'point_order', name=op.f('pk_search_sector_point'))
    )
    op.create_table('sector_entry',
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('search_sector_id', sa.Integer(), nullable=False),
    sa.Column('entered_time', missiondb.sqltypes.UTCDateTime(timezone=True), nullable=False),
    sa.CheckConstraint("entered_time IS NULL OR entered_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'", name=op.f('ck_sector_entry_entered_time_utc_text')).ddl_if(dialect='sqlite'),
    sa.ForeignKeyConstraint(['search_sector_id'], ['search_sector.search_sector_id'], name=op.f('fk_sector_entry_search_sector_id_search_sector')),
    sa.ForeignKeyConstraint(['team_id'], ['team.team_id'], name=op.f('fk_sector_entry_team_id_team')),
    sa.PrimaryKeyConstraint('team_id', 'search_sector_id', name=op.f('pk_sector_entry'))
    )

    op.bulk_insert(
        sa.table('message_type', sa.column('type_code', sa.Text), sa.column('description', sa.Text)),
        [{'type_code': c, 'description': d} for c, d in DEFAULT_MESSAGE_TYPES],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('sector_entry')
    op.drop_table('search_sector_point')
    with op.batch_alter_table('team_group_assignment', schema=None) as batch_op:
        batch_op.drop_index('ux_team_group_assignment_open', sqlite_where=sa.text('to_time IS NULL'), postgresql_where=sa.text('to_time IS NULL'))

    op.drop_table('team_group_assignment')
    with op.batch_alter_table('searcher_team_assignment', schema=None) as batch_op:
        batch_op.drop_index('ux_searcher_team_assignment_open', sqlite_where=sa.text('to_time IS NULL'), postgresql_where=sa.text('to_time IS NULL'))

    op.drop_table('searcher_team_assignment')
    with op.batch_alter_table('search_sector', schema=None) as batch_op:
        batch_op.drop_index('ux_search_sector_open_per_group', sqlite_where=sa.text("status IN ('drawn', 'searching')"), postgresql_where=sa.text("status IN ('drawn', 'searching')"))

    op.drop_table('search_sector')
    op.drop_table('search_area')
    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.drop_index('ix_message_time')

    op.drop_table('message')
    with op.batch_alter_table('location', schema=None) as batch_op:
        batch_op.drop_index('ix_location_time')

    op.drop_table('location')
    op.drop_table('team')
    op.drop_table('searcher')
    op.drop_table('search_group')
    op.drop_table('mission')
    op.drop_table('message_type')
