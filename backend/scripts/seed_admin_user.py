"""
Seed script to create an admin user if one doesn't exist.
Run this after migrations to ensure at least one admin user exists.
"""

import os
import sys
from datetime import datetime

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load environment variables
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
dotenv_path = os.path.join(project_root, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

from healthnavi.models.user import User
from healthnavi.api.v1.auth import get_password_hash

def get_db_url():
    """Get database URL from environment variables."""
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    db = os.getenv("DB_NAME")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    
    if not all([user, password, db, host, port]):
        raise ValueError("One or more database environment variables are not set.")
    
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"

def seed_admin_user():
    """Create an admin user if one doesn't exist."""
    try:
        # Create database connection
        db_url = get_db_url()
        engine = create_engine(db_url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        # Check if any admin user exists
        existing_admin = db.query(User).filter(
            User.role.in_(["admin", "super_admin"])
        ).first()
        
        if existing_admin:
            print(f"Admin user already exists: {existing_admin.email} (role: {existing_admin.role})")
            db.close()
            return
        
        # Create default admin user
        admin_email = os.getenv("ADMIN_EMAIL", "admin@healthnavi.com")
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
        admin_username = os.getenv("ADMIN_USERNAME", "admin")
        admin_full_name = os.getenv("ADMIN_FULL_NAME", "System Administrator")
        admin_role = os.getenv("ADMIN_ROLE", "super_admin")
        
        # Check if email already exists
        existing_user = db.query(User).filter(User.email == admin_email).first()
        if existing_user:
            # Update existing user to admin
            existing_user.role = admin_role
            existing_user.is_active = True
            existing_user.is_email_verified = True
            existing_user.updated_at = datetime.utcnow().isoformat()
            db.commit()
            print(f"Updated existing user {admin_email} to {admin_role} role")
            db.close()
            return
        
        # Create new admin user
        hashed_password = get_password_hash(admin_password)
        admin_user = User(
            username=admin_username,
            full_name=admin_full_name,
            email=admin_email,
            hashed_password=hashed_password,
            role=admin_role,
            is_active=True,
            is_email_verified=True,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print(f"✅ Admin user created successfully!")
        print(f"   Email: {admin_email}")
        print(f"   Username: {admin_username}")
        print(f"   Role: {admin_role}")
        print(f"   Password: {admin_password}")
        print(f"\n⚠️  Please change the default password after first login!")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    seed_admin_user()
