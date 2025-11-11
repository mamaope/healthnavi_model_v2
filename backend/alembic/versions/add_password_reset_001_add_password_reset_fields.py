"""Add password reset fields to users table

Revision ID: add_password_reset_001
Revises: add_diagnosis_sessions_001
Create Date: 2025-01-27 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_password_reset_001'
down_revision: Union[str, Sequence[str], None] = 'add_diagnosis_sessions_001'
branch_labels = None
depends_on = None


def upgrade():
    """Add password reset fields to users table."""
    # Add password reset fields
    op.add_column('users', sa.Column('password_reset_token', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('password_reset_expires', sa.String(), nullable=True))
    
    # Create index on password reset token for faster lookups
    op.create_index('ix_users_password_reset_token', 'users', ['password_reset_token'])


def downgrade():
    """Remove password reset fields from users table."""
    # Drop index
    op.drop_index('ix_users_password_reset_token', table_name='users')
    
    # Drop columns
    op.drop_column('users', 'password_reset_expires')
    op.drop_column('users', 'password_reset_token')

