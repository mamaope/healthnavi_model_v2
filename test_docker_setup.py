#!/usr/bin/env python3
"""
Test script to verify Docker setup and database models.
This script can be run inside the Docker container to test the setup.
"""

import os
import sys
import traceback

def test_imports():
    """Test that all required modules can be imported."""
    print("🔍 Testing imports...")
    
    try:
        # Test basic imports
        from healthnavi.models.user import User
        from healthnavi.models.diagnosis_session import DiagnosisSession, ChatMessage
        from healthnavi.models.base import Base
        print("✅ All model imports successful")
        
        # Test that models are registered with Base
        tables = Base.metadata.tables.keys()
        expected_tables = {'users', 'diagnosis_sessions', 'chat_messages'}
        
        if expected_tables.issubset(tables):
            print("✅ All expected tables are registered")
        else:
            missing = expected_tables - set(tables)
            print(f"❌ Missing tables: {missing}")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        traceback.print_exc()
        return False

def test_database_connection():
    """Test database connection."""
    print("\n🔍 Testing database connection...")
    
    try:
        from healthnavi.core.database import get_db
        from sqlalchemy.orm import Session
        
        # Try to get a database session
        db = next(get_db())
        if isinstance(db, Session):
            print("✅ Database connection successful")
            return True
        else:
            print("❌ Database connection failed - invalid session type")
            return False
            
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        traceback.print_exc()
        return False

def test_alembic_migrations():
    """Test Alembic migration status."""
    print("\n🔍 Testing Alembic migrations...")
    
    try:
        from alembic import command
        from alembic.config import Config
        
        # Create Alembic config
        alembic_cfg = Config("alembic.ini")
        
        # Check current revision
        from alembic.runtime.migration import MigrationContext
        from healthnavi.core.database import engine
        
        context = MigrationContext.configure(engine.connect())
        current_rev = context.get_current_revision()
        
        if current_rev:
            print(f"✅ Current migration revision: {current_rev}")
            return True
        else:
            print("❌ No migration revision found")
            return False
            
    except Exception as e:
        print(f"❌ Alembic test error: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("🏥 HealthNavi AI CDSS - Docker Setup Test")
    print("=" * 50)
    
    # Set Python path
    if '/app/src' not in sys.path:
        sys.path.insert(0, '/app/src')
    
    tests = [
        test_imports,
        test_database_connection,
        test_alembic_migrations
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ All {total} tests passed!")
        return 0
    else:
        print(f"❌ {total - passed} out of {total} tests failed")
        return 1

if __name__ == "__main__":
    exit(main())








