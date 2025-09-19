"""Fix user role enum values

Revision ID: fix_user_role_enum_001
Revises: add_user_role_001
Create Date: 2025-01-20 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'fix_user_role_enum_001'
down_revision = 'add_user_role_001'
branch_labels = None
depends_on = None


def upgrade():
    """Fix user role enum values to use uppercase."""
    # Drop the existing enum type
    op.execute('DROP TYPE IF EXISTS userrole CASCADE')
    
    # Create new enum type with uppercase values
    user_role_enum = postgresql.ENUM('USER', 'ADMIN', 'SUPER_ADMIN', name='userrole')
    user_role_enum.create(op.get_bind())
    
    # Add the role column back with the correct enum
    op.add_column('users', sa.Column('role', user_role_enum, nullable=False, server_default='USER'))


def downgrade():
    """Revert to lowercase enum values."""
    # Drop the role column
    op.drop_column('users', 'role')
    
    # Drop the enum type
    op.execute('DROP TYPE IF EXISTS userrole')
    
    # Recreate with lowercase values
    user_role_enum = postgresql.ENUM('user', 'admin', 'super_admin', name='userrole')
    user_role_enum.create(op.get_bind())
    
    # Add role column back with lowercase enum
    op.add_column('users', sa.Column('role', user_role_enum, nullable=False, server_default='user'))
