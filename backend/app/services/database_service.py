"""
Database Service for HealthNavi AI CDSS

This service handles all database operations including user management,
authentication, and data persistence.
"""

import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import hashlib
import secrets

from app.models.database import SessionLocal, engine
from app.models.user import User, Base, UserRole

logger = logging.getLogger(__name__)

class DatabaseService:
    """Service class for database operations."""
    
    def __init__(self):
        """Initialize database service."""
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def get_db(self) -> Session:
        """Get database session."""
        db = self.SessionLocal()
        try:
            return db
        except Exception as e:
            logger.error(f"Database session error: {e}")
            db.close()
            raise
    
    def create_tables(self):
        """Create all database tables."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except SQLAlchemyError as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    def hash_password(self, password: str) -> str:
        """Hash password using SHA-256 with salt."""
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{password_hash}"
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        try:
            salt, password_hash = hashed_password.split(':')
            return hashlib.sha256((password + salt).encode()).hexdigest() == password_hash
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    def create_user(self, first_name: str, last_name: str, email: str, password: str, verification_token: str = None, role: str = "USER") -> Optional[User]:
        """Create a new user."""
        db = self.get_db()
        try:
            # Check if user already exists
            existing_user = db.query(User).filter(User.email == email.lower()).first()
            if existing_user:
                logger.warning(f"User with email {email} already exists")
                return None
            
            # Convert role string to UserRole enum
            try:
                user_role = UserRole(role.upper())
            except ValueError:
                logger.warning(f"Invalid role '{role}', using default 'USER'")
                user_role = UserRole.USER
            
            # Create new user
            hashed_password = self.hash_password(password)
            user = User(
                first_name=first_name,
                last_name=last_name,
                email=email.lower(),
                password_hash=hashed_password,
                active=False,
                email_verified=False,
                verification_token=verification_token,
                role=user_role,
                created_at=datetime.utcnow()
            )
            
            db.add(user)
            db.commit()
            db.refresh(user)
            
            logger.info(f"User created successfully: {email}")
            return user
            
        except SQLAlchemyError as e:
            logger.error(f"Error creating user: {e}")
            db.rollback()
            return None
        finally:
            db.close()
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        db = self.get_db()
        try:
            user = db.query(User).filter(User.email == email.lower()).first()
            return user
        except SQLAlchemyError as e:
            logger.error(f"Error getting user by email: {e}")
            return None
        finally:
            db.close()
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        db = self.get_db()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            return user
        except SQLAlchemyError as e:
            logger.error(f"Error getting user by ID: {e}")
            return None
        finally:
            db.close()
    
    def verify_user_email(self, email: str, verification_token: str) -> bool:
        """Verify user email address."""
        db = self.get_db()
        try:
            user = db.query(User).filter(User.email == email.lower()).first()
            if not user:
                logger.warning(f"User not found for email: {email}")
                return False
            
            if user.email_verified:
                logger.info(f"Email already verified for user: {email}")
                return True
            
            if user.verification_token != verification_token:
                logger.warning(f"Invalid verification token for user: {email}")
                return False
            
            # Update user verification status
            user.email_verified = True
            user.active = True
            user.verified_at = datetime.utcnow()
            user.verification_token = None  # Clear token after use
            
            db.commit()
            logger.info(f"Email verified successfully for user: {email}")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Error verifying email: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    def update_user_verification_token(self, email: str, new_token: str) -> bool:
        """Update user verification token."""
        db = self.get_db()
        try:
            user = db.query(User).filter(User.email == email.lower()).first()
            if not user:
                logger.warning(f"User not found for email: {email}")
                return False
            
            user.verification_token = new_token
            db.commit()
            logger.info(f"Verification token updated for user: {email}")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Error updating verification token: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    def update_last_login(self, email: str) -> bool:
        """Update user's last login timestamp."""
        db = self.get_db()
        try:
            user = db.query(User).filter(User.email == email.lower()).first()
            if not user:
                logger.warning(f"User not found for email: {email}")
                return False
            
            user.last_login = datetime.utcnow()
            db.commit()
            logger.info(f"Last login updated for user: {email}")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Error updating last login: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    def get_all_users(self) -> List[User]:
        """Get all users (for admin purposes)."""
        db = self.get_db()
        try:
            users = db.query(User).all()
            return users
        except SQLAlchemyError as e:
            logger.error(f"Error getting all users: {e}")
            return []
        finally:
            db.close()
    
    def delete_user(self, email: str) -> bool:
        """Delete user account."""
        db = self.get_db()
        try:
            user = db.query(User).filter(User.email == email.lower()).first()
            if not user:
                logger.warning(f"User not found for email: {email}")
                return False
            
            db.delete(user)
            db.commit()
            logger.info(f"User deleted successfully: {email}")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Error deleting user: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            db = self.get_db()
            db.execute("SELECT 1")
            db.close()
            logger.info("Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

# Global database service instance
db_service = DatabaseService()
