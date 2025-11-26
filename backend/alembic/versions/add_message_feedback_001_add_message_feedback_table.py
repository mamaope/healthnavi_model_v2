"""Add message feedback table

Revision ID: add_message_feedback_001
Revises: add_password_reset_001
Create Date: 2025-01-27 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'add_message_feedback_001'
down_revision: Union[str, Sequence[str], None] = 'add_password_reset_001'
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def index_exists(table_name: str, index_name: str) -> bool:
    """Check if an index exists on a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = inspector.get_indexes(table_name)
    return any(idx['name'] == index_name for idx in indexes)


def upgrade():
    """Create message_feedback table."""
    # Check if table already exists (may have been created by create_tables())
    if not table_exists('message_feedback'):
        op.create_table('message_feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('feedback_type', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.String(), nullable=True),
        sa.Column('updated_at', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['message_id'], ['chat_messages.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id')
        )
    
    # Create indexes if they don't exist
    if not index_exists('message_feedback', 'ix_message_feedback_id'):
        op.create_index(op.f('ix_message_feedback_id'), 'message_feedback', ['id'], unique=False)
    if not index_exists('message_feedback', 'ix_message_feedback_message_id'):
        op.create_index(op.f('ix_message_feedback_message_id'), 'message_feedback', ['message_id'], unique=True)
    if not index_exists('message_feedback', 'ix_message_feedback_user_id'):
        op.create_index(op.f('ix_message_feedback_user_id'), 'message_feedback', ['user_id'], unique=False)


def downgrade():
    """Drop message_feedback table."""
    op.drop_index(op.f('ix_message_feedback_user_id'), table_name='message_feedback')
    op.drop_index(op.f('ix_message_feedback_message_id'), table_name='message_feedback')
    op.drop_index(op.f('ix_message_feedback_id'), table_name='message_feedback')
    op.drop_table('message_feedback')

