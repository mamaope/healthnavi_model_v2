"""add_survey_visibility_config

Revision ID: b12fdd5688b7
Revises: f00086956cf5
Create Date: 2026-01-19 22:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'b12fdd5688b7'
down_revision: Union[str, Sequence[str], None] = 'create_admin_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists using direct SQL query."""
    bind = op.get_bind()
    result = bind.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = :table_name
        )
    """), {"table_name": table_name}).scalar()
    return result


def upgrade() -> None:
    """Add survey_config table for managing survey visibility."""
    if not table_exists('survey_config'):
        op.create_table(
            'survey_config',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('survey_type', sa.String(length=50), nullable=False, unique=True),
            sa.Column('is_visible', sa.Boolean(), nullable=False, default=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('created_at', sa.String(), nullable=True),
            sa.Column('updated_at', sa.String(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_survey_config_id'), 'survey_config', ['id'], unique=False)
        op.create_index(op.f('ix_survey_config_survey_type'), 'survey_config', ['survey_type'], unique=True)
        
        # Insert default survey configs
        from datetime import datetime
        now = datetime.utcnow().isoformat()
        bind = op.get_bind()
        bind.execute(sa.text("""
            INSERT INTO survey_config (survey_type, is_visible, title, description, created_at, updated_at)
            VALUES 
            ('baseline', false, 'Pre-Pilot Survey', 'Baseline survey before pilot starts', :now, :now),
            ('mid', false, 'Mid-Pilot Survey', 'Mid-pilot PMF pulse survey', :now, :now),
            ('final', false, 'Post-Pilot Survey', 'PMF decider survey (last week)', :now, :now)
        """), {"now": now})


def downgrade() -> None:
    """Drop survey_config table."""
    op.drop_index(op.f('ix_survey_config_survey_type'), table_name='survey_config')
    op.drop_index(op.f('ix_survey_config_id'), table_name='survey_config')
    op.drop_table('survey_config')
