import logging
from fastapi import APIRouter, HTTPException, Depends
from app.auth import require_user_role
from app.models.schemas import DiagnosisInput, DiagnosisResponse
from app.services.vectorstore_manager import initialize_vectorstore
from app.services.conversational_service import generate_response

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

@router.post("/diagnose", response_model=DiagnosisResponse)
async def diagnose(data: DiagnosisInput, current_user=Depends(require_user_role)):
    try:
        query = data.patient_data
        response, diagnosis_complete = await generate_response(
            query=query,
            chat_history=data.chat_history,
            patient_data=data.patient_data
        )

        updated_chat_history = (
            f"{data.chat_history}\nDoctor: {data.patient_data}\nModel: {response}"
            if data.chat_history else
            f"Doctor: {data.patient_data}\nModel: {response}"
        )

        logger.info(f"Diagnosis endpoint called. Query: {query[:50]}... Complete: {diagnosis_complete}")
        return DiagnosisResponse(
            model_response=response,
            diagnosis_complete=diagnosis_complete,
            updated_chat_history=updated_chat_history,
        )
    except HTTPException as e:
        logger.error(f"HTTP error in diagnose endpoint: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in diagnose endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
