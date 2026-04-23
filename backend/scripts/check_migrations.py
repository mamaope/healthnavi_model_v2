#!/usr/bin/env python3
"""
Script to check migration status in production.
This can be run manually or as part of health checks.
"""
import os
import sys
import subprocess
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir / "src"))

def check_migration_status():
    """Check if migrations are up to date."""
    print("🔍 Checking migration status...")
    
    try:
        # Get current revision
        result = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True,
            cwd=backend_dir
        )
        
        if result.returncode != 0:
            print(f"❌ Error checking current revision: {result.stderr}")
            return False
        
        current_output = result.stdout.strip()
        print(f"   Current: {current_output}")
        
        # Get head revision
        result = subprocess.run(
            ["alembic", "heads"],
            capture_output=True,
            text=True,
            cwd=backend_dir
        )
        
        if result.returncode != 0:
            print(f"❌ Error checking head revision: {result.stderr}")
            return False
        
        head_output = result.stdout.strip()
        print(f"   Head: {head_output}")
        
        # Compare current and head to check if up to date
        current_rev = None
        head_rev = None
        
        # Extract revision from current output
        import re
        current_match = re.search(r'([a-f0-9]+)', current_output)
        if current_match:
            current_rev = current_match.group(1)
        
        # Extract revision from head output
        head_match = re.search(r'([a-f0-9]+)', head_output)
        if head_match:
            head_rev = head_match.group(1)
        
        if current_rev and head_rev:
            if current_rev == head_rev:
                print("✅ All migrations are applied!")
                return True
            else:
                print(f"⚠️  Current revision ({current_rev}) differs from head ({head_rev})")
                print("   There may be pending migrations.")
                return False
        else:
            print("⚠️  Could not determine revision status.")
            return False
            
    except Exception as e:
        print(f"❌ Error checking migration status: {e}")
        return False


def show_migration_history():
    """Show migration history."""
    print("\n📜 Migration History:")
    try:
        result = subprocess.run(
            ["alembic", "history"],
            capture_output=True,
            text=True,
            cwd=backend_dir
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"Error: {result.stderr}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    success = check_migration_status()
    if len(sys.argv) > 1 and sys.argv[1] == "--history":
        show_migration_history()
    sys.exit(0 if success else 1)
