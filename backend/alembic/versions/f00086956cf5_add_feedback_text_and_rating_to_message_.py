"""add_feedback_text_and_rating_to_message_feedback

Revision ID: f00086956cf5
Revises: 2488515241be
Create Date: 2026-01-10 16:19:06.393210

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'f00086956cf5'
down_revision: Union[str, Sequence[str], None] = '2488515241be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(col['name'] == column_name for col in columns)


def upgrade() -> None:
    """Add feedback_text and rating columns to message_feedback table."""
    # Add feedback_text column if it doesn't exist
    if not column_exists('message_feedback', 'feedback_text'):
        op.add_column('message_feedback', sa.Column('feedback_text', sa.Text(), nullable=True))
    
    # Add rating column if it doesn't exist
    if not column_exists('message_feedback', 'rating'):
        op.add_column('message_feedback', sa.Column('rating', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove feedback_text and rating columns from message_feedback table."""
    # Remove rating column if it exists
    if column_exists('message_feedback', 'rating'):
        op.drop_column('message_feedback', 'rating')
    
    # Remove feedback_text column if it exists
    if column_exists('message_feedback', 'feedback_text'):
        op.drop_column('message_feedback', 'feedback_text')
