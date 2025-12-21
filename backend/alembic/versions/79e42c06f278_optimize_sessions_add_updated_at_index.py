"""optimize_sessions_add_updated_at_index

Revision ID: 79e42c06f278
Revises: add_google_oauth_001
Create Date: 2025-12-21 20:47:13.408674

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79e42c06f278'
down_revision: Union[str, Sequence[str], None] = 'add_google_oauth_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add index to diagnosis_sessions.updated_at for faster session list queries."""
    # Add index to updated_at column for faster sorting
    op.create_index(
        'ix_diagnosis_sessions_updated_at',
        'diagnosis_sessions',
        ['updated_at'],
        unique=False
    )


def downgrade() -> None:
    """Remove index from diagnosis_sessions.updated_at."""
    op.drop_index('ix_diagnosis_sessions_updated_at', table_name='diagnosis_sessions')
