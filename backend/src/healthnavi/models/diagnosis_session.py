"""
Diagnosis Session and Chat Message models for HealthNavi AI CDSS.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Boolean, Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from healthnavi.models.base import Base


class DiagnosisSession(Base):
    """
    Represents a diagnosis session between a user and the AI system.
    Each session can have multiple chat messages.
    """
    __tablename__ = "diagnosis_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_name = Column(String(255), nullable=True)
    patient_summary = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(String, nullable=True, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, nullable=True, default=lambda: datetime.utcnow().isoformat())

    # Relationships
    user = relationship("User", back_populates="diagnosis_sessions")
    chat_messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<DiagnosisSession(id={self.id}, user_id={self.user_id}, name='{self.session_name}')>"


class ChatMessage(Base):
    """
    Represents a message in a diagnosis chat session.
    Can be from the user (doctor) or the AI assistant.
    """
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("diagnosis_sessions.id"), nullable=False, index=True)
    message_type = Column(String(20), nullable=False)  # 'user', 'assistant', or 'system'
    content = Column(Text, nullable=False)
    patient_data = Column(Text, nullable=True)
    diagnosis_complete = Column(Boolean, nullable=False, default=False)
    created_at = Column(String, nullable=True, default=lambda: datetime.utcnow().isoformat())

    # Relationships
    session = relationship("DiagnosisSession", back_populates="chat_messages")
    feedback = relationship("MessageFeedback", back_populates="message", cascade="all, delete-orphan", uselist=False)

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, session_id={self.session_id}, type='{self.message_type}')>"


class MessageFeedback(Base):
    """
    Represents user feedback on AI assistant messages.
    Stores whether a message was helpful or not helpful.
    """
    __tablename__ = "message_feedback"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    feedback_type = Column(String(20), nullable=False)  # 'helpful' or 'not_helpful'
    created_at = Column(String, nullable=True, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, nullable=True, default=lambda: datetime.utcnow().isoformat())

    # Relationships
    message = relationship("ChatMessage", back_populates="feedback")
    user = relationship("User")

    def __repr__(self):
        return f"<MessageFeedback(id={self.id}, message_id={self.message_id}, feedback_type='{self.feedback_type}')>"