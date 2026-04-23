"""add surveytype enum lowercase values

Ensure surveytype has 'baseline','mid','final','pmf' so inserts from the app work.
The app sends lowercase (SurveyType.value); if the DB enum was created with
uppercase (BASELINE etc.) or is missing lowercase, ADD VALUE IF NOT EXISTS.

Revision ID: add_surveytype_lower
Revises: fix_device_activity_log_id
Create Date: 2026-01-20

"""
from alembic import op


revision = 'add_surveytype_lower'
down_revision = 'fix_device_activity_log_id'
branch_labels = None
depends_on = None


def upgrade():
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction in many PostgreSQL configs
    with op.get_context().autocommit_block():
        for label in ('baseline', 'mid', 'final', 'pmf'):
            op.execute(f"ALTER TYPE surveytype ADD VALUE IF NOT EXISTS '{label}'")


def downgrade():
    # PostgreSQL does not support removing an enum value. No-op.
    pass
