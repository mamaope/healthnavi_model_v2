"""create admin tables

Revision ID: create_admin_tables
Revises: 
Create Date: 2025-01-XX

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'create_admin_tables'
down_revision: Union[str, Sequence[str], None] = 'f00086956cf5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create admin-related tables."""
    # Create enum types if they don't exist
    bind = op.get_bind()
    
    # Check and create safetyeventseverity enum
    result = bind.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_type WHERE typname = 'safetyeventseverity'
        )
    """)).scalar()
    if not result:
        bind.execute(sa.text("CREATE TYPE safetyeventseverity AS ENUM ('low', 'medium', 'high', 'critical')"))
    
    # Check and create safetyeventstatus enum
    result = bind.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_type WHERE typname = 'safetyeventstatus'
        )
    """)).scalar()
    if not result:
        bind.execute(sa.text("CREATE TYPE safetyeventstatus AS ENUM ('open', 'investigating', 'resolved', 'closed')"))
    
    # Check and create surveytype enum
    result = bind.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_type WHERE typname = 'surveytype'
        )
    """)).scalar()
    if not result:
        bind.execute(sa.text("CREATE TYPE surveytype AS ENUM ('baseline', 'mid', 'final', 'pmf')"))
    
    # Create safety_events table
    op.create_table(
        'safety_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('severity', postgresql.ENUM('low', 'medium', 'high', 'critical', name='safetyeventseverity', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('open', 'investigating', 'resolved', 'closed', name='safetyeventstatus', create_type=False), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('is_critical', sa.Boolean(), nullable=False),
        sa.Column('has_guideline_citation', sa.Boolean(), nullable=True),
        sa.Column('was_red_flag_queried', sa.Boolean(), nullable=True),
        sa.Column('was_red_flag_correctly_flagged', sa.Boolean(), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.String(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=True),
        sa.Column('updated_at', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['message_id'], ['chat_messages.id'], ),
        sa.ForeignKeyConstraint(['session_id'], ['diagnosis_sessions.id'], ),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_safety_events_id'), 'safety_events', ['id'], unique=False)
    op.create_index(op.f('ix_safety_events_user_id'), 'safety_events', ['user_id'], unique=False)
    op.create_index(op.f('ix_safety_events_message_id'), 'safety_events', ['message_id'], unique=False)
    op.create_index(op.f('ix_safety_events_session_id'), 'safety_events', ['session_id'], unique=False)
    op.create_index(op.f('ix_safety_events_updated_at'), 'safety_events', ['updated_at'], unique=False)
    
    # Create surveys table
    op.create_table(
        'surveys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('survey_type', postgresql.ENUM('baseline', 'mid', 'final', 'pmf', name='surveytype', create_type=False), nullable=False),
        sa.Column('pmf_score', sa.Integer(), nullable=True),
        sa.Column('very_disappointed', sa.Boolean(), nullable=True),
        sa.Column('willingness_to_pay', sa.Integer(), nullable=True),
        sa.Column('replacement_behavior', sa.String(length=100), nullable=True),
        sa.Column('time_saved_minutes', sa.Integer(), nullable=True),
        sa.Column('usefulness_score', sa.Integer(), nullable=True),
        sa.Column('query_relevance', sa.Boolean(), nullable=True),
        sa.Column('survey_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=True),
        sa.Column('updated_at', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_surveys_id'), 'surveys', ['id'], unique=False)
    op.create_index(op.f('ix_surveys_user_id'), 'surveys', ['user_id'], unique=False)
    op.create_index(op.f('ix_surveys_survey_type'), 'surveys', ['survey_type'], unique=False)
    
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=True),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('event_metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_resource_type'), 'audit_logs', ['resource_type'], unique=False)
    op.create_index(op.f('ix_audit_logs_resource_id'), 'audit_logs', ['resource_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    
    # Create alerts table
    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('severity', postgresql.ENUM('low', 'medium', 'high', 'critical', name='safetyeventseverity', create_type=False), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('safety_event_id', sa.Integer(), nullable=True),
        sa.Column('related_data', sa.Text(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('is_resolved', sa.Boolean(), nullable=False),
        sa.Column('read_by', sa.Integer(), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.String(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.Column('updated_at', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['safety_event_id'], ['safety_events.id'], ),
        sa.ForeignKeyConstraint(['read_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alerts_id'), 'alerts', ['id'], unique=False)
    op.create_index(op.f('ix_alerts_alert_type'), 'alerts', ['alert_type'], unique=False)
    op.create_index(op.f('ix_alerts_created_at'), 'alerts', ['created_at'], unique=False)


def downgrade() -> None:
    """Drop admin-related tables."""
    op.drop_index(op.f('ix_alerts_created_at'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_alert_type'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_id'), table_name='alerts')
    op.drop_table('alerts')
    
    op.drop_index(op.f('ix_audit_logs_created_at'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_resource_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_resource_type'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_user_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_id'), table_name='audit_logs')
    op.drop_table('audit_logs')
    
    op.drop_index(op.f('ix_surveys_survey_type'), table_name='surveys')
    op.drop_index(op.f('ix_surveys_user_id'), table_name='surveys')
    op.drop_index(op.f('ix_surveys_id'), table_name='surveys')
    op.drop_table('surveys')
    
    op.drop_index(op.f('ix_safety_events_updated_at'), table_name='safety_events')
    op.drop_index(op.f('ix_safety_events_session_id'), table_name='safety_events')
    op.drop_index(op.f('ix_safety_events_message_id'), table_name='safety_events')
    op.drop_index(op.f('ix_safety_events_user_id'), table_name='safety_events')
    op.drop_index(op.f('ix_safety_events_id'), table_name='safety_events')
    op.drop_table('safety_events')
    
    # Drop enums
    sa.Enum(name='safetyeventseverity').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='safetyeventstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='surveytype').drop(op.get_bind(), checkfirst=True)
