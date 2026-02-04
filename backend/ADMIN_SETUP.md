# Admin Dashboard Setup Guide

This guide will help you set up the admin dashboard by running the database migration and seeding an admin user.

## Prerequisites

1. Ensure your database is running and accessible
2. Set up your `.env` file in the project root with the following variables:
   ```
   DB_USER=your_db_user
   DB_PASSWORD=your_db_password
   DB_NAME=your_db_name
   DB_HOST=your_db_host
   DB_PORT=5432
   ```

## Quick Start with Docker Compose (Recommended)

If you're using Docker Compose, migrations and admin user seeding happen **automatically** when you run:

```bash
docker-compose up
```

The startup script will:
1. Wait for the database to be ready
2. Run all pending migrations (`alembic upgrade head`)
3. Seed an admin user if none exists
4. Start the API server

**No manual steps required!** Just make sure your `.env` file is configured correctly.

## Manual Setup (Without Docker)

If you're running the application manually, follow these steps:

## Step 1: Run Database Migration

The migration will create the following tables:
- `safety_events` - Tracks safety flags and incidents
- `surveys` - Stores PMF, baseline, mid, and final survey responses
- `audit_logs` - Immutable audit trail for compliance
- `alerts` - System alerts for clinical leads

### Option A: Using the Combined Script (Recommended)

```bash
cd backend
python scripts/run_migration_and_seed.py
```

This script will:
1. Run the database migration
2. Seed an admin user if none exists

### Option B: Manual Steps

1. Run the migration:
   ```bash
   cd backend
   python -m alembic upgrade head
   ```

2. Seed the admin user:
   ```bash
   python scripts/seed_admin_user.py
   ```

## Step 2: Verify Admin User

The seed script will create an admin user with the following defaults (can be overridden with environment variables):

- **Email**: `admin@empirico.ai` (set `ADMIN_EMAIL` to change)
- **Username**: `admin` (set `ADMIN_USERNAME` to change)
- **Password**: `admin123` (set `ADMIN_PASSWORD` to change)
- **Role**: `super_admin` (set `ADMIN_ROLE` to change)
- **Full Name**: `System Administrator` (set `ADMIN_FULL_NAME` to change)

### Customizing Admin User

You can set these environment variables in your `.env` file:

```env
ADMIN_EMAIL=your-admin@example.com
ADMIN_PASSWORD=your-secure-password
ADMIN_USERNAME=your-admin-username
ADMIN_FULL_NAME=Your Full Name
ADMIN_ROLE=super_admin  # or "admin"
```

## Step 3: Access the Admin Dashboard

1. Log in to the web application with your admin credentials
2. Click on your user profile in the sidebar
3. Select "Admin Dashboard" from the dropdown menu
4. Or navigate directly to `/admin` in your browser

## Admin Dashboard Features

The admin dashboard provides:

### Usage Panel
- Daily Active Users (DAU)
- Weekly Active Users (WAU)
- Activated users
- Queries per clinician
- Sessions per user
- Retention (Week 1 → Week 3)

### Clinical Value Panel
- % responses marked helpful
- Average usefulness score
- % queries marked relevant
- Average time saved (from surveys)

### Safety Panel
- Flags per 100 queries
- Open safety events
- Critical incidents
- % answers with guideline citations
- % red-flag queries correctly flagged

### PMF Panel
- Heavy users (>20 queries/week)
- Users active in week 3
- % "Very disappointed" (PMF test)
- Replacement behavior (Google / WhatsApp / etc)

### Alerts
- Automatic alerts for critical safety events
- High flag rate warnings (>5% in 24h)
- Missing citations on high-risk queries

## Troubleshooting

### Migration Fails

If the migration fails, check:
1. Database connection settings in `.env`
2. Database user has proper permissions
3. All previous migrations have been applied

### Admin User Not Created

If the admin user is not created:
1. Check if an admin user already exists
2. Verify database connection
3. Check for errors in the seed script output

### Cannot Access Admin Dashboard

If you can't access the admin dashboard:
1. Verify your user has `admin` or `super_admin` role
2. Check browser console for errors
3. Verify the backend API is running and accessible

## Security Notes

⚠️ **IMPORTANT**: Change the default admin password immediately after first login!

The default password (`admin123`) is not secure and should only be used for initial setup.

## Next Steps

After setup:
1. Change the admin password
2. Configure alert thresholds if needed
3. Set up survey collection endpoints (if not already done)
4. Configure safety event creation logic in your application
