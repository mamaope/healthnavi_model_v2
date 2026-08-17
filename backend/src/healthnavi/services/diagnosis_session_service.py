"""
Diagnosis Session Service for Empirico.

This module provides services for managing diagnosis sessions and chat messages.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from healthnavi.models.user import User
from healthnavi.models.diagnosis_session import DiagnosisSession, ChatMessage
from healthnavi.schemas import (
    ChatSessionCreate, ChatSessionUpdate, ChatSessionResponse, 
    ChatMessageCreate, ChatMessageResponse, ChatSessionWithMessages,
    ChatSessionListResponse
)

logger = logging.getLogger(__name__)


class DiagnosisSessionService:
    """Service for managing diagnosis sessions and chat messages."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_session(
        self, user: User, session_data: ChatSessionCreate, device_type: Optional[str] = None
    ) -> ChatSessionResponse:
        """Create a new diagnosis session. Optionally log device_type for admin statistics."""
        try:
            # Create new session
            new_session = DiagnosisSession(
                user_id=user.id,
                session_name=session_data.session_name,
                patient_summary=session_data.patient_summary,
                is_active=True,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )
            
            self.db.add(new_session)
            self.db.commit()
            self.db.refresh(new_session)
            
            if device_type:
                try:
                    from healthnavi.services.admin_service import AdminService
                    AdminService(self.db).log_device_activity(user.id, device_type, "session_create")
                except Exception as e:
                    logger.warning(f"Could not log device activity: {e}", exc_info=True)
            
            logger.info(f"Created new diagnosis session {new_session.id} for user {user.id}")
            
            return ChatSessionResponse(
                id=new_session.id,
                user_id=new_session.user_id,
                session_name=new_session.session_name,
                patient_summary=new_session.patient_summary,
                is_active=new_session.is_active,
                created_at=new_session.created_at,
                updated_at=new_session.updated_at,
                message_count=0
            )
            
        except Exception as e:
            logger.error(f"Error creating diagnosis session: {e}")
            self.db.rollback()
            raise
    
    def get_session(self, session_id: int, user: User) -> Optional[ChatSessionResponse]:
        """Get a diagnosis session by ID."""
        try:
            session = self.db.query(DiagnosisSession).filter(
                DiagnosisSession.id == session_id,
                DiagnosisSession.user_id == user.id
            ).first()
            
            if not session:
                return None
            
            # Get message count
            message_count = self.db.query(func.count(ChatMessage.id)).filter(
                ChatMessage.session_id == session.id
            ).scalar()
            
            return ChatSessionResponse(
                id=session.id,
                user_id=session.user_id,
                session_name=session.session_name,
                patient_summary=session.patient_summary,
                is_active=session.is_active,
                created_at=session.created_at,
                updated_at=session.updated_at,
                message_count=message_count or 0
            )
            
        except Exception as e:
            logger.error(f"Error getting diagnosis session {session_id}: {e}")
            raise
    
    def get_session_with_messages(self, session_id: int, user: User) -> Optional[ChatSessionWithMessages]:
        """Get a diagnosis session with all its messages."""
        try:
            session = self.db.query(DiagnosisSession).filter(
                DiagnosisSession.id == session_id,
                DiagnosisSession.user_id == user.id
            ).first()
            
            if not session:
                return None
            
            # Get messages ordered by creation time
            messages = self.db.query(ChatMessage).filter(
                ChatMessage.session_id == session.id
            ).order_by(ChatMessage.id.asc()).all()
            
            # Convert messages to response format
            message_responses = [
                ChatMessageResponse(
                    id=msg.id,
                    session_id=msg.session_id,
                    message_type=msg.message_type,
                    content=msg.content,
                    patient_data=msg.patient_data,
                    diagnosis_complete=msg.diagnosis_complete,
                    created_at=msg.created_at
                ) for msg in messages
            ]
            
            return ChatSessionWithMessages(
                id=session.id,
                user_id=session.user_id,
                session_name=session.session_name,
                patient_summary=session.patient_summary,
                is_active=session.is_active,
                created_at=session.created_at,
                updated_at=session.updated_at,
                message_count=len(messages),
                messages=message_responses
            )
            
        except Exception as e:
            logger.error(f"Error getting diagnosis session with messages {session_id}: {e}")
            raise
    
    def list_sessions(self, user: User, page: int = 1, per_page: int = 20) -> ChatSessionListResponse:
        """List diagnosis sessions for a user. Returns all active sessions (including empty ones created manually)."""
        try:
            # Calculate offset
            offset = (page - 1) * per_page
            
            # Get all active sessions for the user (including empty ones created manually)
            # This allows manually created sessions to appear in the session history immediately
            total = self.db.query(func.count(DiagnosisSession.id)).filter(
                DiagnosisSession.user_id == user.id,
                DiagnosisSession.is_active == True
            ).scalar() or 0
            
            # Get all active sessions ordered by most recently updated
            sessions = self.db.query(DiagnosisSession).filter(
                DiagnosisSession.user_id == user.id,
                DiagnosisSession.is_active == True
            ).order_by(
                desc(DiagnosisSession.updated_at)
            ).offset(offset).limit(per_page).all()
            
            # Convert to response format
            session_responses = [
                ChatSessionResponse(
                    id=session.id,
                    user_id=session.user_id,
                    session_name=session.session_name,
                    patient_summary=session.patient_summary,
                    is_active=session.is_active,
                    created_at=session.created_at,
                    updated_at=session.updated_at,
                    message_count=0  # Set to 0 to avoid expensive join - frontend doesn't display this anyway
                ) for session in sessions
            ]
            
            return ChatSessionListResponse(
                sessions=session_responses,
                total=total or 0,
                page=page,
                per_page=per_page
            )
            
        except Exception as e:
            logger.error(f"Error listing diagnosis sessions for user {user.id}: {e}")
            raise
    
    def update_session(self, session_id: int, user: User, update_data: ChatSessionUpdate) -> Optional[ChatSessionResponse]:
        """Update a diagnosis session."""
        try:
            session = self.db.query(DiagnosisSession).filter(
                DiagnosisSession.id == session_id,
                DiagnosisSession.user_id == user.id
            ).first()
            
            if not session:
                return None
            
            # Update fields
            if update_data.session_name is not None:
                session.session_name = update_data.session_name
            if update_data.patient_summary is not None:
                session.patient_summary = update_data.patient_summary
            if update_data.is_active is not None:
                session.is_active = update_data.is_active
            
            session.updated_at = datetime.utcnow().isoformat()
            
            self.db.commit()
            self.db.refresh(session)
            
            # Get message count
            message_count = self.db.query(func.count(ChatMessage.id)).filter(
                ChatMessage.session_id == session.id
            ).scalar()
            
            logger.info(f"Updated diagnosis session {session_id} for user {user.id}")
            
            return ChatSessionResponse(
                id=session.id,
                user_id=session.user_id,
                session_name=session.session_name,
                patient_summary=session.patient_summary,
                is_active=session.is_active,
                created_at=session.created_at,
                updated_at=session.updated_at,
                message_count=message_count or 0
            )
            
        except Exception as e:
            logger.error(f"Error updating diagnosis session {session_id}: {e}")
            self.db.rollback()
            raise
    
    def delete_session(self, session_id: int, user: User) -> bool:
        """Delete a diagnosis session."""
        try:
            session = self.db.query(DiagnosisSession).filter(
                DiagnosisSession.id == session_id,
                DiagnosisSession.user_id == user.id
            ).first()
            
            if not session:
                return False
            
            self.db.delete(session)
            self.db.commit()
            
            logger.info(f"Deleted diagnosis session {session_id} for user {user.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting diagnosis session {session_id}: {e}")
            self.db.rollback()
            raise
    
    def add_message(self, session_id: int, user: User, message_data: ChatMessageCreate) -> Optional[ChatMessageResponse]:
        """Add a message to a diagnosis session."""
        try:
            # Verify session belongs to user
            session = self.db.query(DiagnosisSession).filter(
                DiagnosisSession.id == session_id,
                DiagnosisSession.user_id == user.id
            ).first()
            
            if not session:
                return None
            
            # If this is the first user message and session has default/generic name, update it
            if message_data.message_type == 'user':
                message_count = self.db.query(func.count(ChatMessage.id)).filter(
                    ChatMessage.session_id == session.id
                ).scalar() or 0
                
                generic_prefixes = ['Diagnosis Session', 'Empirico Session', 'Streaming Session', 'Session', 'New Session']
                is_generic_name = session.session_name and any(
                    session.session_name.startswith(prefix) for prefix in generic_prefixes
                )
                
                if message_count == 0 and is_generic_name:
                    # Extract first 50 chars from user message as session name 
                    content = message_data.content or ''
                    if len(content) > 50:
                        session.session_name = content[:50].strip() + '...'
                    elif content.strip():
                        session.session_name = content.strip()
                    logger.info(f"Updated session {session_id} name to: {session.session_name}")
            
            # Create new message
            new_message = ChatMessage(
                session_id=session_id,
                message_type=message_data.message_type,
                content=message_data.content,
                patient_data=message_data.patient_data,
                diagnosis_complete=message_data.diagnosis_complete,
                created_at=datetime.utcnow().isoformat()
            )
            
            self.db.add(new_message)
            
            # Update session timestamp
            session.updated_at = datetime.utcnow().isoformat()
            
            self.db.commit()
            self.db.refresh(new_message)
            
            logger.info(f"Added message {new_message.id} to session {session_id}")
            
            return ChatMessageResponse(
                id=new_message.id,
                session_id=new_message.session_id,
                message_type=new_message.message_type,
                content=new_message.content,
                patient_data=new_message.patient_data,
                diagnosis_complete=new_message.diagnosis_complete,
                created_at=new_message.created_at
            )
            
        except Exception as e:
            logger.error(f"Error adding message to session {session_id}: {e}")
            self.db.rollback()
            raise
    
    def get_chat_history(self, session_id: int, user: User) -> str:
        """Get formatted chat history for a session."""
        try:
            # Verify session belongs to user
            session = self.db.query(DiagnosisSession).filter(
                DiagnosisSession.id == session_id,
                DiagnosisSession.user_id == user.id
            ).first()
            
            if not session:
                return ""
            
            # Get messages ordered by creation time
            messages = self.db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.id.asc()).all()
            
            # Format chat history
            chat_history_parts = []
            for msg in messages:
                if msg.message_type == "user":
                    chat_history_parts.append(f"User: {msg.content}")
                elif msg.message_type == "assistant":
                    chat_history_parts.append(f"Empirico: {msg.content}")
                # Skip system messages in chat history
            
            return "\n".join(chat_history_parts)
            
        except Exception as e:
            logger.error(f"Error getting chat history for session {session_id}: {e}")
            return ""
            
