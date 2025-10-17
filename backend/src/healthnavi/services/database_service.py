"""
Database service for HealthNavi AI CDSS.
"""

from sqlalchemy.orm import Session
from healthnavi.core.database import get_db, SessionLocal


def get_database_session() -> Session:
    """Get a database session."""
    return SessionLocal()


# Export the get_db function for dependency injection
__all__ = ["get_db", "get_database_session"]