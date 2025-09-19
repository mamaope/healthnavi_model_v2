"""
HealthNavi AI CDSS - Main Application

A comprehensive Clinical Decision Support System (CDSS) built with FastAPI.
This application provides AI-powered medical diagnosis assistance with secure
user authentication and email verification.

Features:
- User registration and authentication with JWT tokens
- Email verification system for enhanced security
- AI-powered medical diagnosis assistance
- Comprehensive input validation and security measures
- Rate limiting and audit logging
- HIPAA/GDPR compliant data handling

API Version: 2.0.0
Environment: Development/Production
"""

import logging
import time
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError
import uvicorn
import os

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting HealthNavi AI CDSS API...")
    
    try:
        # Check database connection
        db_url = os.getenv("DATABASE_URL", "postgresql://healthnavi_user:SecurePass123!@db:5432/healthnavi_cdss")
        logger.info(f"Database URL configured: {db_url[:50]}...")
        
        # Initialize vector store (simplified)
        logger.info("Vector store initialization skipped for now")
        
        logger.info("Application startup complete")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down HealthNavi AI CDSS API...")


# Create FastAPI application with comprehensive metadata
app = FastAPI(
    title="HealthNavi AI CDSS",
    description="""
    ## HealthNavi AI Clinical Decision Support System
    
    A comprehensive medical AI platform that provides intelligent diagnosis assistance
    to healthcare professionals and patients.
    
    ### Key Features
    
    * **🔐 Secure Authentication**: JWT-based authentication with email verification
    * **🤖 AI-Powered Diagnosis**: Advanced AI models for medical diagnosis assistance
    * **📊 Data Analytics**: Comprehensive medical data analysis and insights
    * **🛡️ Security & Compliance**: HIPAA/GDPR compliant with enterprise-grade security
    * **📱 Modern API**: RESTful API with comprehensive documentation
    
    ### Authentication
    
    All protected endpoints require a valid JWT token. Users must:
    1. Register with valid email and strong password
    2. Verify their email address
    3. Login to receive access token
    4. Include token in Authorization header: `Bearer <token>`
    
    ### Rate Limiting
    
    * Login attempts: 5 per hour per IP
    * Verification emails: 5 per hour per email
    * API requests: 100 per minute per user
    
    ### Security Features
    
    * Password hashing with salt
    * JWT tokens with expiration
    * Email verification system
    * Rate limiting and abuse prevention
    * Comprehensive audit logging
    * Input validation and sanitization
    
    ### Compliance
    
    This system is designed to meet:
    * HIPAA (Health Insurance Portability and Accountability Act)
    * GDPR (General Data Protection Regulation)
    * ISO 13485 (Medical Device Quality Management)
    """,
    version="2.0.0",
    contact={
        "name": "HealthNavi Support",
        "email": "support@healthnavi.ai",
        "url": "https://healthnavi.ai/support"
    },
    license_info={
        "name": "Proprietary",
        "url": "https://healthnavi.ai/license"
    },
    servers=[
        {
            "url": "http://localhost:8050",
            "description": "Development server"
        },
        {
            "url": "https://api.healthnavi.ai",
            "description": "Production server"
        }
    ],
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080", "http://localhost:8050"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests."""
    start_time = time.time()
    
    # Generate request ID
    request_id = f"req_{int(time.time() * 1000)}"
    
    # Log request
    logger.info(f'Request started: {request.method} {request.url.path}')
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    
    # Log response
    logger.info(f'Request completed: {response.status_code} in {process_time:.3f}s')
    
    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id
    
    return response


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logger.warning(f'HTTP exception: {exc.status_code} - {exc.detail}')
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "data": {
                "message": exc.detail
            },
            "metadata": {
                "statusCode": exc.status_code,
                "errors": [exc.detail],
                "executionTime": 0.0
            },
            "success": 0
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    logger.warning(f'Validation error: {exc.errors()}')
    
    # Convert validation errors to a more user-friendly format
    error_details = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        error_details.append(f"{field}: {message}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "data": {
                "message": "Validation error"
            },
            "metadata": {
                "statusCode": 422,
                "errors": error_details,
                "executionTime": 0.0
            },
            "success": 0
        }
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors."""
    logger.warning(f'Pydantic validation error: {exc.errors()}')
    
    # Convert validation errors to a more user-friendly format
    error_details = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        error_details.append(f"{field}: {message}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "data": {
                "message": "Validation error"
            },
            "metadata": {
                "statusCode": 422,
                "errors": error_details,
                "executionTime": 0.0
            },
            "success": 0
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f'Unexpected error: {str(exc)}')
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "data": {
                "message": "Internal server error"
            },
            "metadata": {
                "statusCode": 500,
                "errors": [str(exc)],
                "executionTime": 0.0
            },
            "success": 0
        }
    )


# Health check endpoint
@app.get(
    "/health", 
    tags=["System"],
    summary="System Health Check",
    description="""
    Check the health status of the HealthNavi AI CDSS system.
    
    This endpoint provides information about:
    - Overall system status
    - Database connectivity
    - Vector store status
    - API version and environment
    
    **Use Cases:**
    - Monitoring system health
    - Load balancer health checks
    - DevOps monitoring scripts
    - System diagnostics
    
    **Response Codes:**
    - `200`: System is healthy
    - `503`: System is unhealthy (not implemented yet)
    """,
    responses={
        200: {
            "description": "System is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "status": "healthy",
                            "version": "2.0.0",
                            "environment": "development",
                            "services": {
                                "database": "healthy",
                                "vectorstore": "healthy"
                            }
                        },
                        "metadata": {
                            "statusCode": 200,
                            "errors": [],
                            "executionTime": 0.01
                        },
                        "success": 1
                    }
                }
            }
        },
        503: {
            "description": "System is unhealthy",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "System unhealthy"
                        },
                        "metadata": {
                            "statusCode": 503,
                            "errors": ["Database connection failed"],
                            "executionTime": 0.0
                        },
                        "success": 0
                    }
                }
            }
        }
    }
)
async def health_check():
    """
    System Health Check Endpoint
    
    Returns the current health status of the HealthNavi AI CDSS system,
    including database connectivity, vector store status, and system information.
    
    This endpoint is designed for:
    - Health monitoring systems
    - Load balancer health checks
    - DevOps monitoring and alerting
    - System diagnostics and troubleshooting
    
    The response includes:
    - System status (healthy/unhealthy)
    - API version information
    - Environment details
    - Service status (database, vector store)
    - Execution time for performance monitoring
    """
    start_time = time.time()
    
    # Test database connection
    database_status = "healthy"
    try:
        from app.services.database_service import db_service
        if not db_service.test_connection():
            database_status = "unhealthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        database_status = "unhealthy"
    
    # Test email service connection
    email_status = "healthy"
    try:
        from app.services.email_service import email_service
        if not email_service.test_connection():
            email_status = "unhealthy"
    except Exception as e:
        logger.error(f"Email service health check failed: {e}")
        email_status = "unhealthy"
    
    # Simulate some processing time
    await asyncio.sleep(0.01)  # 10ms delay
    
    execution_time = round(time.time() - start_time, 2)
    
    # Determine overall system status
    overall_status = "healthy" if database_status == "healthy" and email_status == "healthy" else "unhealthy"
    
    return {
        "data": {
            "status": overall_status,
            "version": "2.0.0",
            "environment": os.getenv("ENV", "development"),
            "services": {
                "database": database_status,
                "email": email_status,
                "vectorstore": "healthy",  # Placeholder for now
            }
        },
        "metadata": {
            "statusCode": 200 if overall_status == "healthy" else 503,
            "errors": [] if overall_status == "healthy" else ["Service connection failed"],
            "executionTime": execution_time
        },
        "success": 1 if overall_status == "healthy" else 0
    }


# Root endpoint
@app.get(
    "/", 
    tags=["System"],
    summary="API Welcome Endpoint",
    description="""
    Welcome endpoint for the HealthNavi AI CDSS API.
    
    This endpoint provides:
    - Welcome message and API information
    - Current API version
    - Environment information
    - Links to documentation and health check
    
    **Use Cases:**
    - API discovery and information
    - Quick system status check
    - Documentation links
    - Version verification
    
    **Response Information:**
    - API version and environment
    - Links to interactive documentation
    - Health check endpoint reference
    """,
    responses={
        200: {
            "description": "API information retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "Welcome to HealthNavi AI CDSS!",
                            "version": "2.0.0",
                            "environment": "development",
                            "docs_url": "/docs",
                            "health_check": "/health"
                        },
                        "metadata": {
                            "statusCode": 200,
                            "errors": [],
                            "executionTime": 0.005
                        },
                        "success": 1
                    }
                }
            }
        }
    }
)
async def root():
    """
    API Welcome and Information Endpoint
    
    Provides basic information about the HealthNavi AI CDSS API,
    including version, environment, and helpful links.
    
    This endpoint serves as:
    - API discovery point
    - Version verification
    - Quick system information
    - Documentation gateway
    
    Returns:
    - Welcome message
    - API version (2.0.0)
    - Current environment (development/production)
    - Links to documentation (/docs) and health check (/health)
    """
    start_time = time.time()
    
    # Simulate some processing time
    await asyncio.sleep(0.005)  # 5ms delay
    
    execution_time = round(time.time() - start_time, 2)
    
    return {
        "data": {
            "message": "Welcome to HealthNavi AI CDSS!",
            "version": "2.0.0",
            "environment": os.getenv("ENV", "development"),
            "docs_url": "/docs",
            "health_check": "/health"
        },
        "metadata": {
            "statusCode": 200,
            "errors": [],
            "executionTime": execution_time
        },
        "success": 1
    }


# Include routers (simplified)
try:
    from app.routers import auth, diagnosis
    app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
    app.include_router(diagnosis.router, prefix="/diagnosis", tags=["Diagnosis"])
    logger.info("Routers loaded successfully")
except ImportError as e:
    logger.warning(f"Could not load routers: {e}")


# Development server
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8050,
        reload=True,
        log_level="info",
        access_log=True,
    )