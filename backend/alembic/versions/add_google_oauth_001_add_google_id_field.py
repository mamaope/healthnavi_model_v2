"""Add Google OAuth support

Revision ID: add_google_oauth_001
Revises: add_message_feedback_001
Create Date: 2025-01-27 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'add_google_oauth_001'
down_revision: Union[str, Sequence[str], None] = 'add_message_feedback_001'
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(col['name'] == column_name for col in columns)


def upgrade():
    """Add Google OAuth support to users table."""
    # Add google_id column if it doesn't exist
    if not column_exists('users', 'google_id'):
        op.add_column('users', sa.Column('google_id', sa.String(length=255), nullable=True))
        op.create_index('ix_users_google_id', 'users', ['google_id'], unique=True)
    
    # Make hashed_password nullable (for OAuth users who don't have passwords)
    # Check current nullability first
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = inspector.get_columns('users')
    hashed_password_col = next((col for col in columns if col['name'] == 'hashed_password'), None)
    
    if hashed_password_col and hashed_password_col['nullable'] is False:
        # Make it nullable
        op.alter_column('users', 'hashed_password', nullable=True)


def downgrade():
    """Remove Google OAuth support from users table."""
    # Remove google_id column
    if column_exists('users', 'google_id'):
        op.drop_index('ix_users_google_id', table_name='users')
        op.drop_column('users', 'google_id')
    
    # Note: We don't revert hashed_password to NOT NULL as it might break existing OAuth users

