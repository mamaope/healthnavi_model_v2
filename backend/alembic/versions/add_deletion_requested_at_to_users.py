"""add_deletion_requested_at_to_users

Revision ID: add_deletion_requested_at
Revises: add_survey_reminder_date
Create Date: 2025-01-01 00:00:00.000000

Adds deletion_requested_at to users for privacy/GDPR: users request data deletion,
and their data is removed 6 months after the request.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'add_deletion_requested_at'
down_revision: Union[str, None] = 'add_survey_reminder_date'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if table_exists('users') and not column_exists('users', 'deletion_requested_at'):
        op.add_column(
            'users',
            sa.Column('deletion_requested_at', sa.String(), nullable=True)
        )


def downgrade() -> None:
    if table_exists('users') and column_exists('users', 'deletion_requested_at'):
        op.drop_column('users', 'deletion_requested_at')
