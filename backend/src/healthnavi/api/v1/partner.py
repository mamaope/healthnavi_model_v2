"""
Partner-facing diagnosis endpoint with scoped bearer auth.

This keeps existing public/mobile/web APIs untouched while adding a
partner-only surface that requires a short-lived, scope-bearing token.
"""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from healthnavi.core.config import get_config
from healthnavi.core.database import get_db
from healthnavi.core.response_utils import (
    create_error_response,
    create_success_response,
    ResponseTimer,
)
from healthnavi.schemas import DiagnosisInput, DiagnosisResponse, StandardResponse
from healthnavi.services.conversational_service import generate_response

logger = logging.getLogger(__name__)
router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=True)
config = get_config()


def _has_scope(scopes: List[str], required: str) -> bool:
    """Check for required scope in a space-delimited scope list."""
    return required in scopes


def verify_partner_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """
    Validate a partner token:
    - HS256 using the configured secret_key
    - token_type == "partner"
    - scope includes "diagnosis:read"
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            config.security.secret_key,
            algorithms=[config.security.algorithm],
            options={"verify_aud": False},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid partner token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_type = payload.get("token_type")
    scope_raw = payload.get("scope") or payload.get("scopes") or ""
    scopes = scope_raw.split() if isinstance(scope_raw, str) else []

    if token_type != "partner" or not _has_scope(scopes, "diagnosis:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient partner scope",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


@router.post("/diagnose", response_model=StandardResponse)
async def partner_diagnose(
    data: DiagnosisInput,
    _partner=Depends(verify_partner_token),
    db: Session = Depends(get_db),
):
    """
    Partner-facing diagnosis endpoint.

    Differences vs public/mobile/web:
    - Requires partner bearer token with scope `diagnosis:read`.
    - Does NOT persist chat sessions or messages (stateless).
    - Returns the same payload shape for compatibility.
    """
    with ResponseTimer() as timer:
        try:
            if not data.patient_data or len(data.patient_data.strip()) < 3:
                return create_error_response(
                    message="Patient data must be at least 3 characters long",
                    status_code=400,
                    execution_time=timer.get_execution_time(),
                )

            chat_history = data.chat_history or ""
            deep_search_enabled = data.deep_search if data.deep_search is not None else False

            try:
                response, diagnosis_complete, prompt_type, followup_questions = await generate_response(
                    query=data.patient_data,
                    chat_history=chat_history,
                    patient_data=data.patient_data,
                    deep_search=deep_search_enabled,
                )
                if followup_questions is None:
                    followup_questions = []
                if not response or len(response.strip()) < 10:
                    return create_error_response(
                        message="AI service returned insufficient response. Please try again.",
                        status_code=503,
                        execution_time=timer.get_execution_time(),
                    )
            except Exception as ai_error:
                logger.error(f"AI service error (partner): {str(ai_error)}")
                return create_error_response(
                    message="AI service is currently unavailable.",
                    status_code=503,
                    execution_time=timer.get_execution_time(),
                )

            updated_chat_history = (
                f"{chat_history}\nDoctor: {data.patient_data}\nAI Assistant: {response}"
                if chat_history
                else f"Doctor: {data.patient_data}\nAI Assistant: {response}"
            )

            diagnosis_data = DiagnosisResponse(
                model_response=response,
                diagnosis_complete=diagnosis_complete,
                updated_chat_history=updated_chat_history,
                session_id=None,  # stateless for partner use
                message_id=None,
                prompt_type=prompt_type,
                followup_questions=followup_questions,
            )

            return create_success_response(
                data=diagnosis_data,
                status_code=200,
                execution_time=timer.get_execution_time(),
            )

        except HTTPException:
            # Let FastAPI handle propagated HTTP errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error in partner diagnose: {str(e)}", exc_info=True)
            return create_error_response(
                message="Diagnosis generation failed",
                status_code=500,
                execution_time=timer.get_execution_time(),
            )



