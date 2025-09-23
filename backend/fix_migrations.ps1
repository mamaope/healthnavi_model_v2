# HealthNavi AI CDSS - Migration Fix Script (PowerShell)
# This script fixes the Alembic migration issues

Write-Host "HealthNavi AI CDSS - Migration Fix Script" -ForegroundColor Green
Write-Host "=" * 50 -ForegroundColor Green

# Set environment variables
Write-Host "`n1. Setting up environment variables..." -ForegroundColor Yellow
$env:DB_USER = "healthnavi_user"
$env:DB_PASSWORD = "SecurePass123!"
$env:DB_HOST = "localhost"
$env:DB_PORT = "5432"
$env:DB_NAME = "healthnavi_cdss"
$env:PYTHONPATH = "$PWD\src"

Write-Host "Environment variables set:" -ForegroundColor Cyan
Write-Host "DB_USER: $env:DB_USER"
Write-Host "DB_HOST: $env:DB_HOST"
Write-Host "DB_NAME: $env:DB_NAME"
Write-Host "PYTHONPATH: $env:PYTHONPATH"

# Check if virtual environment exists
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "`n2. Activating virtual environment..." -ForegroundColor Yellow
    & ".\venv\Scripts\Activate.ps1"
} else {
    Write-Host "`n2. Virtual environment not found. Please create one first:" -ForegroundColor Red
    Write-Host "python -m venv venv" -ForegroundColor White
    Write-Host ".\venv\Scripts\Activate.ps1" -ForegroundColor White
    Write-Host "pip install -r requirements.txt" -ForegroundColor White
    exit 1
}

# Check migration files
Write-Host "`n3. Checking migration files..." -ForegroundColor Yellow
$migrationFiles = @(
    "alembic\versions\72d72b51ae8e_create_users_table.py",
    "alembic\versions\add_user_roles_001_add_user_roles_and_timestamps.py",
    "alembic\versions\add_email_verification_001_add_email_verification_fields.py"
)

$allFilesExist = $true
foreach ($file in $migrationFiles) {
    if (Test-Path $file) {
        Write-Host "✓ $file exists" -ForegroundColor Green
    } else {
        Write-Host "✗ $file missing" -ForegroundColor Red
        $allFilesExist = $false
    }
}

if (-not $allFilesExist) {
    Write-Host "❌ Some migration files are missing!" -ForegroundColor Red
    exit 1
}

# Check current migration status
Write-Host "`n4. Checking current migration status..." -ForegroundColor Yellow
try {
    $current = & alembic current 2>&1
    Write-Host "Current migration status:" -ForegroundColor Cyan
    Write-Host $current
} catch {
    Write-Host "Error checking current migration: $_" -ForegroundColor Red
}

# Show migration history
Write-Host "`n5. Showing migration history..." -ForegroundColor Yellow
try {
    $history = & alembic history --verbose 2>&1
    Write-Host "Migration history:" -ForegroundColor Cyan
    Write-Host $history
} catch {
    Write-Host "Error showing migration history: $_" -ForegroundColor Red
}

# Try to upgrade to head
Write-Host "`n6. Attempting to upgrade to head..." -ForegroundColor Yellow
try {
    $upgrade = & alembic upgrade head 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Migration successful!" -ForegroundColor Green
        Write-Host $upgrade
    } else {
        Write-Host "❌ Migration failed!" -ForegroundColor Red
        Write-Host $upgrade
        
        # Try to stamp the database to the first migration
        Write-Host "`n7. Attempting to stamp database to first migration..." -ForegroundColor Yellow
        $stamp = & alembic stamp 72d72b51ae8e 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Database stamped to first migration" -ForegroundColor Green
            Write-Host $stamp
            
            # Try upgrade again
            Write-Host "`n8. Attempting upgrade again..." -ForegroundColor Yellow
            $upgrade2 = & alembic upgrade head 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✅ Migration successful after stamping!" -ForegroundColor Green
                Write-Host $upgrade2
            } else {
                Write-Host "❌ Migration still failed after stamping!" -ForegroundColor Red
                Write-Host $upgrade2
            }
        } else {
            Write-Host "❌ Failed to stamp database!" -ForegroundColor Red
            Write-Host $stamp
        }
    }
} catch {
    Write-Host "Error running migration: $_" -ForegroundColor Red
}

Write-Host "`nMigration fix script completed." -ForegroundColor Green
