# Database Migration Guide for Production

This guide explains how to ensure database migrations are properly implemented in production.

## Automatic Migration on Startup

Migrations run **automatically** when the production container starts via `startup_prod.sh`. The script:

1. ✅ Waits for the database to be ready
2. ✅ Runs `alembic upgrade head` to apply all pending migrations
3. ✅ Verifies the migration status
4. ✅ Seeds the admin user
5. ✅ Starts the API server

## Verifying Migrations in Production

### Method 1: Check Container Logs

When the container starts, you'll see migration output:

```bash
docker logs healthnavi_cdss_api | grep -A 10 "migration"
```

Look for:
- `🔄 Running database migrations...`
- `✅ Migrations completed successfully!`
- `✅ Database is up to date!`

### Method 2: Manual Migration Check Script

Run the migration check script inside the container:

```bash
# Check migration status
docker exec healthnavi_cdss_api python /backend/scripts/check_migrations.py

# Check migration status with history
docker exec healthnavi_cdss_api python /backend/scripts/check_migrations.py --history
```

### Method 3: Direct Alembic Commands

You can also run Alembic commands directly:

```bash
# Check current revision
docker exec healthnavi_cdss_api alembic current

# Check head revision
docker exec healthnavi_cdss_api alembic heads

# Show migration history
docker exec healthnavi_cdss_api alembic history

# Check for pending migrations
docker exec healthnavi_cdss_api alembic check
```

### Method 4: Database Query

Check the `alembic_version` table directly:

```bash
docker exec -it healthnavi_cdss_postgres psql -U $DB_USER -d $DB_NAME -c "SELECT * FROM alembic_version;"
```

## Troubleshooting

### Migration Failed on Startup

If migrations fail, the container will exit with an error. Check logs:

```bash
docker logs healthnavi_cdss_api
```

Common issues:
- **Database not ready**: The script waits for DB, but if it times out, check DB health
- **Connection issues**: Verify `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` environment variables
- **Migration conflicts**: Check if there are conflicting migrations or manual schema changes

### Manual Migration Run

If you need to run migrations manually:

```bash
# Enter the container
docker exec -it healthnavi_cdss_api bash

# Run migrations
cd /backend
alembic upgrade head

# Verify
alembic current
```

### Rollback (Use with Caution!)

⚠️ **Only rollback in development or if absolutely necessary in production**

```bash
# Rollback one migration
docker exec healthnavi_cdss_api alembic downgrade -1

# Rollback to specific revision
docker exec healthnavi_cdss_api alembic downgrade <revision_id>
```

## Best Practices

1. **Always test migrations locally** before deploying to production
2. **Backup your database** before running migrations in production
3. **Monitor migration logs** during deployment
4. **Use idempotent migrations** - migrations should be safe to run multiple times
5. **Check migration status** after deployment to verify success

## Migration Status Indicators

- ✅ `✅ Migrations completed successfully!` - All migrations applied
- ✅ `✅ Database is up to date!` - Current revision matches head
- ⚠️ `⚠️ Warning: Current revision differs from head` - Potential issue
- ❌ `❌ Migration failed!` - Migration error, container will exit

## Health Check Integration

The migration check script can be integrated into health checks:

```bash
# Add to health check
docker exec healthnavi_cdss_api python /backend/scripts/check_migrations.py && echo "Migrations OK" || echo "Migration issue"
```

## Environment Variables Required

Ensure these are set in your `.env` file or environment:

```bash
DB_HOST=your_db_host
DB_PORT=5432
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=your_db_name
```

These are used by Alembic's `env.py` to construct the database connection URL.
