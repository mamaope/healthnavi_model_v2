"""
Core schemas module for HealthNavi AI CDSS.

This module contains Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    """User role enumeration."""
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

class UserBase(BaseModel):
    """Base user schema."""
    username: str
    full_name: Optional[str] = None
    email: EmailStr
    role: UserRole = UserRole.USER
    is_active: bool = True

class UserCreate(UserBase):
    """Schema for user creation."""
    password: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v
    
    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters long')
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v

class UserUpdate(BaseModel):
    """Schema for user updates."""
    username: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    """Schema for user responses."""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    """Schema for user login."""
    username: str
    password: str

class Token(BaseModel):
    """Schema for authentication token."""
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Schema for token data."""
    username: Optional[str] = None

class DiagnosisInput(BaseModel):
    """Schema for diagnosis input."""
    patient_data: str
    chat_history: Optional[str] = ""

class DiagnosisResponse(BaseModel):
    """Schema for diagnosis response."""
    model_response: str
    diagnosis_complete: bool
    updated_chat_history: str
    confidence: Optional[float] = None
    suggestions: Optional[List[str]] = None

class HealthCheck(BaseModel):
    """Schema for health check response."""
    status: str
    timestamp: datetime
    version: str
    services: dict

class ErrorResponse(BaseModel):
    """Schema for error responses."""
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = datetime.utcnow()

class PaginatedResponse(BaseModel):
    """Schema for paginated responses."""
    items: List[dict]
    total: int
    page: int
    size: int
    pages: int
