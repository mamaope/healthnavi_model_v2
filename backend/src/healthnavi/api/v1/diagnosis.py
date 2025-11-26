"""
Diagnosis router for HealthNavi AI CDSS.
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload
from healthnavi.core.database import get_db
from healthnavi.core.response_utils import create_success_response, create_error_response, ResponseTimer
from healthnavi.models.user import User
from healthnavi.schemas import DiagnosisInput, DiagnosisResponse, StandardResponse, SuccessResponse, ChatMessageCreate, MessageFeedbackRequest, MessageFeedbackResponse
from healthnavi.services.conversational_service import generate_response
from healthnavi.services.diagnosis_session_service import DiagnosisSessionService
from healthnavi.api.v1.auth import get_current_user, require_user_role, require_admin_role, get_current_user_safe_v2
from healthnavi.models.diagnosis_session import ChatMessage, MessageFeedback
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
            if not data.patient_data or len(data.patient_data.strip()) < 3:
                return create_error_response(
                    message="Patient data must be at least 3 characters long",
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
            # Explicitly default to False if not provided or None
            deep_search_enabled = data.deep_search if data.deep_search is not None else False
            logger.info(f"Search mode: {'DEEP SEARCH' if deep_search_enabled else 'QUICK SEARCH'}")
            
            try:
                response, diagnosis_complete, prompt_type, followup_questions = await generate_response(
                    query=data.patient_data,
                    chat_history=chat_history,
                    patient_data=data.patient_data,
                    deep_search=deep_search_enabled
                )
                logger.info(f"Prompt type used: {prompt_type}")
                # Ensure followup_questions is always a list
                if followup_questions is None:
                    followup_questions = []
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
            
            if followup_questions is None:
                followup_questions = []
            
            try:
                diagnosis_data = DiagnosisResponse(
                    model_response=response,
                    diagnosis_complete=diagnosis_complete,
                    updated_chat_history=updated_chat_history,
                    session_id=session_id,
                    message_id=message_id,
                    prompt_type=prompt_type,
                    followup_questions=followup_questions
                )
            except Exception as schema_error:
                logger.error(f"Error creating DiagnosisResponse schema: {schema_error}", exc_info=True)
                # Return with empty followup_questions as fallback
                diagnosis_data = DiagnosisResponse(
                    model_response=response,
                    diagnosis_complete=diagnosis_complete,
                    updated_chat_history=updated_chat_history,
                    session_id=session_id,
                    message_id=message_id,
                    prompt_type=prompt_type,
                    followup_questions=[]
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


@router.post("/feedback", response_model=StandardResponse)
async def submit_feedback(
    feedback_data: MessageFeedbackRequest,
    current_user: User = Depends(require_user_role),
    db: Session = Depends(get_db)
):
    """
    Submit feedback on an AI assistant message.
    Users can mark messages as helpful or not helpful.
    """
    with ResponseTimer() as timer:
        try:
            # Validate feedback type
            if feedback_data.feedback_type not in ['helpful', 'not_helpful']:
                return create_error_response(
                    message="Invalid feedback type. Must be 'helpful' or 'not_helpful'",
                    status_code=400,
                    execution_time=timer.get_execution_time()
                )

            # Verify message exists and belongs to the user
            message = db.query(ChatMessage).options(
                joinedload(ChatMessage.session)
            ).filter(
                ChatMessage.id == feedback_data.message_id,
                ChatMessage.message_type == 'assistant'  # Only allow feedback on AI messages
            ).first()

            if not message:
                return create_error_response(
                    message="Message not found or feedback not allowed on this message type",
                    status_code=404,
                    execution_time=timer.get_execution_time()
                )

            # Verify the message belongs to a session owned by the user
            if message.session.user_id != current_user.id:
                return create_error_response(
                    message="You can only provide feedback on your own messages",
                    status_code=403,
                    execution_time=timer.get_execution_time()
                )

            # Check if feedback already exists for this message
            existing_feedback = db.query(MessageFeedback).filter(
                MessageFeedback.message_id == feedback_data.message_id
            ).first()

            if existing_feedback:
                # Update existing feedback
                existing_feedback.feedback_type = feedback_data.feedback_type
                existing_feedback.updated_at = datetime.utcnow().isoformat()
                db.commit()
                db.refresh(existing_feedback)

                logger.info(f"Updated feedback {existing_feedback.id} for message {feedback_data.message_id} by user {current_user.id}")

                feedback_response = MessageFeedbackResponse(
                    id=existing_feedback.id,
                    message_id=existing_feedback.message_id,
                    user_id=existing_feedback.user_id,
                    feedback_type=existing_feedback.feedback_type,
                    created_at=existing_feedback.created_at,
                    updated_at=existing_feedback.updated_at
                )

                return create_success_response(
                    data=feedback_response,
                    status_code=200,
                    message="Feedback updated successfully",
                    execution_time=timer.get_execution_time()
                )
            else:
                # Create new feedback
                new_feedback = MessageFeedback(
                    message_id=feedback_data.message_id,
                    user_id=current_user.id,
                    feedback_type=feedback_data.feedback_type,
                    created_at=datetime.utcnow().isoformat(),
                    updated_at=datetime.utcnow().isoformat()
                )

                db.add(new_feedback)
                db.commit()
                db.refresh(new_feedback)

                logger.info(f"Created feedback {new_feedback.id} for message {feedback_data.message_id} by user {current_user.id}")

                feedback_response = MessageFeedbackResponse(
                    id=new_feedback.id,
                    message_id=new_feedback.message_id,
                    user_id=new_feedback.user_id,
                    feedback_type=new_feedback.feedback_type,
                    created_at=new_feedback.created_at,
                    updated_at=new_feedback.updated_at
                )

                return create_success_response(
                    data=feedback_response,
                    status_code=201,
                    message="Feedback submitted successfully",
                    execution_time=timer.get_execution_time()
                )

        except Exception as e:
            logger.error(f"Error submitting feedback: {str(e)}")
            db.rollback()
            error_message = "Failed to submit feedback"
            if "database" in str(e).lower() or "connection" in str(e).lower():
                error_message = "Service temporarily unavailable"

            return create_error_response(
                message=error_message,
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.delete("/feedback/{message_id}", response_model=StandardResponse)
async def remove_feedback(
    message_id: int,
    current_user: User = Depends(require_user_role),
    db: Session = Depends(get_db)
):
    """
    Remove feedback from an AI assistant message.
    """
    with ResponseTimer() as timer:
        try:
            # Find the feedback
            feedback = db.query(MessageFeedback).filter(
                MessageFeedback.message_id == message_id,
                MessageFeedback.user_id == current_user.id
            ).first()

            if not feedback:
                return create_error_response(
                    message="Feedback not found",
                    status_code=404,
                    execution_time=timer.get_execution_time()
                )

            db.delete(feedback)
            db.commit()

            logger.info(f"Removed feedback for message {message_id} by user {current_user.id}")

            return create_success_response(
                data={"message_id": message_id},
                status_code=200,
                message="Feedback removed successfully",
                execution_time=timer.get_execution_time()
            )

        except Exception as e:
            logger.error(f"Error removing feedback: {str(e)}")
            db.rollback()
            error_message = "Failed to remove feedback"
            if "database" in str(e).lower() or "connection" in str(e).lower():
                error_message = "Service temporarily unavailable"

            return create_error_response(
                message=error_message,
                status_code=500,
                execution_time=timer.get_execution_time()
            )
