"""
Combined script to run migration and seed admin user.
This script will:
1. Run the database migration to create admin tables
2. Seed at least one admin user if none exists
"""

import os
import sys
import subprocess
from pathlib import Path

# Get the backend directory
backend_dir = Path(__file__).parent.parent
os.chdir(backend_dir)

def run_migration():
    """Run Alembic migration to create admin tables."""
    print("🔄 Running database migration...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend_dir,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✅ Migration completed successfully!")
            return True
        else:
            print(f"❌ Migration failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error running migration: {e}")
        return False

def seed_admin():
    """Run the seed script to create admin user."""
    print("\n🌱 Seeding admin user...")
    try:
        seed_script = backend_dir / "scripts" / "seed_admin_user.py"
        result = subprocess.run(
            [sys.executable, str(seed_script)],
            cwd=backend_dir,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error seeding admin user: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Empirico Admin Setup")
    print("=" * 60)
    
    # Check if .env file exists
    env_file = backend_dir / ".env"
    if not env_file.exists():
        print("\n⚠️  Warning: .env file not found!")
        print("Please ensure your database environment variables are set:")
        print("  - DB_USER")
        print("  - DB_PASSWORD")
        print("  - DB_NAME")
        print("  - DB_HOST")
        print("  - DB_PORT")
        print("\nOptional admin user variables:")
        print("  - ADMIN_EMAIL (default: admin@empirico.ai)")
        print("  - ADMIN_PASSWORD (default: admin123)")
        print("  - ADMIN_USERNAME (default: admin)")
        print("  - ADMIN_FULL_NAME (default: System Administrator)")
        print("  - ADMIN_ROLE (default: super_admin)")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    # Run migration
    if not run_migration():
        print("\n❌ Migration failed. Please check your database configuration.")
        sys.exit(1)
    
    # Seed admin user
    if not seed_admin():
        print("\n⚠️  Admin user seeding had issues, but migration completed.")
        print("You can manually run: python scripts/seed_admin_user.py")
    
    print("\n" + "=" * 60)
    print("✅ Setup complete!")
    print("=" * 60)
