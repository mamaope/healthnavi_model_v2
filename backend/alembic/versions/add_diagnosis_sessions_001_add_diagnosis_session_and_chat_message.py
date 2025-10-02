"""Add diagnosis session and chat message models

Revision ID: add_diagnosis_sessions_001
Revises: add_email_verification_001
Create Date: 2024-12-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_diagnosis_sessions_001'
down_revision = 'add_email_verification_001'
branch_labels = None
depends_on = None


def upgrade():
    # Create diagnosis_sessions table
    op.create_table('diagnosis_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('session_name', sa.String(length=255), nullable=True),
    sa.Column('patient_summary', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.String(), nullable=True),
    sa.Column('updated_at', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_diagnosis_sessions_id'), 'diagnosis_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_diagnosis_sessions_user_id'), 'diagnosis_sessions', ['user_id'], unique=False)

    # Create chat_messages table
    op.create_table('chat_messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.Integer(), nullable=False),
    sa.Column('message_type', sa.String(length=20), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('patient_data', sa.Text(), nullable=True),
    sa.Column('diagnosis_complete', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_messages_id'), 'chat_messages', ['id'], unique=False)
    op.create_index(op.f('ix_chat_messages_session_id'), 'chat_messages', ['session_id'], unique=False)


def downgrade():
    # Drop chat_messages table
    op.drop_index(op.f('ix_chat_messages_session_id'), table_name='chat_messages')
    op.drop_index(op.f('ix_chat_messages_id'), table_name='chat_messages')
    op.drop_table('chat_messages')

    # Drop diagnosis_sessions table
    op.drop_index(op.f('ix_diagnosis_sessions_user_id'), table_name='diagnosis_sessions')
    op.drop_index(op.f('ix_diagnosis_sessions_id'), table_name='diagnosis_sessions')
    op.drop_table('diagnosis_sessions')
