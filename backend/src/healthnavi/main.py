"""
Main FastAPI application for HealthNavi AI CDSS.
"""

import asyncio
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True  # Override any existing configuration
)
logger = logging.getLogger(__name__)

from healthnavi.core.config import get_config
from healthnavi.core.response_utils import create_success_response, create_error_response, ResponseTimer
from healthnavi.schemas import StandardResponse
from healthnavi.api.v1 import auth, diagnosis, chat_sessions, partner, admin, surveys

config = get_config()

# Conditionally import transcription router
try:
    from healthnavi.api.v1 import transcription
    TRANSCRIPTION_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Transcription router not available: {e}")
    TRANSCRIPTION_AVAILABLE = False
    transcription = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting HealthNavi AI CDSS application...")
    try:
        from healthnavi.core.database import initialize_database
        initialize_database()
        logger.info("Database initialization completed")
    except Exception as e:
        logger.warning(f"Database initialization failed during startup: {e}")
        logger.info("Application will continue - database will be initialized on first access")
    
    try:
        from healthnavi.services.vectorstore_manager import initialize_vectorstore
        initialize_vectorstore()
        logger.info("Vector store initialization completed")
    except Exception as e:
        logger.warning(f"Vector store initialization failed during startup: {e}")
        logger.info("Application will continue - AI will work without RAG context")
    
    try:
        from healthnavi.services.genai_client import initialize_genai_client
        initialize_genai_client()
        logger.info("GenAI client initialization completed")
    except Exception as e:
        logger.warning(f"GenAI client initialization failed during startup: {e}")
        logger.info("Application will continue - AI functionality may be limited")
    
    try:
        from healthnavi.services.transcription_service import preload_model
        # Run in background or just log that it's loading
        logger.info("Preloading Whisper model...")
        preload_model()
        logger.info("Whisper model preloading completed")
    except Exception as e:
        logger.warning(f"Whisper model preloading failed: {e}")
        logger.info("Application will continue - Transcription will load on first use")

    logger.info("Application startup completed successfully")

    # Background job: process pending user data deletions (6 months after request)
    async def _run_pending_deletions_job():
        from healthnavi.core.database import SessionLocal
        from healthnavi.services.data_deletion_service import process_pending_deletions
        # First run after 60s to let DB be ready; then every 24h
        await asyncio.sleep(60)
        while True:
            try:
                db = SessionLocal()
                try:
                    n = process_pending_deletions(db)
                    if n:
                        logger.info(f"Data deletion job: permanently deleted {n} user(s) per deferred privacy requests.")
                finally:
                    db.close()
            except Exception as e:
                logger.exception(f"Data deletion job error: {e}")
            await asyncio.sleep(86400)  # 24 hours

    _deletion_task = asyncio.create_task(_run_pending_deletions_job())
    
    yield
    
    # Shutdown
    _deletion_task.cancel()
    try:
        await _deletion_task
    except asyncio.CancelledError:
        pass
    logger.info("Shutting down HealthNavi AI CDSS application...")


# Create FastAPI application
app = FastAPI(
    title=config.application.app_name,
    description=config.application.app_description,
    version=config.application.app_version,
    lifespan=lifespan,
)

# Add CORS middleware with environment-aware configuration
# Get CORS origins from environment variable or config
import os
cors_origins_env = os.getenv("CORS_ORIGINS", "")
if cors_origins_env:
    cors_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
else:
    cors_origins = ["*"]  # Default to all in development

# Warn if production allows all origins
if config.application.environment == "production" and cors_origins == ["*"]:
    logger.warning("CORS is set to allow all origins in production. Set CORS_ORIGINS environment variable!")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)


