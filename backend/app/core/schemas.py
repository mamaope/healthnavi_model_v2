"""
Enhanced API schemas for HealthNavi AI CDSS.

This module provides secure API schemas with comprehensive validation,
data sanitization, and proper error handling following medical software standards.
"""

from pydantic import BaseModel, validator, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)


class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    
    class Config:
        # Prevent arbitrary types
        arbitrary_types_allowed = False
        # Validate assignment
        validate_assignment = True
        # Use enum values
        use_enum_values = True
        # Extra fields not allowed
        extra = "forbid"


class DiagnosisInput(BaseSchema):
    """Enhanced diagnosis input schema with validation."""
    
    patient_data: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Patient data for diagnosis (max 10KB)"
    )
    chat_history: Optional[str] = Field(
        default="",
        max_length=50000,
        description="Previous conversation history (max 50KB)"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for tracking diagnosis progress"
    )
    
    @validator('patient_data')
    def validate_patient_data(cls, v):
        """Validate and sanitize patient data."""
        if not v or not v.strip():
            raise ValueError('Patient data cannot be empty')
        
        # Check for potentially malicious content
        dangerous_patterns = [
            r'<script.*?>.*?</script>',  # Script tags
            r'javascript:',  # JavaScript protocol
            r'data:text/html',  # Data URLs
            r'vbscript:',  # VBScript
            r'<iframe.*?>',  # Iframe tags
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError('Invalid content detected in patient data')
        
        # Remove excessive whitespace
        sanitized = ' '.join(v.split())
        
        return sanitized
    
    @validator('chat_history')
    def validate_chat_history(cls, v):
        """Validate chat history."""
        if not v:
            return ""
        
        # Basic sanitization
        sanitized = ' '.join(v.split())
        
        # Check for script injection
        if re.search(r'<script.*?>', sanitized, re.IGNORECASE):
            raise ValueError('Invalid content detected in chat history')
        
        return sanitized
    
    @validator('session_id')
    def validate_session_id(cls, v):
        """Validate session ID format."""
        if v is None:
            return v
        
        # UUID format validation
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if not re.match(uuid_pattern, v, re.IGNORECASE):
            raise ValueError('Invalid session ID format')
        
        return v


class DiagnosisResponse(BaseSchema):
    """Enhanced diagnosis response schema."""
    
    model_response: str = Field(
        ...,
        description="AI model response for diagnosis"
    )
    diagnosis_complete: bool = Field(
        ...,
        description="Whether the diagnosis is complete"
    )
    updated_chat_history: str = Field(
        ...,
        description="Updated conversation history"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for tracking"
    )
    sources_used: Optional[List[str]] = Field(
        default=None,
        description="List of sources used in the response"
    )
    processing_time_ms: Optional[int] = Field(
        default=None,
        description="Processing time in milliseconds"
    )
    confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score of the diagnosis (0-1)"
    )


class UserCreate(BaseSchema):
    """Enhanced user creation schema."""
    
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Username (3-50 characters, alphanumeric only)"
    )
    full_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Full name (max 100 characters)"
    )
    email: str = Field(
        ...,
        max_length=255,
        description="Email address"
    )
    password: str = Field(
        ...,
        min_length=12,
        max_length=128,
        description="Password (12-128 characters)"
    )
    
    @validator('username')
    def validate_username(cls, v):
        """Validate username format."""
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username must contain only alphanumeric characters and underscores')
        
        # Check for reserved usernames
        reserved_usernames = ['admin', 'root', 'system', 'api', 'test', 'user', 'guest']
        if v.lower() in reserved_usernames:
            raise ValueError('Username is reserved')
        
        return v.lower()
    
    @validator('email')
    def validate_email(cls, v):
        """Validate email format."""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format')
        
        return v.lower()
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength."""
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters')
        
        if len(v) > 128:
            raise ValueError('Password must be no more than 128 characters')
        
        # Check for required character types
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', v):
            raise ValueError('Password must contain at least one special character')
        
        # Check for common patterns
        common_patterns = ['password', '123456', 'qwerty', 'admin', 'user']
        if any(pattern in v.lower() for pattern in common_patterns):
            raise ValueError('Password contains common patterns')
        
        return v
    
    @validator('full_name')
    def validate_full_name(cls, v):
        """Validate full name."""
        if v is None:
            return v
        
        if len(v.strip()) == 0:
            return None
        
        # Check for potentially malicious content
        if re.search(r'<[^>]*>', v):
            raise ValueError('Full name cannot contain HTML tags')
        
        return v.strip()


class UserResponse(BaseSchema):
    """User response schema (without sensitive data)."""
    
    id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    full_name: Optional[str] = Field(default=None, description="Full name")
    email: str = Field(..., description="Email address")
    is_active: bool = Field(..., description="Whether user is active")
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_login_at: Optional[datetime] = Field(default=None, description="Last login timestamp")


class LoginRequest(BaseSchema):
    """Login request schema."""
    
    username: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Username"
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Password"
    )
    
    @validator('username')
    def validate_username(cls, v):
        """Validate username format."""
        if not v or not v.strip():
            raise ValueError('Username cannot be empty')
        
        return v.strip().lower()
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password format."""
        if not v:
            raise ValueError('Password cannot be empty')
        
        return v


