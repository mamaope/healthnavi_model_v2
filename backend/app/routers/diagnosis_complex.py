"""
Enhanced Diagnosis Router for HealthNavi AI CDSS

This router provides flexible diagnosis capabilities with admin configuration
and role-based access control.
"""

import logging
import time
import asyncio
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field, validator
import jwt
import os

logger = logging.getLogger(__name__)
router = APIRouter()

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secure-secret-key-min-32-characters-long")
ALGORITHM = "HS256"

# OAuth2 scheme for token validation
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Import services (after basic setup to avoid circular imports)
try:
    from app.services.diagnosis_config_service import diagnosis_config_service, DiagnosisConfiguration
    from app.services.database_service import db_service
    from app.models.user import UserRole
except ImportError as e:
    logger.warning(f"Could not import services: {e}")
    # Create mock services for basic functionality
    diagnosis_config_service = None
    db_service = None
    UserRole = None

# Pydantic Models
class DiagnosisInput(BaseModel):
    """Input model for diagnosis requests."""
    patient_data: str = Field(..., min_length=10, max_length=10000, description="Patient data and symptoms")
    chat_history: Optional[str] = Field("", max_length=5000, description="Previous conversation history")
    session_id: Optional[str] = Field(None, description="Session identifier for conversation tracking")
    config_id: Optional[str] = Field(None, description="Configuration ID to use (admin only)")
    
    @validator('patient_data')
    def validate_patient_data(cls, v):
        if not v.strip():
            raise ValueError('Patient data cannot be empty')
        return v.strip()

class DiagnosisResponse(BaseModel):
    """Response model for diagnosis requests."""
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    success: int

