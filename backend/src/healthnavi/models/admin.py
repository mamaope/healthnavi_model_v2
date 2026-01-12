"""
Admin-related models for HealthNavi AI CDSS.
Includes safety events, surveys, audit logs, and alerts.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, Column, Integer, String, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from healthnavi.models.base import Base


class SafetyEventSeverity(str, enum.Enum):
    """Severity levels for safety events."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SafetyEventStatus(str, enum.Enum):
    """Status of safety events."""
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class SurveyType(str, enum.Enum):
    """Types of surveys."""
    BASELINE = "baseline"
    MID = "mid"
    FINAL = "final"
    PMF = "pmf"  # Product-Market Fit survey


class SafetyEvent(Base):
    """
    Represents a safety event or flag in the system.
    Tracks potential safety issues with AI responses.
    """
    __tablename__ = "safety_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Nullable for system-generated events
    message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=True, index=True)
    session_id = Column(Integer, ForeignKey("diagnosis_sessions.id"), nullable=True, index=True)
    
    severity = Column(SQLEnum(SafetyEventSeverity), nullable=False, default=SafetyEventSeverity.MEDIUM)
    status = Column(SQLEnum(SafetyEventStatus), nullable=False, default=SafetyEventStatus.OPEN)
    
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String(50), nullable=False)  # e.g., "missing_citation", "red_flag_not_flagged", "inappropriate_response"
    
    # Flags and metadata
    is_critical = Column(Boolean, nullable=False, default=False)
    has_guideline_citation = Column(Boolean, nullable=True)  # Whether the response had citations
    was_red_flag_queried = Column(Boolean, nullable=True)  # Whether query was a red flag
    was_red_flag_correctly_flagged = Column(Boolean, nullable=True)  # Whether red flag was correctly identified
    
    # Resolution tracking
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    resolved_at = Column(String, nullable=True)
    
    created_at = Column(String, nullable=True, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, nullable=True, default=lambda: datetime.utcnow().isoformat(), index=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    message = relationship("ChatMessage", foreign_keys=[message_id])
    session = relationship("DiagnosisSession", foreign_keys=[session_id])
    resolver = relationship("User", foreign_keys=[resolved_by])

    def __repr__(self):
        return f"<SafetyEvent(id={self.id}, severity='{self.severity}', status='{self.status}', type='{self.event_type}')>"


class Survey(Base):
    """
    Represents survey responses from users.
    Used for PMF analysis, baseline/mid/final surveys.
    """
    __tablename__ = "surveys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    survey_type = Column(SQLEnum(SurveyType), nullable=False, index=True)
    
    # PMF-specific fields
    pmf_score = Column(Integer, nullable=True)  # 0-10 scale
    very_disappointed = Column(Boolean, nullable=True)  # PMF test: "Very disappointed if product disappeared"
    willingness_to_pay = Column(Integer, nullable=True)  # Amount in local currency
    replacement_behavior = Column(String(100), nullable=True)  # e.g., "Google", "WhatsApp", "Consultation", "None"
    
    # Clinical value fields
    time_saved_minutes = Column(Integer, nullable=True)  # Estimated time saved
    usefulness_score = Column(Integer, nullable=True)  # 1-5 scale
    query_relevance = Column(Boolean, nullable=True)  # Whether query was relevant
    
    # Additional survey data (stored as JSON string for flexibility)
    survey_data = Column(Text, nullable=True)  # JSON string for additional questions
    
    created_at = Column(String, nullable=True, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, nullable=True, default=lambda: datetime.utcnow().isoformat())
    
    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<Survey(id={self.id}, user_id={self.user_id}, type='{self.survey_type}', pmf_score={self.pmf_score})>"


class AuditLog(Base):
    """
    Immutable audit log for all admin actions and system events.
    Ensures compliance and traceability.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Nullable for system events
    action = Column(String(100), nullable=False, index=True)  # e.g., "user_created", "session_deleted", "admin_access"
    resource_type = Column(String(50), nullable=True, index=True)  # e.g., "user", "session", "message"
    resource_id = Column(Integer, nullable=True, index=True)
    
    # Event details
    description = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(String(500), nullable=True)
    
    # Metadata (stored as JSON string) - renamed to event_metadata to avoid SQLAlchemy conflict
    event_metadata = Column(Text, nullable=True)  # JSON string for additional context
    
    # Immutable timestamp
    created_at = Column(String, nullable=False, default=lambda: datetime.utcnow().isoformat(), index=True)
    
    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, user_id={self.user_id}, action='{self.action}', created_at='{self.created_at}')>"


class Alert(Base):
    """
    Represents alerts triggered by the system.
    Alerts are sent to Clinical Leads for critical events.
    """
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String(50), nullable=False, index=True)  # e.g., "critical_safety_event", "high_flag_rate", "missing_citations"
    severity = Column(SQLEnum(SafetyEventSeverity), nullable=False, default=SafetyEventSeverity.HIGH)
    
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    
    # Related resources
    safety_event_id = Column(Integer, ForeignKey("safety_events.id"), nullable=True)
    related_data = Column(Text, nullable=True)  # JSON string for additional context
    
    # Alert status
    is_read = Column(Boolean, nullable=False, default=False)
    is_resolved = Column(Boolean, nullable=False, default=False)
    read_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(String, nullable=True)
    
    created_at = Column(String, nullable=False, default=lambda: datetime.utcnow().isoformat(), index=True)
    updated_at = Column(String, nullable=True, default=lambda: datetime.utcnow().isoformat())
    
    # Relationships
    safety_event = relationship("SafetyEvent", foreign_keys=[safety_event_id])
    reader = relationship("User", foreign_keys=[read_by])
    resolver = relationship("User", foreign_keys=[resolved_by])

    def __repr__(self):
        return f"<Alert(id={self.id}, type='{self.alert_type}', severity='{self.severity}', is_read={self.is_read})>"
