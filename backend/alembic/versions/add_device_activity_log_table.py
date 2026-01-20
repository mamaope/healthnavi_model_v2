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


def upgrade():
    op.create_table(
        'device_activity_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('device_type', sa.String(20), nullable=False, index=True),
        sa.Column('activity', sa.String(50), nullable=False, index=True),
        sa.Column('created_at', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_device_activity_log_created_at'), 'device_activity_log', ['created_at'], unique=False)


def downgrade():
    op.drop_table('device_activity_log')