class TokenResponse(BaseSchema):
    """Token response schema."""
    
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class RefreshTokenRequest(BaseSchema):
    """Refresh token request schema."""
    
    refresh_token: str = Field(..., description="Refresh token")


class PasswordChangeRequest(BaseSchema):
    """Password change request schema."""
    
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., description="New password")
    
    @validator('new_password')
    def validate_new_password(cls, v):
        """Validate new password strength."""
        if len(v) < 12:
            raise ValueError('New password must be at least 12 characters')
        
        if len(v) > 128:
            raise ValueError('New password must be no more than 128 characters')
        
        # Check for required character types
        if not re.search(r'[A-Z]', v):
            raise ValueError('New password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', v):
            raise ValueError('New password must contain at least one lowercase letter')
        
        if not re.search(r'\d', v):
            raise ValueError('New password must contain at least one digit')
        
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', v):
            raise ValueError('New password must contain at least one special character')
        
        return v


class ErrorResponse(BaseSchema):
    """Standard error response schema."""
    
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(default=None, description="Error code")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class HealthCheckResponse(BaseSchema):
    """Health check response schema."""
    
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Environment")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")
    services: Dict[str, str] = Field(..., description="External services status")


class AuditLogResponse(BaseSchema):
    """Audit log response schema."""
    
    id: int = Field(..., description="Audit log ID")
    user_id: Optional[int] = Field(default=None, description="User ID")
    username: Optional[str] = Field(default=None, description="Username")
    action: str = Field(..., description="Action performed")
    resource_type: Optional[str] = Field(default=None, description="Resource type")
    resource_id: Optional[str] = Field(default=None, description="Resource ID")
    ip_address: Optional[str] = Field(default=None, description="IP address")
    success: bool = Field(..., description="Whether action was successful")
    created_at: datetime = Field(..., description="Timestamp")


class SecurityEventResponse(BaseSchema):
    """Security event response schema."""
    
    id: int = Field(..., description="Security event ID")
    event_type: str = Field(..., description="Event type")
    severity: str = Field(..., description="Event severity")
    user_id: Optional[int] = Field(default=None, description="User ID")
    ip_address: Optional[str] = Field(default=None, description="IP address")
    details: str = Field(..., description="Event details")
    resolved: bool = Field(..., description="Whether event is resolved")
    created_at: datetime = Field(..., description="Timestamp")


# Utility functions for schema validation
def validate_input_length(text: str, max_length: int, field_name: str) -> str:
    """Validate input text length."""
    if len(text) > max_length:
        raise ValueError(f'{field_name} exceeds maximum length of {max_length} characters')
    return text


def sanitize_text(text: str) -> str:
    """Basic text sanitization."""
    import html
    
    # HTML escape
    sanitized = html.escape(text)
    
    # Remove excessive whitespace
    sanitized = ' '.join(sanitized.split())
    
    return sanitized


def validate_medical_data(data: str) -> str:
    """Validate medical data input."""
    # Check for potentially sensitive patterns
    sensitive_patterns = [
        r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
        r'\b\d{4}\s\d{4}\s\d{4}\s\d{4}\b',  # Credit card
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
    ]
    
    for pattern in sensitive_patterns:
        if re.search(pattern, data):
            logger.warning("Potential sensitive data detected in medical input")
            # In production, you might want to raise an error or redact the data
    
    return sanitize_text(data)
