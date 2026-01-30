"""add device_activity_log table for device type statistics

Revision ID: add_device_activity_log
Revises: b12fdd5688b7
Create Date: 2025-01-20

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_device_activity_log'
down_revision = 'add_deletion_requested_at'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    if not _table_exists('device_activity_log'):
        op.create_table(
            'device_activity_log',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('device_type', sa.String(20), nullable=False, index=True),
            sa.Column('activity', sa.String(50), nullable=False, index=True),
            sa.Column('created_at', sa.String(), nullable=True),
        )
        op.create_index(op.f('ix_device_activity_log_created_at'), 'device_activity_log', ['created_at'], unique=False)


def downgrade():
    if _table_exists('device_activity_log'):
        op.drop_table('device_activity_log')
