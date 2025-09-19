"""
Enhanced authentication system for HealthNavi AI CDSS.

This module provides secure authentication with proper session management,
rate limiting, and audit logging following medical software security standards.
"""

import os
import time
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator

from app.core.config import get_config
from app.core.security import PasswordValidator, SecureLogger, InputValidator
from app.core.database import get_db
from app.core.models import User as UserModel

config = get_config()
logger = logging.getLogger(__name__)

# Password hashing with stronger settings
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Increased from default 10 for better security
)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{config.application.api_root_path}/auth/login",
    auto_error=False
)


class LoginAttemptTracker:
    """Tracks login attempts for rate limiting."""
    
    def __init__(self):
        self.attempts: Dict[str, Dict[str, Any]] = {}
    
    def record_attempt(self, username: str, success: bool) -> None:
        """Record a login attempt."""
        now = time.time()
        
        if username not in self.attempts:
            self.attempts[username] = {
                'attempts': [],
                'locked_until': None
            }
        
        self.attempts[username]['attempts'].append({
            'timestamp': now,
            'success': success
        })
        
        # Clean old attempts (older than 1 hour)
        cutoff = now - 3600
        self.attempts[username]['attempts'] = [
            attempt for attempt in self.attempts[username]['attempts']
            if attempt['timestamp'] > cutoff
        ]
    
    def is_locked(self, username: str) -> bool:
        """Check if username is locked due to too many failed attempts."""
        if username not in self.attempts:
            return False
        
        user_data = self.attempts[username]
        
        # Check if currently locked
        if user_data['locked_until'] and time.time() < user_data['locked_until']:
            return True
        
        # Check recent failed attempts
        recent_failures = [
            attempt for attempt in user_data['attempts']
            if not attempt['success'] and 
            attempt['timestamp'] > time.time() - (config.security.login_lockout_minutes * 60)
        ]
        
        if len(recent_failures) >= config.security.max_login_attempts:
            # Lock the account
            user_data['locked_until'] = time.time() + (config.security.login_lockout_minutes * 60)
            SecureLogger.log_securely('warning', f'Account locked due to too many failed attempts: {username}')
            return True
        
        return False
    
    def get_lockout_time_remaining(self, username: str) -> Optional[int]:
        """Get remaining lockout time in seconds."""
        if username not in self.attempts:
            return None
        
        user_data = self.attempts[username]
        if user_data['locked_until']:
            remaining = user_data['locked_until'] - time.time()
            return max(0, int(remaining))
        
        return None


# Global login attempt tracker
login_tracker = LoginAttemptTracker()


class TokenData(BaseModel):
    """Token data model."""
    username: Optional[str] = None
    exp: Optional[datetime] = None
    iat: Optional[datetime] = None


class Token(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserCreate(BaseModel):
    """User creation model with validation."""
    username: str
    full_name: Optional[str] = None
    email: str
    password: str
    
    @validator('username')
    def validate_username(cls, v):
        """Validate username."""
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        if len(v) > 50:
            raise ValueError('Username must be no more than 50 characters')
        if not v.isalnum():
            raise ValueError('Username must contain only alphanumeric characters')
        return v.lower()
    
    @validator('email')
    def validate_email(cls, v):
        """Validate email format."""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format')
        return v.lower()
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength."""
        validation_result = PasswordValidator.validate_password(v)
        if not validation_result['is_valid']:
            raise ValueError(f"Password validation failed: {', '.join(validation_result['errors'])}")
        return v


class UserResponse(BaseModel):
    """User response model (without sensitive data)."""
    username: str
    full_name: Optional[str] = None
    email: str
    is_active: bool
    created_at: Optional[datetime] = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)


def get_user_by_username(db: Session, username: str) -> Optional[UserModel]:
    """Get user by username."""
    return db.query(UserModel).filter(UserModel.username == username.lower()).first()


def get_user_by_email(db: Session, email: str) -> Optional[UserModel]:
    """Get user by email."""
    return db.query(UserModel).filter(UserModel.email == email.lower()).first()


def authenticate_user(db: Session, username: str, password: str) -> Optional[UserModel]:
    """Authenticate user with credentials."""
    # Check if account is locked
    if login_tracker.is_locked(username):
        lockout_time = login_tracker.get_lockout_time_remaining(username)
        SecureLogger.log_securely('warning', f'Login attempt on locked account: {username}')
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked due to too many failed attempts. Try again in {lockout_time} seconds."
        )
    
    user = get_user_by_username(db, username)
    if not user:
        login_tracker.record_attempt(username, False)
        SecureLogger.log_securely('warning', f'Login attempt with invalid username: {username}')
        return None
    
    if not verify_password(password, user.hashed_password):
        login_tracker.record_attempt(username, False)
        SecureLogger.log_securely('warning', f'Failed login attempt for user: {username}')
        return None
    
    # Successful login
    login_tracker.record_attempt(username, True)
    SecureLogger.log_securely('info', f'Successful login for user: {username}')
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=config.security.access_token_expire_minutes)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(
        to_encode, 
        config.security.secret_key, 
        algorithm=config.security.algorithm
    )
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=config.security.refresh_token_expire_days)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        config.security.secret_key,
        algorithm=config.security.algorithm
    )
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> TokenData:
    """Verify and decode JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, 
            config.security.secret_key, 
            algorithms=[config.security.algorithm]
        )
        
        # Verify token type
        if payload.get("type") != token_type:
            raise credentials_exception
        
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        
        token_data = TokenData(
            username=username,
            exp=datetime.fromtimestamp(payload.get("exp", 0)),
            iat=datetime.fromtimestamp(payload.get("iat", 0))
        )
        
        return token_data
        
    except JWTError:
        raise credentials_exception


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> UserModel:
    """Get current authenticated user."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_data = verify_token(token, "access")
    user = get_user_by_username(db, token_data.username)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_active_user(
    current_user: UserModel = Depends(get_current_user)
) -> UserModel:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return current_user


def create_user(db: Session, user_data: UserCreate) -> UserModel:
    """Create a new user."""
    # Check if user already exists
    if get_user_by_username(db, user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    if get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    hashed_password = get_password_hash(user_data.password)
    db_user = UserModel(
        username=user_data.username,
        full_name=user_data.full_name,
        email=user_data.email,
        hashed_password=hashed_password,
        is_active=True
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    SecureLogger.log_securely('info', f'New user registered: {user_data.username}')
    return db_user


def refresh_access_token(refresh_token: str, db: Session) -> Token:
    """Refresh access token using refresh token."""
    token_data = verify_token(refresh_token, "refresh")
    user = get_user_by_username(db, token_data.username)
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Create new access token
    access_token_expires = timedelta(minutes=config.security.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )
    
    # Create new refresh token
    new_refresh_token = create_refresh_token(data={"sub": user.username})
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=config.security.access_token_expire_minutes * 60
    )
