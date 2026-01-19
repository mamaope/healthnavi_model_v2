"""add_survey_reminder_date_to_users

Revision ID: add_survey_reminder_date
Revises: b12fdd5688b7
Create Date: 2026-01-19 23:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_survey_reminder_date'
down_revision: Union[str, None] = 'b12fdd5688b7'
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
    # Add survey_reminder_date column to users table if it doesn't exist
    if table_exists('users') and not column_exists('users', 'survey_reminder_date'):
        op.add_column('users', sa.Column('survey_reminder_date', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove survey_reminder_date column from users table if it exists
    if table_exists('users') and column_exists('users', 'survey_reminder_date'):
        op.drop_column('users', 'survey_reminder_date')
