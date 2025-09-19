"""
Simplified diagnosis router for HealthNavi AI CDSS.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()


class DiagnosisInput(BaseModel):
    patient_data: str
    chat_history: Optional[str] = ""
    session_id: Optional[str] = None


class DiagnosisResponse(BaseModel):
    response: str
    session_id: str
    timestamp: datetime
    confidence: float
    suggestions: list


@router.post("/diagnose", response_model=DiagnosisResponse)
async def diagnose_patient(diagnosis_data: DiagnosisInput, request: Request):
    """Generate diagnosis suggestions based on patient data."""
    logger.info(f"Diagnosis request for session: {diagnosis_data.session_id}")
    
    # Simple validation
    if len(diagnosis_data.patient_data) > 10000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patient data too long (max 10000 characters)"
        )
    
    # Mock response for now
    response_text = f"""
    Based on the patient data provided: "{diagnosis_data.patient_data[:100]}..."
    
    I recommend the following diagnostic considerations:
    
    1. **Primary Assessment**: Please conduct a thorough physical examination
    2. **Laboratory Tests**: Consider ordering relevant blood work and imaging
    3. **Differential Diagnosis**: Multiple conditions should be considered
    
    **Important**: This is a preliminary assessment. Please consult with appropriate medical specialists and conduct proper clinical evaluation.
    
    **Disclaimer**: This AI system is for educational and decision support purposes only. All clinical decisions must be made by qualified healthcare professionals.
    """
    
    return DiagnosisResponse(
        response=response_text.strip(),
        session_id=diagnosis_data.session_id or "mock_session_123",
        timestamp=datetime.now(),
        confidence=0.75,
        suggestions=[
            "Conduct physical examination",
            "Order laboratory tests",
            "Consider imaging studies",
            "Consult with specialists"
        ]
    )


@router.get("/health")
async def diagnosis_health():
    """Health check for diagnosis service."""
    return {
        "status": "healthy",
        "service": "diagnosis",
        "timestamp": datetime.now()
    }