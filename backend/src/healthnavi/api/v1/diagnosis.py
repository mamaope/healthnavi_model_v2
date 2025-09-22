"""
Diagnosis router for HealthNavi AI CDSS.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from healthnavi.core.database import get_db
from healthnavi.core.response_utils import create_success_response, create_error_response, ResponseTimer
from healthnavi.models.user import User
from healthnavi.schemas import DiagnosisInput, DiagnosisResponse, StandardResponse, SuccessResponse
from healthnavi.services.conversational_service import generate_response
from healthnavi.api.v1.auth import require_user_role

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
            test_response, _ = await generate_response(
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
async def diagnose(data: DiagnosisInput, current_user: User = Depends(require_user_role)):
    """
    Generate AI-powered diagnosis based on patient data.
    Requires authentication - only logged-in users can access this endpoint.
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

            logger.info(f"Diagnosis request from user: {current_user.username} (role: {current_user.role})")
            logger.info(f"Patient data length: {len(data.patient_data)} characters")

            # Use the real AI service to generate response
            try:
                response, diagnosis_complete = await generate_response(
                    query=data.patient_data,
                    chat_history=data.chat_history or "",
                    patient_data=data.patient_data
                )
                
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

            # Build updated chat history
            updated_chat_history = (
                f"{data.chat_history}\nDoctor: {data.patient_data}\nAI Assistant: {response}"
                if data.chat_history else
                f"Doctor: {data.patient_data}\nAI Assistant: {response}"
            )

            logger.info(f"AI diagnosis completed successfully. Response length: {len(response)} characters")
            
            diagnosis_data = DiagnosisResponse(
                model_response=response,
                diagnosis_complete=diagnosis_complete,
                updated_chat_history=updated_chat_history
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
