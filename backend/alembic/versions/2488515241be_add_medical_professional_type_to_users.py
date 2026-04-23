"""add_medical_professional_type_to_users

Revision ID: 2488515241be
Revises: 79e42c06f278
Create Date: 2026-01-09 14:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '2488515241be'
down_revision: Union[str, Sequence[str], None] = '79e42c06f278'
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(col['name'] == column_name for col in columns)


def upgrade():
    """Add medical_professional_type column to users table."""
    # Add medical_professional_type column if it doesn't exist
    if not column_exists('users', 'medical_professional_type'):
        op.add_column('users', sa.Column('medical_professional_type', sa.String(length=50), nullable=True))


def downgrade():
    """Remove medical_professional_type column from users table."""
    # Remove medical_professional_type column
    if column_exists('users', 'medical_professional_type'):
        op.drop_column('users', 'medical_professional_type')
