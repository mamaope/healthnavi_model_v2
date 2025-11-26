"""
Authentication router for HealthNavi AI CDSS.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
import time
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt
import os
import secrets
import string
from urllib.parse import urlencode

from healthnavi.core.database import get_db
from healthnavi.core.config import get_config
from healthnavi.core.response_utils import create_success_response, create_error_response, ResponseTimer
from healthnavi.models.user import User
from healthnavi.schemas import UserCreate, UserResponse, UserUpdate, Token, LoginRequest, StandardResponse, SuccessResponse, EmailVerificationRequest, ResendVerificationRequest, ForgotPasswordRequest, ResetPasswordRequest

# Import email service with error handling
try:
    from healthnavi.services.email_service import email_service
except ImportError as e:
    logger.warning(f"Email service not available: {e}")
    email_service = None

config = get_config()
logger = logging.getLogger(__name__)

# Security configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

router = APIRouter()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        # Bcrypt has a 72 byte limit, truncate if necessary
        if len(plain_password.encode('utf-8')) > 72:
            plain_password = plain_password[:72]
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Hash a password."""
    # Bcrypt has a 72 byte limit, truncate if necessary
    if len(password.encode('utf-8')) > 72:
        password = password[:72]
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=config.security.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, config.security.secret_key, algorithm=config.security.algorithm)
    return encoded_jwt


def authenticate_user(db: Session, username: str, password: str):
    """Authenticate a user."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def get_user_by_email(db: Session, email: str):
    """Get user by email."""
    return db.query(User).filter(User.email == email).first()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, config.security.secret_key, algorithms=[config.security.algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    
    return user


def get_current_user_safe(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Get current authenticated user with safe error handling."""
    try:
        payload = jwt.decode(token, config.security.secret_key, algorithms=[config.security.algorithm])
        username: str = payload.get("sub")
        if username is None:
            return None
    except jwt.JWTError:
        return None
    
    user = db.query(User).filter(User.username == username).first()
    return user


def get_token_safe(request: Request) -> Optional[str]:
    """Safely extract token from request headers."""
    try:
        authorization: str = request.headers.get("Authorization")
        if not authorization:
            return None
        
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return None
            
        return token
    except (ValueError, AttributeError):
        return None


def get_current_user_safe_v2(request: Request, db: Session = Depends(get_db)):
    """Get current authenticated user with safe error handling for missing tokens."""
    token = get_token_safe(request)
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, config.security.secret_key, algorithms=[config.security.algorithm])
        username: str = payload.get("sub")
        if username is None:
            return None
    except jwt.JWTError:
        return None
    
    user = db.query(User).filter(User.username == username).first()
    return user


