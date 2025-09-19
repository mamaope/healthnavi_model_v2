"""Add user role column

Revision ID: add_user_role_001
Revises: update_user_auth_001
Create Date: 2025-01-20 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_user_role_001'
down_revision = 'update_user_auth_001'
branch_labels = None
depends_on = None


def upgrade():
    """Add role column to users table."""
    # Create enum type for user roles
    user_role_enum = postgresql.ENUM('USER', 'ADMIN', 'SUPER_ADMIN', name='userrole')
    user_role_enum.create(op.get_bind())
    
    # Add role column with default value
    op.add_column('users', sa.Column('role', user_role_enum, nullable=False, server_default='USER'))


def downgrade():
    """Remove role column from users table."""
    # Drop role column
    op.drop_column('users', 'role')
    
    # Drop enum type
    op.execute('DROP TYPE IF EXISTS userrole')


