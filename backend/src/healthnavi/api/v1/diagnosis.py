"""
Diagnosis router for HealthNavi AI CDSS.
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from healthnavi.core.database import get_db
from healthnavi.core.response_utils import create_success_response, create_error_response, ResponseTimer
from healthnavi.models.user import User
from healthnavi.schemas import DiagnosisInput, DiagnosisResponse, StandardResponse, SuccessResponse, ChatMessageCreate
from healthnavi.services.conversational_service import generate_response
from healthnavi.services.diagnosis_session_service import DiagnosisSessionService
from healthnavi.api.v1.auth import get_current_user, require_user_role, require_admin_role, get_current_user_safe_v2
logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=StandardResponse)
async def diagnosis_health():
    """
    Health check endpoint for the diagnosis service.
    Checks if the AI service is available and responding.
    """
    with ResponseTimer() as timer:
        try:
            # Test AI service with a simple query
            test_response, _, _ = await generate_response(
                query="test",
                chat_history="",
                patient_data="test patient data"
            )
            
            if test_response and len(test_response.strip()) > 0:
                health_data = {
                    "status": "healthy",
                    "ai_service": "available",
                    "message": "Diagnosis service is operational"
                }
                
                return create_success_response(
                    data=health_data,
                    status_code=200,
                    message="Diagnosis service is healthy",
                    execution_time=timer.get_execution_time()
                )
            else:
                return create_error_response(
                    message="AI service returned empty response",
                    status_code=503,
                    execution_time=timer.get_execution_time()
                )
                
        except Exception as e:
            logger.error(f"Diagnosis health check failed: {str(e)}")
            # Sanitize error message for security
            error_message = "AI service temporarily unavailable"
            if "database" in str(e).lower() or "connection" in str(e).lower():
                error_message = "Service temporarily unavailable"
            
            return create_error_response(
                message=error_message,
                status_code=503,
                execution_time=timer.get_execution_time()
            )


@router.post("/diagnose", response_model=StandardResponse)
async def diagnose(data: DiagnosisInput, current_user: User = Depends(get_current_user_safe_v2), db: Session = Depends(get_db)):
    """
    Generate AI-powered diagnosis based on patient data.
    Now allows unauthenticated access for demo purposes.
    """
    with ResponseTimer() as timer:
        try:
            # Validate input data
            if not data.patient_data or len(data.patient_data.strip()) < 10:
                return create_error_response(
                    message="Patient data must be at least 10 characters long",
                    status_code=400,
                    execution_time=timer.get_execution_time()
                )

            # Handle both authenticated and unauthenticated users
            user_info = f"{current_user.username} (role: {current_user.role})" if current_user else "unauthenticated user"
            logger.info(f"Diagnosis request from: {user_info}")
            logger.info(f"Patient data length: {len(data.patient_data)} characters")

            # Get chat history from session if session_id is provided
            chat_history = data.chat_history or ""
            session_id = data.session_id
            message_id = None
            
            # Initialize session service
            session_service = DiagnosisSessionService(db)
            
            if session_id:
                try:
                    chat_history = session_service.get_chat_history(session_id, current_user)
                except Exception as e:
                    logger.warning(f"Could not get chat history from session {session_id}: {e}")
                    # Continue with provided chat_history
            else:
                # Auto-create a new session if none provided and user is authenticated
                if current_user:  # Only create session for authenticated users
                    try:
                        from healthnavi.schemas import ChatSessionCreate
                        new_session_data = ChatSessionCreate(
                            session_name=f"Diagnosis Session - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                            patient_summary=data.patient_data[:200] + "..." if len(data.patient_data) > 200 else data.patient_data
                        )
                        new_session = session_service.create_session(current_user, new_session_data)
                        session_id = new_session.id
                        logger.info(f"Auto-created new diagnosis session {session_id} for user {current_user.id}")
                    except Exception as e:
                        logger.warning(f"Could not auto-create session: {e}")
                        # Continue without session
                else:
                    # For unauthenticated users, use the provided session_id or None
                    logger.info("Skipping session creation for unauthenticated user")

            # Use the real AI service to generate response
            try:
                response, diagnosis_complete, prompt_type = await generate_response(
                    query=data.patient_data,
                    chat_history=chat_history,
                    patient_data=data.patient_data
                )
                logger.info(f"🎯 Prompt type used: {prompt_type}")
                # Validate AI response
                if not response or len(response.strip()) < 10:
                    return create_error_response(
                        message="AI service returned insufficient response. Please try again.",
                        status_code=503,
                        execution_time=timer.get_execution_time()
                    )
                    
            except Exception as ai_error:
                logger.error(f"AI service error: {str(ai_error)}")
                return create_error_response(
                    message=f"AI service is currently unavailable. Error: {str(ai_error)}",
                    status_code=503,
                    execution_time=timer.get_execution_time()
                )

            # Store messages in session only for authenticated users
            if session_id and current_user:  # Only store messages for authenticated users
                try:
                    # Add user message
                    user_message = ChatMessageCreate(
                        content=data.patient_data,
                        message_type="user",
                        patient_data=data.patient_data,
                        diagnosis_complete=False
                    )
                    session_service.add_message(session_id, current_user, user_message)
                    
                    # Add AI response message
                    ai_message = ChatMessageCreate(
                        content=response,
                        message_type="assistant",
                        patient_data=data.patient_data,
                        diagnosis_complete=diagnosis_complete
                    )
                    ai_msg_response = session_service.add_message(session_id, current_user, ai_message)
                    message_id = ai_msg_response.id if ai_msg_response else None
                    
                    logger.info(f"Stored messages in session {session_id}, message_id: {message_id}")
                    
                except Exception as e:
                    logger.warning(f"Could not store messages in session {session_id}: {e}")
                    # Continue without storing
            else:
                logger.info("Skipping message storage for unauthenticated user")

            # Build updated chat history
            updated_chat_history = (
                f"{chat_history}\nDoctor: {data.patient_data}\nAI Assistant: {response}"
                if chat_history else
                f"Doctor: {data.patient_data}\nAI Assistant: {response}"
            )

            logger.info(f"AI diagnosis completed successfully. Response length: {len(response)} characters")
            
            diagnosis_data = DiagnosisResponse(
                model_response=response,
                diagnosis_complete=diagnosis_complete,
                updated_chat_history=updated_chat_history,
                session_id=session_id,
                message_id=message_id,
                prompt_type=prompt_type
            )
            
            return create_success_response(
                data=diagnosis_data,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
            
        except Exception as e:
            logger.error(f"Unexpected error in diagnose endpoint: {str(e)}")
            # Sanitize error message for security
            error_message = "Diagnosis generation failed"
            if "database" in str(e).lower() or "connection" in str(e).lower():
                error_message = "Service temporarily unavailable"
            elif "ai" in str(e).lower() or "model" in str(e).lower():
                error_message = "AI service temporarily unavailable"
            
            return create_error_response(
                message=error_message,
                status_code=500,
                execution_time=timer.get_execution_time()
            )
