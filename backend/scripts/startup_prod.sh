#!/bin/bash
set -e

# Ensure we're in the backend directory
cd /backend

echo "🚀 Starting Empirico API (Production)..."

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

# Run migrations with verification
echo "🔄 Running database migrations..."
if alembic upgrade head; then
    echo "✅ Migrations completed successfully!"
    
    # Verify migration status
    echo "📊 Verifying migration status..."
    CURRENT_OUTPUT=$(alembic current 2>/dev/null || echo "")
    HEAD_OUTPUT=$(alembic heads 2>/dev/null || echo "")
    
    if [ -n "$CURRENT_OUTPUT" ]; then
        echo "   Current: $CURRENT_OUTPUT"
    fi
    if [ -n "$HEAD_OUTPUT" ]; then
        echo "   Head: $HEAD_OUTPUT"
    fi
    
    # Check if we're at head by comparing outputs
    if [ -n "$CURRENT_OUTPUT" ] && [ -n "$HEAD_OUTPUT" ]; then
        # Extract revision IDs (handles both short and long formats)
        CURRENT_REV=$(echo "$CURRENT_OUTPUT" | grep -oE '[a-f0-9]+' | head -1 || echo "")
        HEAD_REV=$(echo "$HEAD_OUTPUT" | grep -oE '[a-f0-9]+' | head -1 || echo "")
        
        if [ -n "$CURRENT_REV" ] && [ -n "$HEAD_REV" ] && [ "$CURRENT_REV" = "$HEAD_REV" ]; then
            echo "✅ Database is up to date!"
        elif [ -n "$CURRENT_REV" ] && [ -n "$HEAD_REV" ]; then
            echo "⚠️  Warning: Current revision ($CURRENT_REV) differs from head ($HEAD_REV)"
        fi
    fi
else
    echo "❌ Migration failed! Exiting..."
    echo "   Check the logs above for details."
    exit 1
fi

# Seed admin user
echo "🌱 Seeding admin user..."
python /backend/scripts/seed_admin_user.py

# Start the application
WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"
echo "🚀 Starting API server..."
exec uvicorn healthnavi.main:app --host 0.0.0.0 --port 8050 --workers "$WEB_CONCURRENCY" --timeout-keep-alive 120
