import logging
import time
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from app.auth import get_current_active_user
from app.models.schemas import DiagnosisInput
from app.services.vectorstore_manager import initialize_vectorstore
from app.services.conversational_service import generate_response_stream

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

@router.post("/diagnose")
async def diagnose(data: DiagnosisInput, current_user=Depends(get_current_active_user)):
    request_start_time = time.time()
    logger.info(f"New request from user: {current_user.username}")

    try:
        # The core processing is now a generator that we will stream
        response_generator = generate_response_stream(
            query=data.patient_data,
            chat_history=data.chat_history,
            patient_data=data.patient_data
        )
        
        # FastAPI's StreamingResponse will handle iterating over the async generator
        # and sending the data to the client chunk by chunk.
        return StreamingResponse(response_generator, media_type="text/plain")

    except Exception as e:
        error_time = time.time() - request_start_time
        logger.error(f"Error after {error_time:.2f}s: {e}")
        # This will catch errors that happen before the stream begins
        raise HTTPException(status_code=500, detail=f"Error setting up stream: {str(e)}")


    # try:
    #     # Authentication and request parsing timing
    #     auth_time = time.time() - request_start
        
    #     # Core processing
    #     processing_start = time.time()
    #     query = data.patient_data
    #     response, diagnosis_complete = await generate_response(
    #         query=query,
    #         chat_history=data.chat_history,
    #         patient_data=data.patient_data
    #     )
    #     processing_time = time.time() - processing_start

    #     # Response formatting
    #     formatting_start = time.time()
    #     updated_chat_history = (
    #         f"{data.chat_history}\nDoctor: {data.patient_data}\nModel: {response}"
    #         if data.chat_history else
    #         f"Doctor: {data.patient_data}\nModel: {response}"
    #     )
    #     formatting_time = time.time() - formatting_start

    #     # Total request timing
    #     total_request_time = time.time() - request_start
    #     response_length = len(response)
        
    #     logger.info(f"🏁 ===== REQUEST COMPLETED =====")
    #     logger.info(f"📊 TOTAL REQUEST BREAKDOWN:")
    #     logger.info(f"   ├── Auth & Parsing: {auth_time:.3f}s ({auth_time/total_request_time*100:.1f}%)")
    #     logger.info(f"   ├── Core Processing: {processing_time:.3f}s ({processing_time/total_request_time*100:.1f}%)")
    #     logger.info(f"   └── Response Formatting: {formatting_time:.3f}s ({formatting_time/total_request_time*100:.1f}%)")
    #     logger.info(f"⏱️  TOTAL REQUEST TIME: {total_request_time:.3f}s")
    #     logger.info(f"📄 Response: {response_length} chars, Complete: {diagnosis_complete}")
    #     logger.info("=" * 60)

    #     return DiagnosisResponse(
    #         model_response=response,
    #         diagnosis_complete=diagnosis_complete,
    #         updated_chat_history=updated_chat_history,
    #     )
    # except HTTPException as e:
    #     error_time = time.time() - request_start
    #     logger.error(f"❌ HTTP error after {error_time:.3f}s in diagnose endpoint: {e}")
    #     raise
    # except Exception as e:
    #     error_time = time.time() - request_start
    #     logger.error(f"❌ Unexpected error after {error_time:.3f}s in diagnose endpoint: {e}")
    #     raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
