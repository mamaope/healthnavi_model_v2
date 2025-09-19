"""
Enhanced database models for HealthNavi AI CDSS.

This module provides secure database models with proper validation,
audit trails, and data protection following medical software standards.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()


class User(Base):
    """Enhanced user model with audit fields and security features."""
    
    __tablename__ = "users"
    
    # Primary fields
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    login_count = Column(Integer, default=0, nullable=False)
    
    # Security fields
    password_changed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_email_active', 'email', 'is_active'),
        Index('idx_user_username_active', 'username', 'is_active'),
    )
    
    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}', active={self.is_active})>"
    
    def is_locked(self) -> bool:
        """Check if user account is locked."""
        if self.locked_until:
            return datetime.utcnow() < self.locked_until
        return False
    
    def increment_login_count(self):
        """Increment login count and update last login time."""
        self.login_count += 1
        self.last_login_at = datetime.utcnow()
        self.failed_login_attempts = 0  # Reset failed attempts on successful login


class AuditLog(Base):
    """Audit log for tracking user actions and system events."""
    
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)  # Null for system events
    username = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False)  # e.g., 'login', 'diagnosis_request', 'user_created'
    resource_type = Column(String(50), nullable=True)  # e.g., 'user', 'diagnosis', 'system'
    resource_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    details = Column(Text, nullable=True)  # JSON string with additional details
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_audit_user_action', 'user_id', 'action'),
        Index('idx_audit_created_at', 'created_at'),
        Index('idx_audit_success', 'success'),
    )
    
    def __repr__(self):
        return f"<AuditLog(user_id={self.user_id}, action='{self.action}', success={self.success})>"


class DiagnosisSession(Base):
    """Track diagnosis sessions for audit and analytics."""
    
    __tablename__ = "diagnosis_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    session_id = Column(String(100), unique=True, nullable=False)  # UUID for session tracking
    patient_data_hash = Column(String(64), nullable=False)  # SHA-256 hash of patient data
    query_count = Column(Integer, default=0, nullable=False)
    diagnosis_complete = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_diagnosis_user_session', 'user_id', 'session_id'),
        Index('idx_diagnosis_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<DiagnosisSession(user_id={self.user_id}, session_id='{self.session_id}', complete={self.diagnosis_complete})>"


class DiagnosisQuery(Base):
    """Track individual diagnosis queries within sessions."""
    
    __tablename__ = "diagnosis_queries"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), nullable=False)
    user_id = Column(Integer, nullable=False)
    query_text_hash = Column(String(64), nullable=False)  # SHA-256 hash of query
    response_length = Column(Integer, nullable=False)
    processing_time_ms = Column(Integer, nullable=False)
    sources_used = Column(Text, nullable=True)  # JSON string of sources
    model_version = Column(String(50), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_query_session', 'session_id'),
        Index('idx_query_user', 'user_id'),
        Index('idx_query_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<DiagnosisQuery(session_id='{self.session_id}', response_length={self.response_length})>"


class SystemConfiguration(Base):
    """Store system configuration settings."""
    
    __tablename__ = "system_configurations"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    is_encrypted = Column(Boolean, default=False, nullable=False)
    updated_by = Column(Integer, nullable=True)  # User ID who updated
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<SystemConfiguration(key='{self.key}', encrypted={self.is_encrypted})>"


class SecurityEvent(Base):
    """Track security-related events."""
    
    __tablename__ = "security_events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False)  # e.g., 'failed_login', 'suspicious_activity', 'data_access'
    severity = Column(String(20), nullable=False)  # 'low', 'medium', 'high', 'critical'
    user_id = Column(Integer, nullable=True)
    ip_address = Column(String(45), nullable=True)
    details = Column(Text, nullable=False)  # JSON string with event details
    resolved = Column(Boolean, default=False, nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_security_event_type', 'event_type'),
        Index('idx_security_severity', 'severity'),
        Index('idx_security_resolved', 'resolved'),
        Index('idx_security_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<SecurityEvent(type='{self.event_type}', severity='{self.severity}', resolved={self.resolved})>"


# Utility functions for database operations
def create_audit_log(
    db_session,
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
    """Create an audit log entry."""
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
    
    db_session.add(audit_log)
    db_session.commit()
    return audit_log


def create_security_event(
    db_session,
    event_type: str,
    severity: str,
    details: str,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None
) -> SecurityEvent:
    """Create a security event entry."""
    security_event = SecurityEvent(
        event_type=event_type,
        severity=severity,
        details=details,
        user_id=user_id,
        ip_address=ip_address
    )
    
    db_session.add(security_event)
    db_session.commit()
    return security_event
