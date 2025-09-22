"""add user roles and timestamps

Revision ID: user_roles_v1
Revises: 72d72b51ae8e
Create Date: 2025-09-22 10:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'user_roles_v1'
down_revision: Union[str, Sequence[str], None] = '72d72b51ae8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user roles and timestamps."""
    # Add role column as string with default value
    op.add_column('users', sa.Column('role', sa.String(20), nullable=False, server_default='user'))
    
    # Add timestamp columns
    op.add_column('users', sa.Column('created_at', sa.String(), nullable=True))
    op.add_column('users', sa.Column('updated_at', sa.String(), nullable=True))
    
    # Add check constraint for role values
    op.create_check_constraint(
        'users_role_check',
        'users',
        "role IN ('user', 'admin', 'super_admin')"
    )


def downgrade() -> None:
    """Remove user roles and timestamps."""
    # Remove check constraint
    op.drop_constraint('users_role_check', 'users', type_='check')
    
    # Remove columns
    op.drop_column('users', 'updated_at')
    op.drop_column('users', 'created_at')
    op.drop_column('users', 'role')
