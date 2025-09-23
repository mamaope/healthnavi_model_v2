# Alembic Migration Fix Guide

## Problem
The error `Can't locate revision identified by 'add_user_fields_001'` occurs because:

1. **Broken Migration Chain**: The migration `add_email_verification_001` was trying to reference a non-existent revision `add_user_fields_001`
2. **Merge Conflicts**: Several files had unresolved merge conflicts that needed to be fixed
3. **Missing Environment Setup**: The environment variables needed for Alembic were not properly configured

## Solution

### 1. Fixed Migration Files

**File: `backend/alembic/versions/add_email_verification_001_add_email_verification_fields.py`**
- Fixed the `down_revision` to properly reference `add_user_roles_001`
- Added proper type hints for better compatibility

### 2. Resolved Merge Conflicts

**File: `backend/Dockerfile`**
- Resolved merge conflict in the credentials file path
- Fixed the uvicorn command to use `healthnavi.main:app`

**File: `docker-compose.yml`**
- Resolved merge conflicts in environment variables
- Fixed the command to use `healthnavi.main:app`

**File: `README.md`**
- Resolved merge conflicts in documentation section

### 3. Migration Chain Structure

The correct migration chain is now:
```
72d72b51ae8e (create_users_table)
    ↓
add_user_roles_001 (add_user_roles_and_timestamps)
    ↓
add_email_verification_001 (add_email_verification_fields)
```

## How to Fix the Issue

### Option 1: Use the Fix Script (Recommended)

1. **Run the PowerShell script:**
   ```powershell
   cd backend
   .\fix_migrations.ps1
   ```

2. **Or run the Python script:**
   ```bash
   cd backend
   python fix_migrations.py
   ```

### Option 2: Manual Fix

1. **Set environment variables:**
   ```powershell
   $env:DB_USER = "healthnavi_user"
   $env:DB_PASSWORD = "SecurePass123!"
   $env:DB_HOST = "localhost"
   $env:DB_PORT = "5432"
   $env:DB_NAME = "healthnavi_cdss"
   $env:PYTHONPATH = "$PWD\src"
   ```

2. **Activate virtual environment:**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

3. **Check current status:**
   ```bash
   alembic current
   alembic history --verbose
   ```

4. **If database is empty, stamp to first migration:**
   ```bash
   alembic stamp 72d72b51ae8e
   ```

5. **Run migrations:**
   ```bash
   alembic upgrade head
   ```

### Option 3: Docker Compose (If using Docker)

1. **Start the database:**
   ```bash
   docker-compose up -d db
   ```

2. **Wait for database to be ready, then start API:**
   ```bash
   docker-compose up api
   ```

## Environment Setup

### Required Environment Variables

Create a `.env` file in the `backend` directory with:

```env
# Database Configuration
DB_USER=healthnavi_user
DB_PASSWORD=SecurePass123!
DB_HOST=localhost
DB_PORT=5432
DB_NAME=healthnavi_cdss

# Security Keys
SECRET_KEY=your-secure-secret-key
ENCRYPTION_KEY=your-encryption-key

# Application Configuration
ENV=development
DEBUG=true
LOG_LEVEL=INFO
```

### Database Setup

1. **Install PostgreSQL** (if not using Docker)
2. **Create database:**
   ```sql
   CREATE DATABASE healthnavi_cdss;
   CREATE USER healthnavi_user WITH PASSWORD 'SecurePass123!';
   GRANT ALL PRIVILEGES ON DATABASE healthnavi_cdss TO healthnavi_user;
   ```

## Verification

After running the fix, verify the setup:

1. **Check migration status:**
   ```bash
   alembic current
   ```

2. **Check database tables:**
   ```sql
   \dt
   ```

3. **Test the API:**
   ```bash
   curl http://localhost:8050/health
   ```

## Troubleshooting

### Common Issues

1. **"Can't locate revision" error:**
   - Run `alembic stamp 72d72b51ae8e` first
   - Then run `alembic upgrade head`

2. **Database connection error:**
   - Check if PostgreSQL is running
   - Verify environment variables
   - Check database credentials

3. **Import errors:**
   - Ensure `PYTHONPATH` includes `src` directory
   - Activate virtual environment
   - Install dependencies: `pip install -r requirements.txt`

4. **Permission errors:**
   - Check file permissions
   - Ensure user has database access

### Reset Database (If needed)

If you need to start fresh:

1. **Drop and recreate database:**
   ```sql
   DROP DATABASE IF EXISTS healthnavi_cdss;
   CREATE DATABASE healthnavi_cdss;
   ```

2. **Run migrations:**
   ```bash
   alembic upgrade head
   ```

## Files Modified

- `backend/alembic/versions/add_email_verification_001_add_email_verification_fields.py`
- `backend/Dockerfile`
- `docker-compose.yml`
- `README.md`
- `backend/fix_migrations.py` (new)
- `backend/fix_migrations.ps1` (new)

## Next Steps

1. Run the fix script
2. Verify migrations are working
3. Test the API endpoints
4. Set up your environment variables
5. Configure external services (email, vector database, etc.)

## Support

If you encounter issues:
1. Check the logs in `backend/logs/`
2. Verify all environment variables are set
3. Ensure database is running and accessible
4. Check that all dependencies are installed
