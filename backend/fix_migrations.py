#!/usr/bin/env python3
"""
Fix Alembic Migration Issues for HealthNavi AI CDSS

This script resolves the 'add_user_fields_001' migration error by:
1. Setting up the environment
2. Checking migration files
3. Running migrations in the correct order
"""

import os
import sys
import subprocess
from pathlib import Path

def setup_environment():
    """Set up environment variables for Alembic"""
    env_vars = {
        'DB_USER': 'healthnavi_user',
        'DB_PASSWORD': 'SecurePass123!',
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'DB_NAME': 'healthnavi_cdss',
        'PYTHONPATH': str(Path(__file__).parent / 'src')
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
        print(f"Set {key}={value}")

def check_migration_files():
    """Check if migration files exist and are properly formatted"""
    versions_dir = Path(__file__).parent / 'alembic' / 'versions'
    
    migration_files = [
        '72d72b51ae8e_create_users_table.py',
        'add_user_roles_001_add_user_roles_and_timestamps.py',
        'add_email_verification_001_add_email_verification_fields.py'
    ]
    
    print("\nChecking migration files:")
    for file in migration_files:
        file_path = versions_dir / file
        if file_path.exists():
            print(f"✓ {file} exists")
        else:
            print(f"✗ {file} missing")
    
    return all((versions_dir / file).exists() for file in migration_files)

def run_alembic_command(command):
    """Run an Alembic command"""
    try:
        result = subprocess.run(
            ['alembic'] + command.split(),
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            env=os.environ.copy()
        )
        
        print(f"\nRunning: alembic {' '.join(command.split())}")
        print(f"Return code: {result.returncode}")
        
        if result.stdout:
            print("STDOUT:")
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"Error running alembic command: {e}")
        return False

def main():
    """Main function to fix migration issues"""
    print("HealthNavi AI CDSS - Migration Fix Script")
    print("=" * 50)
    
    # Setup environment
    print("\n1. Setting up environment...")
    setup_environment()
    
    # Check migration files
    print("\n2. Checking migration files...")
    if not check_migration_files():
        print("❌ Some migration files are missing!")
        return False
    
    # Check current migration status
    print("\n3. Checking current migration status...")
    run_alembic_command("current")
    
    # Show migration history
    print("\n4. Showing migration history...")
    run_alembic_command("history --verbose")
    
    # Try to upgrade to head
    print("\n5. Attempting to upgrade to head...")
    if run_alembic_command("upgrade head"):
        print("✅ Migration successful!")
        return True
    else:
        print("❌ Migration failed!")
        
        # Try to stamp the database to the first migration
        print("\n6. Attempting to stamp database to first migration...")
        if run_alembic_command("stamp 72d72b51ae8e"):
            print("✅ Database stamped to first migration")
            
            # Try upgrade again
            print("\n7. Attempting upgrade again...")
            if run_alembic_command("upgrade head"):
                print("✅ Migration successful after stamping!")
                return True
        
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
