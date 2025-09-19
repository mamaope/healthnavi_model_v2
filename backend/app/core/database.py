"""
Enhanced database service for HealthNavi AI CDSS.

This module provides secure database operations with proper connection management,
transaction handling, and audit logging following medical software standards.
"""

import logging
from typing import Generator, Optional
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from contextlib import contextmanager

from app.core.config import get_config
from app.core.models import Base, AuditLog, SecurityEvent
from app.core.security import SecureLogger

config = get_config()
logger = logging.getLogger(__name__)

# Database engine with enhanced security settings
engine = create_engine(
    config.get_database_url(),
    poolclass=QueuePool,
    pool_size=config.database.db_pool_size,
    max_overflow=config.database.db_max_overflow,
    pool_timeout=config.database.db_pool_timeout,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,   # Recycle connections every hour
    echo=config.application.debug,  # Log SQL queries in debug mode
    echo_pool=config.application.debug,  # Log pool events in debug mode
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Get database session with proper error handling and cleanup.
    
    Yields:
        Database session
        
    Raises:
        SQLAlchemyError: If database connection fails
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Unexpected error in database session: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_transaction():
    """
    Get database session with transaction management.
    
    Yields:
        Database session with transaction support
        
    Raises:
        SQLAlchemyError: If database operation fails
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except SQLAlchemyError as e:
        logger.error(f"Database transaction error: {e}")
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Unexpected error in database transaction: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def create_tables():
    """Create all database tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except SQLAlchemyError as e:
        logger.error(f"Failed to create database tables: {e}")
        raise


def drop_tables():
    """Drop all database tables."""
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("Database tables dropped successfully")
    except SQLAlchemyError as e:
        logger.error(f"Failed to drop database tables: {e}")
        raise


def check_database_connection() -> bool:
    """
    Check if database connection is working.
    
    Returns:
        True if connection is successful, False otherwise
    """
    try:
        with engine.connect() as connection:
            connection.execute("SELECT 1")
        logger.info("Database connection check successful")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Database connection check failed: {e}")
        return False


def get_database_stats() -> dict:
    """
    Get database statistics.
    
    Returns:
        Dictionary with database statistics
    """
    try:
        with engine.connect() as connection:
            # Get connection pool stats
            pool = engine.pool
            stats = {
                'pool_size': pool.size(),
                'checked_in': pool.checkedin(),
                'checked_out': pool.checkedout(),
                'overflow': pool.overflow(),
                'invalid': pool.invalid(),
            }
            
            # Get table counts
            from app.core.models import User, AuditLog, SecurityEvent, DiagnosisSession
            
            with SessionLocal() as session:
                stats['user_count'] = session.query(User).count()
                stats['audit_log_count'] = session.query(AuditLog).count()
                stats['security_event_count'] = session.query(SecurityEvent).count()
                stats['diagnosis_session_count'] = session.query(DiagnosisSession).count()
            
            return stats
            
    except SQLAlchemyError as e:
        logger.error(f"Failed to get database stats: {e}")
        return {}


class DatabaseAuditLogger:
    """Database audit logging utility."""
    
    @staticmethod
    def log_user_action(
        db: Session,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        action: str = "",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> AuditLog:
        """Log user action to audit log."""
        try:
            audit_log = AuditLog(
                user_id=user_id,
                username=username,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details,
                success=success,
                error_message=error_message
            )
            
            db.add(audit_log)
            db.commit()
            
            SecureLogger.log_securely('info', f'Audit log created: {action} for user {username}')
            return audit_log
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
            db.rollback()
            raise
    
    @staticmethod
    def log_security_event(
        db: Session,
        event_type: str,
        severity: str,
        details: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None
    ) -> SecurityEvent:
        """Log security event."""
        try:
            security_event = SecurityEvent(
                event_type=event_type,
                severity=severity,
                details=details,
                user_id=user_id,
                ip_address=ip_address
            )
            
            db.add(security_event)
            db.commit()
            
            SecureLogger.log_securely('warning', f'Security event logged: {event_type} - {severity}')
            return security_event
            
        except Exception as e:
            logger.error(f"Failed to create security event log: {e}")
            db.rollback()
            raise


class DatabaseHealthChecker:
    """Database health monitoring utility."""
    
    @staticmethod
    def check_health() -> dict:
        """
        Perform comprehensive database health check.
        
        Returns:
            Dictionary with health check results
        """
        health_status = {
            'database_connection': False,
            'table_access': False,
            'pool_status': 'unknown',
            'response_time_ms': None,
            'errors': []
        }
        
        try:
            import time
            start_time = time.time()
            
            # Test basic connection
            with engine.connect() as connection:
                connection.execute("SELECT 1")
                health_status['database_connection'] = True
            
            # Test table access
            with SessionLocal() as session:
                from app.core.models import User
                session.query(User).limit(1).all()
                health_status['table_access'] = True
            
            # Get pool status
            pool = engine.pool
            health_status['pool_status'] = {
                'size': pool.size(),
                'checked_in': pool.checkedin(),
                'checked_out': pool.checkedout(),
                'overflow': pool.overflow(),
                'invalid': pool.invalid(),
            }
            
            # Calculate response time
            end_time = time.time()
            health_status['response_time_ms'] = round((end_time - start_time) * 1000, 2)
            
        except SQLAlchemyError as e:
            health_status['errors'].append(f"Database error: {str(e)}")
            logger.error(f"Database health check failed: {e}")
        
        except Exception as e:
            health_status['errors'].append(f"Unexpected error: {str(e)}")
            logger.error(f"Unexpected error in database health check: {e}")
        
        return health_status


# Database event listeners for additional security
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set database connection parameters for security."""
    if 'postgresql' in str(dbapi_connection):
        # PostgreSQL specific settings
        with dbapi_connection.cursor() as cursor:
            # Set statement timeout (5 minutes)
            cursor.execute("SET statement_timeout = '300s'")
            # Set idle transaction timeout (10 minutes)
            cursor.execute("SET idle_in_transaction_session_timeout = '600s'")


@event.listens_for(engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log SQL queries in debug mode."""
    if config.application.debug:
        logger.debug(f"SQL Query: {statement}")
        if parameters:
            logger.debug(f"SQL Parameters: {parameters}")


# Initialize database on module import
def initialize_database():
    """Initialize database connection and create tables if needed."""
    try:
        # Check connection
        if not check_database_connection():
            raise RuntimeError("Database connection failed")
        
        # Create tables if they don't exist
        create_tables()
        
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


# Auto-initialize on import
if config.application.environment != 'test':
    initialize_database()
