-- Empirico database initialization.
-- The database itself is created by the official Postgres image from POSTGRES_DB.

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create the application user if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'healthnavi_user') THEN
        CREATE USER healthnavi_user WITH PASSWORD 'SecurePass123!';
    END IF;
END
$$;

-- Grant privileges to the application user
DO $$
BEGIN
    EXECUTE format('GRANT ALL PRIVILEGES ON DATABASE %I TO healthnavi_user', current_database());
END
$$;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO healthnavi_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO healthnavi_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO healthnavi_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO healthnavi_user;

-- Set up security
DO $$
BEGIN
    EXECUTE format('ALTER DATABASE %I SET log_min_duration_statement = 1000', current_database());
END
$$;

-- Create a read-only user for monitoring
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'healthnavi_monitor') THEN
        CREATE ROLE healthnavi_monitor WITH LOGIN PASSWORD 'monitor_password_change_me';
        EXECUTE format('GRANT CONNECT ON DATABASE %I TO healthnavi_monitor', current_database());
        GRANT USAGE ON SCHEMA public TO healthnavi_monitor;
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO healthnavi_monitor;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO healthnavi_monitor;
    END IF;
END
$$;

-- Create indexes for performance (will be created by Alembic migrations)
-- These are just examples of what will be created

-- Security audit log indexes
-- CREATE INDEX IF NOT EXISTS idx_audit_log_user_action ON audit_logs(user_id, action);
-- CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_logs(created_at);
-- CREATE INDEX IF NOT EXISTS idx_audit_log_success ON audit_logs(success);

-- User table indexes
-- CREATE INDEX IF NOT EXISTS idx_user_email_active ON users(email, is_active);
-- CREATE INDEX IF NOT EXISTS idx_user_username_active ON users(username, is_active);

-- Diagnosis session indexes
-- CREATE INDEX IF NOT EXISTS idx_diagnosis_user_session ON diagnosis_sessions(user_id, session_id);
-- CREATE INDEX IF NOT EXISTS idx_diagnosis_created_at ON diagnosis_sessions(created_at);

-- Security event indexes
-- CREATE INDEX IF NOT EXISTS idx_security_event_type ON security_events(event_type);
-- CREATE INDEX IF NOT EXISTS idx_security_severity ON security_events(severity);
-- CREATE INDEX IF NOT EXISTS idx_security_resolved ON security_events(resolved);
-- CREATE INDEX IF NOT EXISTS idx_security_created_at ON security_events(created_at);

-- No pg_stat_statements setup here; local Postgres images do not load that
-- extension by default, and referencing it aborts fresh container initialization.
