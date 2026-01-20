"""
Diagnosis router for HealthNavi AI CDSS.
"""

import logging
import time
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from healthnavi.core.database import get_db
from healthnavi.core.response_utils import create_success_response, create_error_response, ResponseTimer
from healthnavi.models.user import User
from healthnavi.schemas import DiagnosisInput, DiagnosisResponse, StandardResponse, SuccessResponse, ChatMessageCreate, MessageFeedbackRequest, MessageFeedbackResponse
from healthnavi.services.conversational_service import generate_response, generate_response_stream
from healthnavi.services.diagnosis_session_service import DiagnosisSessionService
from healthnavi.api.v1.auth import get_current_user, require_user_role, require_admin_role, get_current_user_safe_v2
from healthnavi.core.device_utils import get_device_type
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
            # Don't auto-create sessions - they will be created when the first user message is saved
            # This prevents empty sessions from being saved

            # Use the real AI service to generate response
            # Explicitly default to False if not provided or None
            deep_search_enabled = data.deep_search if data.deep_search is not None else False
            logger.info(f"Search mode: {'DEEP SEARCH' if deep_search_enabled else 'QUICK SEARCH'}")
            
            try:
                # Get user's medical professional type for role-based prompts
                user_role = current_user.medical_professional_type if current_user else None
                response, diagnosis_complete, prompt_type, followup_questions = await generate_response(
                    query=data.patient_data,
                    chat_history=chat_history,
                    patient_data=data.patient_data,
                    deep_search=deep_search_enabled,
                    user_role_from_db=user_role
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
            # Create session only when saving the first user message (prevents empty sessions)
            if current_user:  # Only store messages for authenticated users
                try:
                    # Create session if it doesn't exist (only when saving first user message)
                    if not session_id:
                        from healthnavi.schemas import ChatSessionCreate
                        new_session_data = ChatSessionCreate(
                            session_name=f"Diagnosis Session - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                            patient_summary=data.patient_data[:200] + "..." if len(data.patient_data) > 200 else data.patient_data
                        )
                        new_session = session_service.create_session(
                            current_user, new_session_data, device_type=get_device_type(request)
                        )
                        session_id = new_session.id
                        logger.info(f"Created new diagnosis session {session_id} for user {current_user.id}")
                    
                    # Add user message (this creates the session if needed)
                    user_message = ChatMessageCreate(
                        content=data.patient_data,
                        message_type="user",
                        patient_data=data.patient_data,
                        diagnosis_complete=False
                    )
                    user_msg_response = session_service.add_message(session_id, current_user, user_message)
                    
                    # Only save AI message if user message was saved successfully
                    if user_msg_response:
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
                    else:
                        logger.warning(f"User message not saved, skipping AI message storage")
                        # Clean up empty session if it was just created
                        if session_id:
                            try:
                                session_service.delete_session(session_id, current_user)
                                logger.info(f"Cleaned up empty session {session_id}")
                            except Exception as cleanup_error:
                                logger.warning(f"Could not clean up empty session {session_id}: {cleanup_error}")
                    
                except Exception as e:
                    logger.warning(f"Could not store messages: {e}")
                    # Clean up session if it was just created and has no messages
                    if session_id and current_user:
                        try:
                            # Check if session has any messages
                            from healthnavi.models.diagnosis_session import ChatMessage
                            message_count = db.query(func.count(ChatMessage.id)).filter(
                                ChatMessage.session_id == session_id
                            ).scalar() or 0
                            if message_count == 0:
                                session_service.delete_session(session_id, current_user)
                                logger.info(f"Cleaned up empty session {session_id} after error")
                        except Exception as cleanup_error:
                            logger.warning(f"Could not clean up empty session after error: {cleanup_error}")
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


@router.post("/diagnose/stream")
async def diagnose_stream(
    data: DiagnosisInput,
    request: Request,
    current_user: User = Depends(get_current_user_safe_v2),
    db: Session = Depends(get_db),
):
    """
    Generate AI-powered diagnosis with streaming response.
    Returns a StreamingResponse that sends text chunks as they are generated.
    """
    request_start_time = time.time()
    
    # Extract user ID IMMEDIATELY before any other operations (current_user may become detached)
    user_id = current_user.id if current_user else None
    
    # Handle both authenticated and unauthenticated users
    user_info = f"{current_user.username} (role: {current_user.role})" if current_user else "unauthenticated user"
    logger.info(f"Streaming diagnosis request from: {user_info}")

    try:
        # Validate input data
        if not data.patient_data or len(data.patient_data.strip()) < 3:
            async def error_generator():
                yield "[STREAM_ERROR]: Patient data must be at least 3 characters long"
            return StreamingResponse(error_generator(), media_type="text/plain", status_code=400)

        # Get chat history from session if session_id is provided
        chat_history = data.chat_history or ""
        session_id = data.session_id
        
        # Initialize session service
        session_service = DiagnosisSessionService(db)
        
        # Convert session_id to int if it's a string (for authenticated users)
        session_id_int = None
        if session_id and current_user:
            try:
                if isinstance(session_id, str):
                    # Try to convert string to int
                    try:
                        session_id_int = int(session_id)
                    except ValueError:
                        # If it's not a numeric string, it might be a guest session ID
                        logger.warning(f"Session ID '{session_id}' is not numeric, treating as guest session")
                        session_id_int = None
                elif isinstance(session_id, int):
                    session_id_int = session_id
                else:
                    logger.warning(f"Unexpected session_id type: {type(session_id)}")
                    session_id_int = None
            except Exception as e:
                logger.error(f"Error converting session_id: {e}")
                session_id_int = None
        
        if session_id_int and current_user:
            try:
                chat_history = session_service.get_chat_history(session_id_int, current_user)
                logger.info(f"Retrieved chat history from session {session_id_int}: {len(chat_history)} chars")
            except Exception as e:
                logger.warning(f"Could not get chat history from session {session_id_int}: {e}")
        # Don't auto-create sessions - they will be created when the first user message is saved
        # This prevents empty sessions from being saved

        deep_search_enabled = data.deep_search if data.deep_search is not None else False
        logger.info(f"Search mode: {'DEEP SEARCH' if deep_search_enabled else 'QUICK SEARCH'} (streaming)")
        
        # Create session only when saving the first user message (prevents empty sessions)
        user_message_saved = False
        if current_user:
            try:
                # Save user message first - create session only if message save succeeds
                user_message = ChatMessageCreate(
                    content=data.patient_data,
                    message_type="user",
                    patient_data=data.patient_data,
                    diagnosis_complete=False
                )
                
                # If session exists, try to save message
                if session_id_int:
                    user_msg_response = session_service.add_message(session_id_int, current_user, user_message)
                    if user_msg_response:
                        user_message_saved = True
                        logger.info(f"Stored user message in session {session_id_int}")
                    else:
                        logger.warning(f"Failed to save user message in existing session {session_id_int}")
                        session_id_int = None  # Don't use this session
                else:
                    # No session exists - create one and save message
                    from healthnavi.schemas import ChatSessionCreate
                    new_session_data = ChatSessionCreate(
                        session_name=f"Streaming Session - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                        patient_summary=data.patient_data[:200] + "..." if len(data.patient_data) > 200 else data.patient_data
                    )
                    new_session = session_service.create_session(
                        current_user, new_session_data, device_type=get_device_type(request)
                    )
                    session_id_int = new_session.id
                    logger.info(f"Created new streaming session {session_id_int} for user {current_user.id}")
                    
                    # Now save the user message
                    user_msg_response = session_service.add_message(session_id_int, current_user, user_message)
                    if user_msg_response:
                        user_message_saved = True
                        logger.info(f"Stored user message in new session {session_id_int}")
                    else:
                        logger.warning(f"Failed to save user message in newly created session {session_id_int}")
                        # Clean up empty session
                        try:
                            session_service.delete_session(session_id_int, current_user)
                            logger.info(f"Cleaned up empty session {session_id_int}")
                            session_id_int = None
                        except Exception as cleanup_error:
                            logger.warning(f"Could not clean up empty session: {cleanup_error}")
            except Exception as e:
                logger.warning(f"Could not store user message: {e}", exc_info=True)
                # Clean up session if it was just created and has no messages
                if session_id_int and current_user:
                    try:
                        message_count = db.query(func.count(ChatMessage.id)).filter(
                            ChatMessage.session_id == session_id_int
                        ).scalar() or 0
                        if message_count == 0:
                            session_service.delete_session(session_id_int, current_user)
                            logger.info(f"Cleaned up empty session {session_id_int} after error")
                            session_id_int = None
                    except Exception as cleanup_error:
                        logger.warning(f"Could not clean up empty session after error: {cleanup_error}")

        user_role = None
        if current_user:
            try:
                # Access the attribute while the session is still active
                user_role = current_user.medical_professional_type
            except Exception as e:
                logger.warning(f"Could not get user role: {e}, defaulting to None")
                user_role = None
        
        # Container to store the AI message ID after it's saved
        ai_message_id_container = {"value": None}
        
        async def streaming_with_storage():
            full_response = ""
            ai_response_content = ""  # Track only the AI response content (without markers)
            stream_error = None
            ai_message_saved = False
            try:
                async for chunk in generate_response_stream(
                    query=data.patient_data,
                    chat_history=chat_history,
                    patient_data=data.patient_data,
                    deep_search=deep_search_enabled,
                    user_role_from_db=user_role
                ):
                    # Check for error markers from the generator
                    if chunk and chunk.startswith("[STREAM_ERROR]:"):
                        error_msg = chunk.replace("[STREAM_ERROR]:", "").strip()
                        logger.error(f"Stream generator reported error: {error_msg}")
                        stream_error = error_msg
                        yield chunk  # Still yield so frontend can handle it
                        break
                    
                    full_response += chunk
                    # Track AI response content separately (exclude followup markers)
                    if not chunk.startswith("[FOLLOWUP_QUESTIONS]:"):
                        ai_response_content += chunk
                    yield chunk
                
                # Save AI message only if user message was saved successfully and we have valid content
                if session_id_int and user_id and user_message_saved:
                    content_to_save = ai_response_content.strip()
                    # Save if we have any content and no stream error
                    if not stream_error and content_to_save:
                        try:
                            # Create a new database session for saving (the original db session may be closed)
                            # Use SessionLocal directly to create a new session
                            from healthnavi.core.database import SessionLocal
                            from healthnavi.models.user import User
                            save_db = SessionLocal()
                            try:
                                # Re-query the user in the new session to avoid detached instance error
                                user_in_new_session = save_db.query(User).filter(User.id == user_id).first()
                                if not user_in_new_session:
                                    logger.error(f"❌ User {user_id} not found in new session")
                                else:
                                    save_session_service = DiagnosisSessionService(save_db)
                                    ai_message = ChatMessageCreate(
                                        content=content_to_save,
                                        message_type="assistant",
                                        patient_data=data.patient_data,
                                        diagnosis_complete=True
                                    )
                                    saved_message = save_session_service.add_message(session_id_int, user_in_new_session, ai_message)
                                    if saved_message:
                                        ai_message_id_container["value"] = saved_message.id
                                        ai_message_saved = True
                                        logger.info(f"✅ Stored AI streaming response in session {session_id_int}: message_id={saved_message.id}, {len(content_to_save)} chars")
                                    else:
                                        logger.warning(f"⚠️ Failed to save AI message - add_message returned None")
                            except Exception as save_error:
                                save_db.rollback()
                                raise save_error
                            finally:
                                save_db.close()
                        except Exception as e:
                            logger.error(f"❌ Could not store AI response in session {session_id_int}: {e}", exc_info=True)
                    elif stream_error:
                        logger.error(f"Stream ended with error, not storing AI response: {stream_error}")
                    elif not content_to_save:
                        logger.warning(f"Stream ended with no content, not storing AI response")
                elif not user_message_saved:
                    logger.warning(f"Skipping AI message save - user message was not saved successfully")
                
                # Generate follow-up questions if we have valid content
                followup_already_sent = "[FOLLOWUP_QUESTIONS]:" in full_response
                if not stream_error and not followup_already_sent and ai_response_content and len(ai_response_content.strip()) > 10:
                    followup_questions = []
                    try:
                        from healthnavi.services.conversational_service import generate_followup_questions_sync
                        followup_questions = generate_followup_questions_sync(data.patient_data, ai_response_content)
                        logger.info(f"Generated {len(followup_questions)} follow-up questions")
                    except Exception as e:
                        logger.warning(f"Could not generate follow-up questions: {e}", exc_info=True)
                    
                    if followup_questions:
                        import json
                        followup_json = json.dumps(followup_questions)
                        yield f"\n\n[FOLLOWUP_QUESTIONS]:{followup_json}"
                        logger.info(f"✅ Sent {len(followup_questions)} follow-up questions to frontend")
                    else:
                        logger.warning("⚠️ Follow-up question generation returned empty list")
                elif followup_already_sent:
                    logger.info("ℹ️ Follow-up questions already sent in stream, skipping duplicate generation")
                elif stream_error:
                    logger.warning("⚠️ Skipping follow-up question generation due to stream error")
                elif not ai_response_content or len(ai_response_content.strip()) <= 10:
                    logger.debug(f"Skipping follow-up question generation - content too short ({len(ai_response_content.strip()) if ai_response_content else 0} chars)")
                
                # Send message_id at the end if available (before stream ends)
                if ai_message_id_container["value"]:
                    yield f"\n[MESSAGE_ID]:{ai_message_id_container['value']}\n"
                
                # Log final status
                if session_id_int and user_id:
                    if ai_message_saved:
                        logger.info(f"✅ Successfully saved AI message to session {session_id_int}, message_id={ai_message_id_container['value']}")
                    else:
                        logger.warning(f"⚠️ AI message was NOT saved to session {session_id_int} (stream_error={stream_error}, content_len={len(ai_response_content.strip())})")
                        
            except Exception as e:
                logger.error(f"Error during streaming generation: {e}", exc_info=True)
                error_msg = f"[STREAM_ERROR]: {str(e)}"
                yield error_msg
                # Don't store error responses

        return StreamingResponse(
            streaming_with_storage(),
            media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
                "Transfer-Encoding": "chunked",
                "Content-Type": "text/plain; charset=utf-8",
                "X-Session-Id": str(session_id) if session_id else ""  # Pass session ID for frontend
            }
        )

    except Exception as e:
        error_time = time.time() - request_start_time
        logger.error(f"Error after {error_time:.2f}s in streaming diagnose endpoint: {e}")
        
        async def error_generator():
            yield f"[STREAM_ERROR]: {str(e)}"
        return StreamingResponse(error_generator(), media_type="text/plain", status_code=500)


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

            logger.info(
                f"Feedback submission attempt: message_id={feedback_data.message_id}, "
                f"user_id={current_user.id}, type={feedback_data.feedback_type}, "
                f"rating={feedback_data.rating}, existing={existing_feedback is not None}"
            )

            if existing_feedback:
                # Update existing feedback
                existing_feedback.feedback_type = feedback_data.feedback_type
                existing_feedback.feedback_text = feedback_data.feedback_text
                existing_feedback.rating = feedback_data.rating
                existing_feedback.updated_at = datetime.utcnow().isoformat()
                db.commit()
                db.refresh(existing_feedback)

                logger.info(
                    f"Updated feedback {existing_feedback.id} for message {feedback_data.message_id} by user {current_user.id}. "
                    f"Type: {feedback_data.feedback_type}, Rating: {feedback_data.rating}, "
                    f"Updated At: {existing_feedback.updated_at}"
                )

                feedback_response = MessageFeedbackResponse(
                    id=existing_feedback.id,
                    message_id=existing_feedback.message_id,
                    user_id=existing_feedback.user_id,
                    feedback_type=existing_feedback.feedback_type,
                    feedback_text=existing_feedback.feedback_text,
                    rating=existing_feedback.rating,
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
                    feedback_text=feedback_data.feedback_text,
                    rating=feedback_data.rating,
                    created_at=datetime.utcnow().isoformat(),
                    updated_at=datetime.utcnow().isoformat()
                )

                db.add(new_feedback)
                db.commit()
                db.refresh(new_feedback)

                logger.info(
                    f"Created feedback {new_feedback.id} for message {feedback_data.message_id} by user {current_user.id}. "
                    f"Type: {feedback_data.feedback_type}, Rating: {feedback_data.rating}, "
                    f"Created At: {new_feedback.created_at}"
                )

                feedback_response = MessageFeedbackResponse(
                    id=new_feedback.id,
                    message_id=new_feedback.message_id,
                    user_id=new_feedback.user_id,
                    feedback_type=new_feedback.feedback_type,
                    feedback_text=new_feedback.feedback_text,
                    rating=new_feedback.rating,
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
