from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from sqlalchemy.orm import Session
from app.routers.auth import router as auth_router
import logging
from fastapi import FastAPI
from app.routers import diagnosis
from app.services.vectorstore_manager import initialize_vectorstore
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="HealthNavi AI CDSS API",
    description="API for conversational clinical decision support using RAG.",
    root_path="/api/v2"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.on_event("startup")
async def startup_event():
    """
    Initialise the vector store at start up.
    """
    logger.info("Starting up HealthNavi AI API...")

    try:
        initialize_vectorstore()
        logger.info("Startup complete.")
    except Exception as e:
        logger.error(f"FATAL: Could not initialize vector store. Shutting down. Error: {e}")
        raise
        
@app.get("/")
def read_root():
    return {"message": "Welcome to the HealthNavi AI CDSS API!"}


app.include_router(diagnosis.router, tags=["Diagnosis"])
app.include_router(auth_router, tags=["Auth"])



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8050)
# uvicorn app.main:app --reload --host 0.0.0.0 --port 8050
