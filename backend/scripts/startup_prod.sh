#!/bin/bash
set -e

# Ensure we're in the backend directory
cd /backend

echo "🚀 Starting HealthNavi API (Production)..."

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
until python -c "
import os
import psycopg2
try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=int(os.getenv('DB_PORT', 5432)),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )
    conn.close()
    exit(0)
except Exception:
    exit(1)
" 2>/dev/null; do
  echo "Database is unavailable - sleeping"
  sleep 1
done

echo "✅ Database is ready!"

# Run migrations
echo "🔄 Running database migrations..."
alembic upgrade head

# Seed admin user
echo "🌱 Seeding admin user..."
python /backend/scripts/seed_admin_user.py

# Start the application
echo "🚀 Starting API server..."
exec uvicorn healthnavi.main:app --host 0.0.0.0 --port 8050 --timeout-keep-alive 120
