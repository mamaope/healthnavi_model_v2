"""fix device_activity_log id to use a sequence if it was created without one

If the table was created by an older revision without autoincrement, this adds
a sequence and default so inserts work. Safe to run if the column already has a default.

Revision ID: fix_device_activity_log_id_serial
Revises: add_device_activity_log
Create Date: 2025-01-20

"""
from alembic import op


revision = 'fix_device_activity_log_id'
down_revision = 'add_device_activity_log'
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL: ensure id has a default so ORM inserts work. If the table was
    # created with SERIAL/autoincrement, the sequence exists and this is a no-op.
    op.execute("CREATE SEQUENCE IF NOT EXISTS device_activity_log_id_seq")
    op.execute("""
        ALTER TABLE device_activity_log
        ALTER COLUMN id SET DEFAULT nextval('device_activity_log_id_seq')
    """)
    op.execute("SELECT setval('device_activity_log_id_seq', COALESCE((SELECT MAX(id) FROM device_activity_log), 1))")


def downgrade():
    op.execute("ALTER TABLE device_activity_log ALTER COLUMN id DROP DEFAULT")
    # Optionally: DROP SEQUENCE device_activity_log_id_seq; leave it for re-upgrade.