# Request logging middleware with correlation IDs
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with correlation IDs for tracing."""
    # Generate correlation ID for this request
    correlation_id = str(uuid.uuid4())[:8]
    request.state.correlation_id = correlation_id
    
    start_time = time.time()
    
    # Log request immediately when received
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"[{correlation_id}] >>> {request.method} {request.url.path} from {client_ip}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"[{correlation_id}] <<< {response.status_code} {request.url.path} ({process_time:.2f}s)")
        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"[{correlation_id}] !!! FAILED {request.url.path} after {process_time:.2f}s: {e}")
        raise


# Request validation error handler (422 errors)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors (422)."""
    logger.error(f"Request validation error for {request.method} {request.url.path}: {exc.errors()}")
    logger.error(f"Request query params: {request.query_params}")
    logger.error(f"Request path params: {request.path_params}")
    
    # Create standardized error response
    error_details = [f"{err.get('loc', [])}: {err.get('msg', '')}" for err in exc.errors()]
    error_response = create_error_response(
        message="Request validation failed",
        status_code=422,
        errors=error_details,
        execution_time=0.0
    )
    
    return JSONResponse(
        status_code=422,
        content=error_response.model_dump(mode='json')
    )

# HTTPException handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP exception handler."""
    logger.warning(f"HTTP exception: {exc.status_code} - {exc.detail}")
    
    # Create standardized error response
    error_response = create_error_response(
        message=str(exc.detail),
        status_code=exc.status_code,
        errors=[str(exc.detail)],
        execution_time=0.0
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(mode='json')
    )


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # Create standardized error response
    error_response = create_error_response(
        message="Internal server error",
        status_code=500,
        errors=[str(exc)],
        execution_time=0.0
    )
    
    return JSONResponse(
        status_code=500,
        content=error_response.model_dump(mode='json')
    )


# Health check endpoint
@app.get("/health", response_model=StandardResponse)
async def health_check():
    """Application health check."""
    with ResponseTimer() as timer:
        health_data = {
            "status": "healthy",
            "timestamp": time.time(),
            "version": config.application.app_version,
            "environment": config.application.environment
        }
        
        return create_success_response(
            data=health_data,
            status_code=200,
            execution_time=timer.get_execution_time()
        )

# API version health check endpoint
@app.get("/api/v2/health", response_model=StandardResponse)
async def api_health_check():
    """API health check endpoint."""
    with ResponseTimer() as timer:
        health_data = {
            "status": "healthy",
            "timestamp": time.time(),
            "version": config.application.app_version,
            "environment": config.application.environment
        }
        
        return create_success_response(
            data=health_data,
            status_code=200,
            execution_time=timer.get_execution_time()
        )

API_VERSION_PREFIX = "/api/v2"

# Health check endpoint under API prefix (for consistency with frontend expectations)
@app.get(f"{API_VERSION_PREFIX}/health", response_model=StandardResponse)
async def api_health_check():
    """API health check endpoint."""
    with ResponseTimer() as timer:
        health_data = {
            "status": "healthy",
            "timestamp": time.time(),
            "version": config.application.app_version,
            "environment": config.application.environment,
            "api_version": "v2"
        }
        
        return create_success_response(
            data=health_data,
            status_code=200,
            execution_time=timer.get_execution_time()
        )

# Include API routers
app.include_router(auth.router, prefix=f"{API_VERSION_PREFIX}/auth", tags=["Authentication"])
app.include_router(diagnosis.router, prefix=f"{API_VERSION_PREFIX}/diagnosis", tags=["Diagnosis"])
app.include_router(chat_sessions.router, prefix=f"{API_VERSION_PREFIX}/chat", tags=["Chat Sessions"])
app.include_router(admin.router, prefix=f"{API_VERSION_PREFIX}/admin", tags=["Admin"])
app.include_router(surveys.router, prefix=f"{API_VERSION_PREFIX}/surveys", tags=["Surveys"])

# Conditionally include transcription router
if TRANSCRIPTION_AVAILABLE and transcription:
    app.include_router(transcription.router, prefix=f"{API_VERSION_PREFIX}/transcription", tags=["Transcription"])
    logger.info("Transcription router registered")
else:
    logger.warning("Transcription router not available - install openai-whisper and torch to enable")

app.include_router(partner.router, prefix="/partner/diagnosis", tags=["Partner Diagnosis"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.application.api_host,
        port=config.application.api_port,
        reload=config.application.debug,
        log_level=config.application.debug and "debug" or "info"
    )
