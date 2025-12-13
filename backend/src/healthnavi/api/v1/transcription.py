"""
Transcription API router for voice-to-text conversion.
"""

import logging
from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Depends
from pydantic import BaseModel
from typing import Optional
from healthnavi.core.response_utils import create_success_response, create_error_response, ResponseTimer
from healthnavi.schemas import StandardResponse
from healthnavi.services.transcription_service import transcribe_audio
from healthnavi.api.v1.auth import get_current_user_safe_v2
from healthnavi.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


class TranscriptionResponse(BaseModel):
    """Response model for transcription."""
    text: str
    language: str
    duration: Optional[float] = None


@router.post("/transcribe", response_model=StandardResponse)
async def transcribe_audio_endpoint(
    current_user: User = Depends(get_current_user_safe_v2),
    audio: UploadFile = File(..., description="Audio file to transcribe (wav, mp3, m4a, etc.)"),
    language: Optional[str] = Form("en", description="Language code. Defaults to 'en' (English).")
):
    """
    Transcribe audio file to text using OpenAI Whisper.
    
    Supports multiple audio formats: wav, mp3, m4a, ogg, webm, flac, etc.
    The endpoint uses the Whisper model to convert speech to text.
    
    Args:
        audio: Audio file upload
        language: Optional language code for transcription (defaults to English)
        current_user: Current authenticated user (optional for demo)
        
    Returns:
        Transcribed text and detected language
    """
    with ResponseTimer() as timer:
        try:
            # Log request info
            user_info = f"{current_user.username}" if current_user else "unauthenticated user"
            logger.info(f"Transcription request from: {user_info}")
            logger.info(f"Audio file: {audio.filename}, content_type: {audio.content_type}")
            
            # Validate file type
            allowed_types = [
                "audio/wav", "audio/wave", "audio/x-wav",
                "audio/mpeg", "audio/mp3",
                "audio/mp4", "audio/x-m4a",
                "audio/ogg", "audio/webm",
                "audio/flac", "audio/x-flac"
            ]
            
            if audio.content_type and audio.content_type not in allowed_types:
                logger.warning(f"Unsupported audio type: {audio.content_type}")
            
            # Read audio file
            audio_bytes = await audio.read()
            
            if len(audio_bytes) == 0:
                return create_error_response(
                    message="Empty audio file received",
                    status_code=400,
                    execution_time=timer.get_execution_time()
                )
            
            max_size = 25 * 1024 * 1024  # 25MB
            if len(audio_bytes) > max_size:
                return create_error_response(
                    message=f"Audio file too large. Maximum size is {max_size / (1024*1024):.1f}MB",
                    status_code=413,
                    execution_time=timer.get_execution_time()
                )
            
            logger.info(f"Audio file size: {len(audio_bytes) / 1024:.2f} KB")
            
            # Transcribe audio
            result = await transcribe_audio(audio_bytes, language=language)
            
            # Prepare response
            transcription_data = TranscriptionResponse(
                text=result["text"],
                language=result["language"]
            )
            
            logger.info(f"Transcription successful. Text length: {len(result['text'])} chars")
            
            return create_success_response(
                data=transcription_data.model_dump(),
                message="Audio transcribed successfully",
                status_code=200,
                execution_time=timer.get_execution_time()
            )
            
        except ValueError as e:
            logger.error(f"Validation error in transcription: {str(e)}")
            return create_error_response(
                message=str(e),
                status_code=400,
                execution_time=timer.get_execution_time()
            )
            
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            return create_error_response(
                message="Failed to transcribe audio. Please try again.",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/health", response_model=StandardResponse)
async def transcription_health():
    """
    Health check endpoint for transcription service.
    """
    with ResponseTimer() as timer:
        try:
            from healthnavi.services.transcription_service import get_whisper_model
            
            # Try to load the model
            model = get_whisper_model()
            
            if model is not None:
                return create_success_response(
                    data={"status": "healthy", "service": "transcription"},
                    message="Transcription service is operational",
                    status_code=200,
                    execution_time=timer.get_execution_time()
                )
            else:
                return create_error_response(
                    message="Whisper model not loaded",
                    status_code=503,
                    execution_time=timer.get_execution_time()
                )
                
        except Exception as e:
            logger.error(f"Transcription health check failed: {str(e)}")
            return create_error_response(
                message="Transcription service unavailable",
                status_code=503,
                execution_time=timer.get_execution_time()
            )
