"""Add email verification fields to users table

Revision ID: add_email_verification_001
Revises: add_user_roles_001
Create Date: 2025-09-22 10:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_email_verification_001'
down_revision: Union[str, Sequence[str], None] = 'add_user_roles_001'
branch_labels = None
depends_on = None


def upgrade():
    """Add email verification fields to users table."""
    # Add email verification fields
    op.add_column('users', sa.Column('is_email_verified', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('email_verification_token', sa.String(255), nullable=True))
    
    # Create index on email verification token for faster lookups
    op.create_index('ix_users_email_verification_token', 'users', ['email_verification_token'])


def downgrade():
    """Remove email verification fields from users table."""
    # Drop index
    op.drop_index('ix_users_email_verification_token', table_name='users')
    
    # Drop columns
    op.drop_column('users', 'email_verification_token')
    op.drop_column('users', 'is_email_verified')