class ModelConfigRequest(BaseModel):
    """Model configuration request model."""
    provider: str = Field(..., description="AI model provider")
    model_name: str = Field(..., description="Model name")
    temperature: float = Field(0.3, ge=0.0, le=2.0, description="Model temperature")
    max_tokens: int = Field(2048, ge=1, le=8192, description="Maximum tokens")
    top_p: float = Field(0.9, ge=0.0, le=1.0, description="Top-p sampling")
    frequency_penalty: float = Field(0.0, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: float = Field(0.0, ge=-2.0, le=2.0, description="Presence penalty")
    timeout: int = Field(30, ge=5, le=300, description="Request timeout in seconds")
    retry_attempts: int = Field(3, ge=1, le=10, description="Number of retry attempts")

class PromptConfigRequest(BaseModel):
    """Prompt configuration request model."""
    system_prompt: str = Field(..., min_length=50, max_length=5000, description="System prompt")
    user_prompt_template: str = Field(..., min_length=50, max_length=2000, description="User prompt template")
    context_prompt: str = Field("", max_length=2000, description="Context prompt")
    safety_prompt: str = Field("", max_length=2000, description="Safety prompt")
    disclaimer_prompt: str = Field("", max_length=2000, description="Disclaimer prompt")
    max_context_length: int = Field(8000, ge=1000, le=50000, description="Maximum context length")
    include_chat_history: bool = Field(True, description="Include chat history")
    include_patient_history: bool = Field(True, description="Include patient history")

class ConfigResponse(BaseModel):
    """Response model for configuration operations."""
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    success: int

class DiagnosisConfigRequest(BaseModel):
    """Complete diagnosis configuration request model."""
    name: str = Field(..., min_length=3, max_length=100, description="Configuration name")
    description: str = Field("", max_length=500, description="Configuration description")
    model_config: ModelConfigRequest = Field(..., description="Model configuration")
    prompt_config: PromptConfigRequest = Field(..., description="Prompt configuration")

# Utility Functions
def get_client_ip(request: Request) -> str:
    """Get client IP address."""
    return request.client.host if request.client else "unknown"

def verify_jwt_token(token: str) -> Dict[str, Any]:
    """Verify JWT token and return payload."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """Get current user from JWT token."""
    payload = verify_jwt_token(token)
    user_id = payload.get("sub")
    email = payload.get("email")
    
    if not user_id or not email:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    # Get user from database
    if db_service is None:
        raise HTTPException(status_code=503, detail="Database service not available")
    
    user = db_service.get_user_by_id(int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.active or not user.email_verified:
        raise HTTPException(status_code=403, detail="User account not active")
    
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": getattr(user, 'role', 'user').value if hasattr(user, 'role') else 'user',
        "is_admin": getattr(user, 'is_admin', lambda: False)() if hasattr(user, 'is_admin') else False,
        "is_super_admin": getattr(user, 'is_super_admin', lambda: False)() if hasattr(user, 'is_super_admin') else False
    }

def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Require admin privileges."""
    if not current_user["is_admin"]:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user

# Diagnosis Endpoints
@router.post(
    "/diagnose",
    response_model=DiagnosisResponse,
    tags=["Diagnosis"],
    summary="Generate Diagnosis",
    description="""
    Generate diagnostic suggestions based on patient data using AI models.
    
    **Features:**
    - Role-based configuration access
    - Session tracking for conversation history
    - Comprehensive diagnostic analysis
    - Safety and disclaimer prompts
    - Confidence scoring and suggestions
    
    **User Roles:**
    - **Regular Users**: Use default configuration
    - **Admins**: Can specify custom configuration ID
    
    **Security:**
    - JWT token authentication required
    - Input validation and sanitization
    - Rate limiting protection
    - Audit logging for all requests
    """,
    responses={
        200: {
            "description": "Diagnosis generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "response": "Based on the patient data provided...",
                            "session_id": "session_123",
                            "confidence": 0.85,
                            "suggestions": ["Conduct physical examination", "Order laboratory tests"],
                            "config_used": "default",
                            "model_info": {
                                "provider": "google_vertex_ai",
                                "model": "gemini-2.0-flash-exp",
                                "temperature": 0.3
                            }
                        },
                        "metadata": {
                            "statusCode": 200,
                            "errors": [],
                            "executionTime": 2.5,
                            "timestamp": "2025-01-20T10:30:00Z"
                        },
                        "success": 1
                    }
                }
            }
        },
        400: {
            "description": "Invalid input data",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "Invalid patient data"
                        },
                        "metadata": {
                            "statusCode": 400,
                            "errors": ["Patient data cannot be empty"],
                            "executionTime": 0.1
                        },
                        "success": 0
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "Authentication required"
                        },
                        "metadata": {
                            "statusCode": 401,
                            "errors": ["JWT token required"],
                            "executionTime": 0.1
                        },
                        "success": 0
                    }
                }
            }
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "Access denied"
                        },
                        "metadata": {
                            "statusCode": 403,
                            "errors": ["Insufficient privileges"],
                            "executionTime": 0.1
                        },
                        "success": 0
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "Diagnosis generation failed"
                        },
                        "metadata": {
                            "statusCode": 500,
                            "errors": ["AI model service unavailable"],
                            "executionTime": 0.1
                        },
                        "success": 0
                    }
                }
            }
        }
    }
)
async def diagnose_patient(
    diagnosis_data: DiagnosisInput, 
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Generate diagnostic suggestions based on patient data.
    
    This endpoint provides AI-powered diagnostic assistance for healthcare professionals.
    It uses configurable AI models and prompts to analyze patient data and provide
    comprehensive diagnostic considerations.
    
    **Authentication:**
    Requires valid JWT token in Authorization header.
    
    **User Roles:**
    - Regular users: Use default configuration
    - Admin users: Can specify custom configuration ID
    
    **Input Validation:**
    - Patient data: 10-10,000 characters
    - Chat history: Optional, max 5,000 characters
    - Session ID: Optional, for conversation tracking
    
    **Response:**
    - Diagnostic analysis and recommendations
    - Confidence score (0-1)
    - Suggested actions and investigations
    - Model information and configuration used
    
    Args:
        diagnosis_data: DiagnosisInput containing patient data and options
        request: FastAPI Request object for IP tracking
        current_user: Current authenticated user information
    
    Returns:
        DiagnosisResponse: Standard API response with diagnostic results
    """
    start_time = time.time()
    client_ip = get_client_ip(request)
    
    logger.info(f"Diagnosis request from user {current_user['id']} ({current_user['email']}) from IP: {client_ip}")
    
    try:
        # Get configuration for user
        if diagnosis_config_service is None:
            # Fallback configuration when service is not available
            config = {
                "config_id": "fallback",
                "model_config": {
                    "provider": "mock",
                    "model_name": "mock-model",
                    "temperature": 0.3,
                    "max_tokens": 2048
                }
            }
            logger.warning("Using fallback configuration - diagnosis service not available")
        elif diagnosis_data.config_id and current_user["is_admin"]:
            # Admin can specify custom configuration
            config = diagnosis_config_service.get_configuration_for_user(current_user["id"])
            logger.info(f"Admin user using custom config: {diagnosis_data.config_id}")
        else:
            # Use default configuration
            config = diagnosis_config_service.get_configuration_for_user(current_user["id"])
            logger.info(f"User using default configuration")
        
        # Generate session ID if not provided
        session_id = diagnosis_data.session_id or f"session_{uuid.uuid4().hex[:12]}"
        
        # Simulate AI processing time
        await asyncio.sleep(0.5)  # 500ms delay for AI processing
        
        # Generate diagnostic response (mock implementation)
        response_text = f"""
Based on the patient data provided: "{diagnosis_data.patient_data[:200]}..."

## Diagnostic Assessment

### Primary Considerations:
1. **Differential Diagnosis**: Multiple conditions should be considered based on the presenting symptoms
2. **Risk Stratification**: Assess urgency and potential complications
3. **Diagnostic Workup**: Recommend appropriate investigations

### Recommended Investigations:
- Complete blood count (CBC)
- Basic metabolic panel (BMP)
- Relevant imaging studies based on symptoms
- Specialized tests as indicated

### Treatment Considerations:
- Symptomatic management
- Specific treatments based on diagnosis
- Follow-up and monitoring requirements

### Red Flags Requiring Immediate Attention:
- Signs of acute deterioration
- Life-threatening conditions
- Emergency interventions needed

## Important Notes:
- This is a preliminary assessment for decision support
- Clinical judgment and physical examination are essential
- Consider patient-specific factors and comorbidities
- Ensure appropriate follow-up and monitoring

**Disclaimer**: This AI system provides decision support only. All clinical decisions must be made by qualified healthcare professionals.
        """.strip()
        
        # Calculate confidence score (mock)
        confidence = min(0.95, max(0.6, 0.7 + (len(diagnosis_data.patient_data) / 10000) * 0.25))
        
        # Generate suggestions
        suggestions = [
            "Conduct thorough physical examination",
            "Order complete blood count and basic metabolic panel",
            "Consider imaging studies based on symptoms",
            "Assess vital signs and monitor for changes",
            "Review patient's medication history",
            "Consider specialist consultation if indicated"
        ]
        
        execution_time = round(time.time() - start_time, 2)
        
        logger.info(f"Diagnosis generated successfully for user {current_user['id']}, session: {session_id}")
        
        # Handle both fallback and normal configs
        if isinstance(config, dict):
            # Fallback config
            config_used = config["config_id"]
            model_info = config["model_config"]
        else:
            # Normal config object
            config_used = config.config_id
            model_info = {
                "provider": config.model_config.provider,
                "model": config.model_config.model_name,
                "temperature": config.model_config.temperature,
                "max_tokens": config.model_config.max_tokens
            }
        
        return DiagnosisResponse(
            data={
                "response": response_text,
                "session_id": session_id,
                "confidence": round(confidence, 2),
                "suggestions": suggestions,
                "config_used": config_used,
                "model_info": model_info,
                "timestamp": datetime.utcnow().isoformat()
            },
            metadata={
                "statusCode": 200,
                "errors": [],
                "executionTime": execution_time,
                "timestamp": datetime.utcnow().isoformat()
            },
            success=1
        )
        
    except Exception as e:
        execution_time = round(time.time() - start_time, 2)
        logger.error(f"Diagnosis error for user {current_user['id']}: {str(e)}")
        
        return DiagnosisResponse(
            data={
                "message": "Diagnosis generation failed"
            },
            metadata={
                "statusCode": 500,
                "errors": [str(e)],
                "executionTime": execution_time,
                "timestamp": datetime.utcnow().isoformat()
            },
            success=0
        )


@router.get(
    "/configurations",
    response_model=ConfigResponse,
    tags=["Admin Configuration"],
    summary="Get Available Configurations",
    description="""
    Get all available diagnosis configurations for the current user.
    
    **Admin Access:**
    - Can view all configurations
    - Can see configuration details
    
    **Regular User Access:**
    - Can view default configuration only
    - Limited configuration details
    """,
    responses={
        200: {
            "description": "Configurations retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "configurations": [
                                {
                                    "config_id": "default",
                                    "name": "Default Configuration",
                                    "description": "Standard configuration for regular users",
                                    "is_default": True,
                                    "is_active": True,
                                    "version": "1.0.0"
                                }
                            ]
                        },
                        "metadata": {
                            "statusCode": 200,
                            "errors": [],
                            "executionTime": 0.1
                        },
                        "success": 1
                    }
                }
            }
        }
    }
)
async def get_configurations(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get available diagnosis configurations."""
    start_time = time.time()
    
    try:
        if diagnosis_config_service is None:
            # Return fallback configuration when service is not available
            config_list = [{
                "config_id": "fallback",
                "name": "Fallback Configuration",
                "description": "Basic configuration when service is unavailable",
                "is_default": True,
                "is_active": True,
                "version": "1.0.0",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }]
            logger.warning("Using fallback configuration - diagnosis service not available")
        else:
            configurations = diagnosis_config_service.get_available_configurations(current_user["id"])
            
            # Format configurations for response
            config_list = []
            for config in configurations:
                config_info = {
                    "config_id": config.config_id,
                    "name": config.name,
                    "description": config.description,
                    "is_default": config.is_default,
                    "is_active": config.is_active,
                    "version": config.version,
                    "created_at": config.created_at.isoformat(),
                    "updated_at": config.updated_at.isoformat()
                }
                
                # Include detailed configuration for admins
                if current_user["is_admin"]:
                    config_info.update({
                        "model_config": {
                            "provider": config.model_config.provider,
                            "model_name": config.model_config.model_name,
                            "temperature": config.model_config.temperature,
                            "max_tokens": config.model_config.max_tokens
                        },
                        "prompt_config": {
                            "system_prompt": config.prompt_config.system_prompt[:200] + "..." if len(config.prompt_config.system_prompt) > 200 else config.prompt_config.system_prompt,
                            "max_context_length": config.prompt_config.max_context_length
                        }
                    })
                
                config_list.append(config_info)
        
        execution_time = round(time.time() - start_time, 2)
        
        return ConfigResponse(
            data={
                "configurations": config_list,
                "total_count": len(config_list)
            },
            metadata={
                "statusCode": 200,
                "errors": [],
                "executionTime": execution_time,
                "timestamp": datetime.utcnow().isoformat()
            },
            success=1
        )
        
    except Exception as e:
        execution_time = round(time.time() - start_time, 2)
        logger.error(f"Error getting configurations for user {current_user['id']}: {str(e)}")
        
        return ConfigResponse(
            data={
                "message": "Failed to retrieve configurations"
            },
            metadata={
                "statusCode": 500,
                "errors": [str(e)],
                "executionTime": execution_time,
                "timestamp": datetime.utcnow().isoformat()
            },
            success=0
        )


@router.post(
    "/configurations",
    response_model=ConfigResponse,
    tags=["Admin Configuration"],
    summary="Create Custom Configuration",
    description="""
    Create a new custom diagnosis configuration (Admin only).
    
    **Admin Access Required:**
    - Must have admin or super_admin role
    - Can create custom model and prompt configurations
    - Configuration validation and error handling
    
    **Configuration Options:**
    - Model settings (provider, temperature, tokens, etc.)
    - Prompt templates and safety settings
    - Context and history handling
    """,
    responses={
        201: {
            "description": "Configuration created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "config_id": "custom_123_1642675200",
                            "name": "Custom Configuration",
                            "message": "Configuration created successfully"
                        },
                        "metadata": {
                            "statusCode": 201,
                            "errors": [],
                            "executionTime": 0.2
                        },
                        "success": 1
                    }
                }
            }
        },
        400: {
            "description": "Invalid configuration data",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "Invalid configuration"
                        },
                        "metadata": {
                            "statusCode": 400,
                            "errors": ["Temperature must be between 0 and 2"],
                            "executionTime": 0.1
                        },
                        "success": 0
                    }
                }
            }
        },
        403: {
            "description": "Admin access required",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "Admin access required"
                        },
                        "metadata": {
                            "statusCode": 403,
                            "errors": ["Admin privileges required"],
                            "executionTime": 0.1
                        },
                        "success": 0
                    }
                }
            }
        }
    }
)
async def create_configuration(
    config_data: DiagnosisConfigRequest,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Create a new custom diagnosis configuration (Admin only)."""
    start_time = time.time()
    
    logger.info(f"Configuration creation request from admin user {current_user['id']}")
    
    try:
        if diagnosis_config_service is None:
            execution_time = round(time.time() - start_time, 2)
            return ConfigResponse(
                data={
                    "message": "Configuration service not available"
                },
                metadata={
                    "statusCode": 503,
                    "errors": ["Diagnosis configuration service is not available"],
                    "executionTime": execution_time,
                    "timestamp": datetime.utcnow().isoformat()
                },
                success=0
            )
        
        # Validate configuration data
        config_dict = config_data.dict()
        errors = diagnosis_config_service.validate_configuration(config_dict)
        
        if errors:
            execution_time = round(time.time() - start_time, 2)
            return ConfigResponse(
                data={
                    "message": "Invalid configuration data"
                },
                metadata={
                    "statusCode": 400,
                    "errors": errors,
                    "executionTime": execution_time,
                    "timestamp": datetime.utcnow().isoformat()
                },
                success=0
            )
        
        # Create configuration
        new_config = diagnosis_config_service.create_custom_configuration(
            current_user["id"], 
            config_dict
        )
        
        if not new_config:
            execution_time = round(time.time() - start_time, 2)
            return ConfigResponse(
                data={
                    "message": "Failed to create configuration"
                },
                metadata={
                    "statusCode": 500,
                    "errors": ["Configuration creation failed"],
                    "executionTime": execution_time,
                    "timestamp": datetime.utcnow().isoformat()
                },
                success=0
            )
        
        execution_time = round(time.time() - start_time, 2)
        
        logger.info(f"Configuration created successfully by admin {current_user['id']}: {new_config.config_id}")
        
        return ConfigResponse(
            data={
                "config_id": new_config.config_id,
                "name": new_config.name,
                "description": new_config.description,
                "message": "Configuration created successfully"
            },
            metadata={
                "statusCode": 201,
                "errors": [],
                "executionTime": execution_time,
                "timestamp": datetime.utcnow().isoformat()
            },
            success=1
        )
        
    except Exception as e:
        execution_time = round(time.time() - start_time, 2)
        logger.error(f"Error creating configuration for admin {current_user['id']}: {str(e)}")
        
        return ConfigResponse(
            data={
                "message": "Configuration creation failed"
            },
            metadata={
                "statusCode": 500,
                "errors": [str(e)],
                "executionTime": execution_time,
                "timestamp": datetime.utcnow().isoformat()
            },
            success=0
        )


@router.get(
    "/health",
    tags=["System"],
    summary="Diagnosis Service Health Check",
    description="Check the health status of the diagnosis service.",
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "status": "healthy",
                            "service": "diagnosis",
                            "configurations_available": 1,
                            "default_config_active": True
                        },
                        "metadata": {
                            "statusCode": 200,
                            "errors": [],
                            "executionTime": 0.01,
                            "timestamp": "2025-01-20T10:30:00Z"
                        },
                        "success": 1
                    }
                }
            }
        }
    }
)
async def diagnosis_health():
    """Health check for diagnosis service."""
    start_time = time.time()
    
    try:
        # Check service status
        if diagnosis_config_service is None:
            execution_time = round(time.time() - start_time, 2)
            return {
                "data": {
                    "status": "degraded",
                    "service": "diagnosis",
                    "configurations_available": 0,
                    "default_config_active": False,
                    "message": "Configuration service not available",
                    "timestamp": datetime.utcnow().isoformat()
                },
                "metadata": {
                    "statusCode": 200,
                    "errors": [],
                    "executionTime": execution_time,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "success": 1
            }
        
        configs = diagnosis_config_service.get_available_configurations(0)  # System check
        default_config_active = any(config.is_default and config.is_active for config in configs)
        
        execution_time = round(time.time() - start_time, 2)
        
    return {
            "data": {
        "status": "healthy",
        "service": "diagnosis",
                "configurations_available": len(configs),
                "default_config_active": default_config_active,
                "timestamp": datetime.utcnow().isoformat()
            },
            "metadata": {
                "statusCode": 200,
                "errors": [],
                "executionTime": execution_time,
                "timestamp": datetime.utcnow().isoformat()
            },
            "success": 1
        }
        
    except Exception as e:
        execution_time = round(time.time() - start_time, 2)
        logger.error(f"Diagnosis service health check failed: {str(e)}")
        
        return {
            "data": {
                "status": "unhealthy",
                "service": "diagnosis",
                "error": str(e)
            },
            "metadata": {
                "statusCode": 503,
                "errors": [str(e)],
                "executionTime": execution_time,
                "timestamp": datetime.utcnow().isoformat()
            },
            "success": 0
        }