def require_admin_role(current_user: User = Depends(get_current_user)):
    """Require admin or super_admin role."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_super_admin_role(current_user: User = Depends(get_current_user)):
    """Require super_admin role."""
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return current_user


def require_user_role(current_user: User = Depends(get_current_user)):
    """Require any authenticated user role."""
    return current_user


@router.post("/register", response_model=StandardResponse, status_code=201)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    with ResponseTimer() as timer:
        try:
            # Debug logging
            logger.info(f"Registration attempt - Email: {user.email}, Username: {user.username}, First: {user.first_name}, Last: {user.last_name}, Role: {user.role}, Password length: {len(user.password) if user.password else 0}")
            # Validate that we have either username or first_name+last_name
            if not user.username and not (user.first_name and user.last_name):
                return create_error_response(
                    message="Either username or both first_name and last_name are required",
                    status_code=400,
                    execution_time=timer.get_execution_time()
                )
            
            # Username and full_name are now generated in the schema's model_post_init method
            
            # Check if email already exists
            if get_user_by_email(db, user.email):
                return create_error_response(
                    message="Email already registered",
                    status_code=400,
                    execution_time=timer.get_execution_time()
                )
            
            # Validate role and convert to lowercase
            valid_roles = ["user", "admin", "super_admin"]
            user_role = user.role.lower() if user.role else "user"
            if user_role not in valid_roles:
                return create_error_response(
                    message=f"Invalid role. Must be one of: {valid_roles}",
                    status_code=400,
                    execution_time=timer.get_execution_time()
                )
            
            hashed_password = get_password_hash(user.password)
            
            # Generate email verification token
            if email_service:
                verification_token = email_service.generate_verification_token()
            else:
                # Fallback: generate a simple token if email service is not available
                import secrets
                import string
                alphabet = string.ascii_letters + string.digits
                verification_token = ''.join(secrets.choice(alphabet) for _ in range(32))
            
            new_user = User(
                username=user.username,
                full_name=user.full_name,
                email=user.email,
                hashed_password=hashed_password,
                is_active=True,
                is_email_verified=True,  # Auto-verify users since email service is not configured
                email_verification_token=verification_token,
                role=user_role,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )
            
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            # Send verification email
            email_sent = False
            if email_service:
                email_sent = email_service.send_verification_email(
                    email=user.email,
                    username=user.full_name,
                    verification_token=verification_token
                )
            
            user_data = UserResponse(
                id=new_user.id,
                username=new_user.username,
                full_name=new_user.full_name,
                email=new_user.email,
                role=new_user.role,
                is_active=new_user.is_active,
                is_email_verified=new_user.is_email_verified,
                created_at=new_user.created_at_str,
                updated_at=new_user.updated_at_str
            )
            
            # Prepare response message
            if email_sent:
                message = "User registered successfully. Please check your email to verify your account."
            else:
                message = "User registered successfully. Please contact support for email verification."
            
            return create_success_response(
                data=user_data,
                status_code=201,
                execution_time=timer.get_execution_time()
            )
            
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            # Sanitize error message for security
            error_message = "Registration failed"
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                error_message = "Email or username already exists"
            elif "email" in str(e).lower() and "validation" in str(e).lower():
                error_message = "Invalid email format"
            elif "password" in str(e).lower():
                error_message = "Password requirements not met"
            elif "email_service" in str(e).lower() or "smtp" in str(e).lower():
                error_message = "Email service temporarily unavailable"
            
            return create_error_response(
                message=error_message,
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.post("/login", response_model=StandardResponse)
def login_for_access_token(login_data: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password."""
    with ResponseTimer() as timer:
        try:
            # Find user by email
            user = get_user_by_email(db, login_data.email)
            if not user:
                return create_error_response(
                    message="Incorrect email or password",
                    status_code=401,
                    execution_time=timer.get_execution_time()
                )
            
            # Verify password (skip for OAuth users who don't have passwords)
            if user.hashed_password:
                if not verify_password(login_data.password, user.hashed_password):
                    return create_error_response(
                        message="Incorrect email or password",
                        status_code=401,
                        execution_time=timer.get_execution_time()
                    )
            else:
                # User registered via OAuth, cannot login with password
                return create_error_response(
                    message="This account was created with Google. Please use Google Sign-In.",
                    status_code=401,
                    execution_time=timer.get_execution_time()
                )
            
            # Check if user is active
            if not user.is_active:
                return create_error_response(
                    message="Account is deactivated",
                    status_code=401,
                    execution_time=timer.get_execution_time()
                )
            
            # Email verification check removed
            # if not user.is_email_verified:
            #     return create_error_response(
            #         message="Please verify your email address before logging in",
            #         status_code=401,
            #         execution_time=timer.get_execution_time()
            #     )
            
            access_token_expires = timedelta(minutes=config.security.access_token_expire_minutes)
            access_token = create_access_token(
                data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
            )
            
            # Create user profile data
            user_profile = UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                is_active=user.is_active,
                is_email_verified=user.is_email_verified,
                created_at=user.created_at_str,
                updated_at=user.updated_at_str
            )
            
            # Create response data with token and profile
            response_data = {
                "access_token": access_token,
                "token_type": "bearer",
                "user": user_profile
            }
            
            return create_success_response(
                data=response_data,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
            
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            # Sanitize error message for security
            error_message = "Login failed"
            if "password" in str(e).lower():
                error_message = "Authentication failed"
            elif "email" in str(e).lower():
                error_message = "Authentication failed"
            
            return create_error_response(
                message=error_message,
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/verify-email", response_model=StandardResponse)
def verify_email(token: str, db: Session = Depends(get_db)):
    """Verify user email with verification token.
    
    This endpoint handles email verification via GET request (for email links).
    Users click the verification link in their email to verify their account.
    """
    with ResponseTimer() as timer:
        try:
            # Find user by verification token
            user = db.query(User).filter(User.email_verification_token == token).first()
            if not user:
                return create_error_response(
                    message="Invalid or expired verification token",
                    status_code=400,
                    execution_time=timer.get_execution_time()
                )
            
            # Check if already verified
            if user.is_email_verified:
                return create_error_response(
                    message="Email already verified",
                    status_code=400,
                    execution_time=timer.get_execution_time()
                )
            
            # Verify email
            user.is_email_verified = True
            user.email_verification_token = None  # Clear the token
            user.updated_at = datetime.utcnow().isoformat()
            db.commit()
            
            return create_success_response(
                data={"message": "Email verified successfully"},
                status_code=200,
                execution_time=timer.get_execution_time()
            )
            
        except Exception as e:
            logger.error(f"Email verification error: {str(e)}")
            # Sanitize error message for security
            error_message = "Email verification failed"
            if "database" in str(e).lower() or "connection" in str(e).lower():
                error_message = "Service temporarily unavailable"
            elif "email" in str(e).lower():
                error_message = "Email verification failed"
            
            return create_error_response(
                message=error_message,
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.post("/resend-verification", response_model=StandardResponse)
def resend_verification_email(resend_data: ResendVerificationRequest, db: Session = Depends(get_db)):
    """Resend email verification."""
    with ResponseTimer() as timer:
        try:
            # Find user by email
            user = get_user_by_email(db, resend_data.email)
            if not user:
                return create_error_response(
                    message="Email not found",
                    status_code=404,
                    execution_time=timer.get_execution_time()
                )
            
            # Check if already verified
            if user.is_email_verified:
                return create_error_response(
                    message="Email already verified",
                    status_code=400,
                    execution_time=timer.get_execution_time()
                )
            
            # Generate new verification token
            if email_service:
                verification_token = email_service.generate_verification_token()
            else:
                # Fallback: generate a simple token if email service is not available
                import secrets
                import string
                alphabet = string.ascii_letters + string.digits
                verification_token = ''.join(secrets.choice(alphabet) for _ in range(32))
            
            user.email_verification_token = verification_token
            user.updated_at = datetime.utcnow().isoformat()
            db.commit()
            
            # Send verification email
            email_sent = False
            if email_service:
                email_sent = email_service.send_verification_email(
                    email=user.email,
                    username=user.full_name,
                    verification_token=verification_token
                )
            
            if email_sent:
                message = "Verification email sent successfully"
            else:
                message = "Failed to send verification email. Please contact support."
            
            return create_success_response(
                data={"message": message},
                status_code=200,
                execution_time=timer.get_execution_time()
            )
            
        except Exception as e:
            logger.error(f"Resend verification error: {str(e)}")
            # Sanitize error message for security
            error_message = "Failed to resend verification email"
            if "database" in str(e).lower() or "connection" in str(e).lower():
                error_message = "Service temporarily unavailable"
            
            return create_error_response(
                message=error_message,
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.post("/manual-verify", response_model=StandardResponse)
def manual_verify_email(email: str, db: Session = Depends(get_db)):
    """Manually verify email for development/testing purposes."""
    with ResponseTimer() as timer:
        try:
            # Find user by email
            user = get_user_by_email(db, email)
            if not user:
                return create_error_response(
                    message="Email not found",
                    status_code=404,
                    execution_time=timer.get_execution_time()
                )
            
            # Check if already verified
            if user.is_email_verified:
                return create_error_response(
                    message="Email already verified",
                    status_code=400,
                    execution_time=timer.get_execution_time()
                )
            
            # Manually verify email
            user.is_email_verified = True
            user.email_verification_token = None
            user.updated_at = datetime.utcnow().isoformat()
            db.commit()
            
            return create_success_response(
                data={"message": f"Email {email} manually verified for development"},
                status_code=200,
                execution_time=timer.get_execution_time()
            )
            
        except Exception as e:
            logger.error(f"Manual verification error: {str(e)}")
            return create_error_response(
                message="Manual verification failed",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/me", response_model=StandardResponse)
def get_current_user_me(
    current_user: User = Depends(get_current_user_safe_v2)
):
    """
    Get current authenticated user profile.
    Alias for /profile endpoint for compatibility.
    """
    return get_user_profile(current_user=current_user)


@router.get("/me", response_model=StandardResponse)
def get_current_user_me(
    current_user: User = Depends(get_current_user_safe_v2)
):
    """
    Get current authenticated user profile.
    Alias for /profile endpoint for compatibility.
    """
    return get_user_profile(current_user=current_user)


@router.get("/profile", response_model=StandardResponse)
def get_user_profile(
    current_user: User = Depends(get_current_user_safe_v2)
):
    """Get current user's profile information."""
    with ResponseTimer() as timer:
        try:
            # Check if user is authenticated
            if not current_user:
                return create_error_response(
                    message="Authentication required",
                    status_code=401,
                    execution_time=timer.get_execution_time()
                )
            
            # Check if user is active
            if not current_user.is_active:
                return create_error_response(
                    message="Account is deactivated",
                    status_code=403,
                    execution_time=timer.get_execution_time()
                )
            
            # Create user profile data with validation
            try:
                user_profile = UserResponse(
                    id=current_user.id,
                    username=current_user.username,
                    email=current_user.email,
                    full_name=current_user.full_name,
                    role=current_user.role,
                    is_active=current_user.is_active,
                    is_email_verified=current_user.is_email_verified,
                    created_at=current_user.created_at_str,
                    updated_at=current_user.updated_at_str
                )
            except Exception as validation_error:
                logger.error(f"Profile data validation error: {str(validation_error)}")
                return create_error_response(
                    message="Profile data validation failed",
                    status_code=500,
                    execution_time=timer.get_execution_time()
                )
            
            return create_success_response(
                data=user_profile,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
            
        except Exception as e:
            logger.error(f"Profile retrieval error: {str(e)}")
            # Sanitize error message for security
            error_message = "Failed to retrieve profile"
            status_code = 500
            
            if "database" in str(e).lower() or "connection" in str(e).lower():
                error_message = "Service temporarily unavailable"
                status_code = 503
            elif "authentication" in str(e).lower() or "token" in str(e).lower():
                error_message = "Authentication failed"
                status_code = 401
            elif "permission" in str(e).lower() or "forbidden" in str(e).lower():
                error_message = "Access denied"
                status_code = 403
            elif "not found" in str(e).lower():
                error_message = "User not found"
                status_code = 404
            
            return create_error_response(
                message=error_message,
                status_code=status_code,
                execution_time=timer.get_execution_time()
            )


@router.get("/users", response_model=StandardResponse)
def get_all_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all users (admin only)."""
    with ResponseTimer() as timer:
        try:
            if current_user.role not in ["admin", "super_admin"]:
                return create_error_response(
                    message="Admin access required",
                    status_code=403,
                    execution_time=timer.get_execution_time()
                )
            
            users = db.query(User).offset(skip).limit(limit).all()
            user_responses = [
                UserResponse(
                    id=user.id,
                    username=user.username,
                    full_name=user.full_name,
                    email=user.email,
                    role=user.role,
                    is_active=user.is_active,
                    is_email_verified=user.is_email_verified,
                    created_at=user.created_at_str,
                    updated_at=user.updated_at_str
                ) for user in users
            ]
            
            return create_success_response(
                data=user_responses,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
            
        except Exception as e:
            logger.error(f"Get users error: {str(e)}")
            # Sanitize error message for security
            error_message = "Failed to retrieve users"
            if "database" in str(e).lower() or "connection" in str(e).lower():
                error_message = "Service temporarily unavailable"
            
            return create_error_response(
                message=error_message,
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.put("/users/{user_id}", response_model=StandardResponse)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user (admin only)."""
    with ResponseTimer() as timer:
        try:
            if current_user.role not in ["admin", "super_admin"]:
                return create_error_response(
                    message="Admin access required",
                    status_code=403,
                    execution_time=timer.get_execution_time()
                )
            
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return create_error_response(
                    message="User not found",
                    status_code=404,
                    execution_time=timer.get_execution_time()
                )
            
            # Validate role if provided and convert to lowercase
            if user_update.role:
                user_update.role = user_update.role.lower()
                if user_update.role not in ["user", "admin", "super_admin"]:
                    return create_error_response(
                        message="Invalid role",
                        status_code=400,
                        execution_time=timer.get_execution_time()
                    )
            
            # Update fields
            update_data = user_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(user, field, value)
            
            user.updated_at = datetime.utcnow().isoformat()
            db.commit()
            db.refresh(user)
            
            user_response = UserResponse(
                id=user.id,
                username=user.username,
                full_name=user.full_name,
                email=user.email,
                role=user.role,
                is_active=user.is_active,
                is_email_verified=user.is_email_verified,
                created_at=user.created_at_str,
                updated_at=user.updated_at_str
            )
            
            return create_success_response(
                data=user_response,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
            
        except Exception as e:
            logger.error(f"Update user error: {str(e)}")
            # Sanitize error message for security
            error_message = "Failed to update user"
            if "database" in str(e).lower() or "connection" in str(e).lower():
                error_message = "Service temporarily unavailable"
            elif "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                error_message = "User data conflict"
            
            return create_error_response(
                message=error_message,
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.post("/forgot-password", response_model=StandardResponse)
def forgot_password(forgot_data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Request password reset email."""
    with ResponseTimer() as timer:
        try:
            # Find user by email
            user = get_user_by_email(db, forgot_data.email)
            if not user:
                # Don't reveal if email exists for security
                return create_success_response(
                    data={"message": "If the email exists, a password reset link has been sent."},
                    status_code=200,
                    execution_time=timer.get_execution_time()
                )
            
            # Check if user is active
            if not user.is_active:
                return create_error_response(
                    message="Account is deactivated",
                    status_code=403,
                    execution_time=timer.get_execution_time()
                )
            
            # Generate password reset token
            if email_service:
                reset_token = email_service.generate_verification_token()
            else:
                # Fallback: generate a simple token if email service is not available
                import secrets
                import string
                alphabet = string.ascii_letters + string.digits
                reset_token = ''.join(secrets.choice(alphabet) for _ in range(32))
            
            # Set token and expiration (1 hour from now)
            user.password_reset_token = reset_token
            user.password_reset_expires = (datetime.utcnow() + timedelta(hours=1)).isoformat()
            user.updated_at = datetime.utcnow().isoformat()
            db.commit()
            
            # Send password reset email
            email_sent = False
            if email_service:
                email_sent = email_service.send_password_reset_email(
                    email=user.email,
                    username=user.full_name or user.username,
                    reset_token=reset_token
                )
            
            if email_sent:
                message = "If the email exists, a password reset link has been sent."
            else:
                message = "Password reset requested. Please contact support if you don't receive an email."
            
            # Always return success message (don't reveal if email exists)
            return create_success_response(
                data={"message": message},
                status_code=200,
                execution_time=timer.get_execution_time()
            )
            
        except Exception as e:
            logger.error(f"Forgot password error: {str(e)}")
            return create_error_response(
                message="Failed to process password reset request",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.post("/reset-password", response_model=StandardResponse)
def reset_password(reset_data: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password with token."""
    with ResponseTimer() as timer:
        try:
            # Find user by reset token
            user = db.query(User).filter(User.password_reset_token == reset_data.token).first()
            if not user:
                return create_error_response(
                    message="Invalid or expired reset token",
                    status_code=400,
                    execution_time=timer.get_execution_time()
                )
            
            # Check if token is expired
            if user.password_reset_expires:
                try:
                    expires_at = datetime.fromisoformat(user.password_reset_expires.replace('Z', '+00:00'))
                    if datetime.utcnow() > expires_at:
                        # Clear expired token
                        user.password_reset_token = None
                        user.password_reset_expires = None
                        user.updated_at = datetime.utcnow().isoformat()
                        db.commit()
                        return create_error_response(
                            message="Reset token has expired. Please request a new one.",
                            status_code=400,
                            execution_time=timer.get_execution_time()
                        )
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Error parsing expiration date: {e}")
                    # If we can't parse the date, treat as expired for security
                    user.password_reset_token = None
                    user.password_reset_expires = None
                    user.updated_at = datetime.utcnow().isoformat()
                    db.commit()
                    return create_error_response(
                        message="Invalid reset token",
                        status_code=400,
                        execution_time=timer.get_execution_time()
                    )
            
            # Check if user is active
            if not user.is_active:
                return create_error_response(
                    message="Account is deactivated",
                    status_code=403,
                    execution_time=timer.get_execution_time()
                )
            
            # Hash new password
            hashed_password = get_password_hash(reset_data.new_password)
            
            # Update password and clear reset token
            user.hashed_password = hashed_password
            user.password_reset_token = None
            user.password_reset_expires = None
            user.updated_at = datetime.utcnow().isoformat()
            db.commit()
            
            return create_success_response(
                data={"message": "Password reset successfully. You can now login with your new password."},
                status_code=200,
                execution_time=timer.get_execution_time()
            )
            
        except Exception as e:
            logger.error(f"Reset password error: {str(e)}")
            return create_error_response(
                message="Failed to reset password",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/google/login")
def google_login():
    """
    Initiate Google OAuth login flow.
    Redirects user to Google's OAuth consent screen.
    """
    with ResponseTimer() as timer:
        try:
            if not config.security.google_client_id or not config.security.google_client_secret:
                return create_error_response(
                    message="Google OAuth is not configured",
                    status_code=503,
                    execution_time=timer.get_execution_time()
                )
            
            # Generate state token for CSRF protection
            state = secrets.token_urlsafe(32)
            
            # Build Google OAuth URL - redirect to backend callback endpoint
            backend_url = os.getenv('BACKEND_URL', 'http://localhost:8050')
            redirect_uri = config.security.google_redirect_uri or f"{backend_url}/api/v2/auth/google/callback"
            
            google_oauth_url = (
                "https://accounts.google.com/o/oauth2/v2/auth?"
                f"client_id={config.security.google_client_id}&"
                f"redirect_uri={redirect_uri}&"
                "response_type=code&"
                "scope=openid email profile&"
                "prompt=select_account&"
                "access_type=offline&"
                "include_granted_scopes=true&"
                f"state={state}"
            )
            
            # Store state in response (in production, use secure session storage)
            response = RedirectResponse(url=google_oauth_url)
            response.set_cookie(key="oauth_state", value=state, httponly=True, samesite="lax", max_age=600)
            
            return response
            
        except Exception as e:
            logger.error(f"Google login initiation error: {str(e)}")
            return create_error_response(
                message="Failed to initiate Google login",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/google/callback")
async def google_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Handle Google OAuth callback.
    Exchanges authorization code for user info and creates/authenticates user.
    """
    with ResponseTimer() as timer:
        try:
            if error:
                logger.error(f"Google OAuth error: {error}")
                redirect_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/auth/google/error?error={error}"
                return RedirectResponse(url=redirect_url)
            
            if not code or not state:
                redirect_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/auth/google/error?error=missing_parameters"
                return RedirectResponse(url=redirect_url)
            
            # Verify state token (CSRF protection)
            cookie_state = request.cookies.get("oauth_state")
            if not cookie_state or cookie_state != state:
                logger.warning("OAuth state mismatch - possible CSRF attack")
                redirect_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/auth/google/error?error=invalid_state"
                return RedirectResponse(url=redirect_url)
            
            # Exchange code for token
            try:
                import httpx
                
                backend_url = os.getenv('BACKEND_URL', 'http://localhost:8050')
                redirect_uri = config.security.google_redirect_uri or f"{backend_url}/api/v2/auth/google/callback"
                
                token_response = httpx.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "code": code,
                        "client_id": config.security.google_client_id,
                        "client_secret": config.security.google_client_secret,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code",
                    },
                    timeout=10.0
                )
                
                if token_response.status_code != 200:
                    logger.error(f"Token exchange failed: {token_response.text}")
                    redirect_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/auth/google/error?error=token_exchange_failed"
                    return RedirectResponse(url=redirect_url)
                
                token_data = token_response.json()
                access_token = token_data.get("id_token") or token_data.get("access_token")
                
                if not access_token:
                    logger.error("No access token in response")
                    redirect_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/auth/google/error?error=no_token"
                    return RedirectResponse(url=redirect_url)
                
                # Get user info from Google
                userinfo_response = httpx.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {token_data.get('access_token')}"},
                    timeout=10.0
                )
                
                if userinfo_response.status_code != 200:
                    logger.error(f"User info fetch failed: {userinfo_response.text}")
                    redirect_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/auth/google/error?error=userinfo_failed"
                    return RedirectResponse(url=redirect_url)
                
                google_user_data = userinfo_response.json()
                google_id = google_user_data.get("id")
                email = google_user_data.get("email")
                name = google_user_data.get("name", "")
                given_name = google_user_data.get("given_name", "")
                family_name = google_user_data.get("family_name", "")
                picture = google_user_data.get("picture")
                
                if not google_id or not email:
                    logger.error("Missing required Google user data")
                    redirect_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/auth/google/error?error=missing_user_data"
                    return RedirectResponse(url=redirect_url)
                
                # Check if user exists by Google ID
                user = db.query(User).filter(User.google_id == google_id).first()
                
                if not user:
                    # Check if user exists by email (link accounts)
                    user = db.query(User).filter(User.email == email).first()
                    
                    if user:
                        # Link Google account to existing user
                        user.google_id = google_id
                        if not user.full_name and name:
                            user.full_name = name
                        user.is_email_verified = True  # Google emails are verified
                        user.updated_at = datetime.utcnow().isoformat()
                        db.commit()
                        db.refresh(user)
                        logger.info(f"Linked Google account to existing user {user.id}")
                    else:
                        # Create new user
                        # Generate username from email
                        username_base = email.split("@")[0]
                        username = username_base
                        counter = 1
                        while db.query(User).filter(User.username == username).first():
                            username = f"{username_base}{counter}"
                            counter += 1
                        
                        new_user = User(
                            username=username,
                            full_name=name or f"{given_name} {family_name}".strip() or username,
                            email=email,
                            hashed_password=None,  # OAuth users don't have passwords
                            google_id=google_id,
                            is_active=True,
                            is_email_verified=True,  # Google emails are verified
                            role="user",
                            created_at=datetime.utcnow().isoformat(),
                            updated_at=datetime.utcnow().isoformat()
                        )
                        
                        db.add(new_user)
                        db.commit()
                        db.refresh(new_user)
                        user = new_user
                        logger.info(f"Created new user from Google OAuth: {user.id}")
                
                # Check if user is active
                if not user.is_active:
                    redirect_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/auth/google/error?error=account_deactivated"
                    return RedirectResponse(url=redirect_url)
                
                # Create JWT token
                access_token_expires = timedelta(minutes=config.security.access_token_expire_minutes)
                jwt_token = create_access_token(
                    data={"sub": user.username, "role": user.role},
                    expires_delta=access_token_expires
                )
                
                # Redirect to frontend with token
                # Try to get frontend URL from environment, with fallbacks
                frontend_url = os.getenv('FRONTEND_URL')
                if not frontend_url:
                    # Default to port 3000 for Docker, or 5173 for dev
                    frontend_url = 'http://localhost:3000'
                # Ensure no trailing slash
                frontend_url = frontend_url.rstrip('/')
                redirect_url = f"{frontend_url}/auth/google/success?token={jwt_token}"
                logger.info(f"OAuth success - Redirecting to frontend: {redirect_url}")
                
                response = RedirectResponse(url=redirect_url)
                response.delete_cookie(key="oauth_state")
                
                return response
                
            except Exception as e:
                logger.error(f"Error processing Google OAuth callback: {str(e)}")
                redirect_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/auth/google/error?error=processing_failed"
                return RedirectResponse(url=redirect_url)
            
        except Exception as e:
            logger.error(f"Google callback error: {str(e)}")
            redirect_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/auth/google/error?error=callback_failed"
            return RedirectResponse(url=redirect_url)
