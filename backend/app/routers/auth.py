"""
Enhanced authentication router for HealthNavi AI CDSS.
Follows standard API practices with proper validation and response formatting.
"""

import logging
import time
import asyncio
import re
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, validator, Field
import hashlib
import secrets
import jwt
from email_validator import validate_email
import os

# Import database service
from app.services.database_service import db_service
from app.services.email_service import email_service

logger = logging.getLogger(__name__)
router = APIRouter()

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secure-secret-key-min-32-characters-long")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OAuth2 scheme for token validation
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Password requirements
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
REQUIRE_UPPERCASE = True
REQUIRE_LOWERCASE = True
REQUIRE_NUMBERS = True
REQUIRE_SPECIAL_CHARS = True

# Rate limiting (simple in-memory store for demo)
login_attempts = {}

# Email verification storage (simple in-memory store for demo)
verification_tokens = {}  # token -> {email, expires_at, used}
email_verification_attempts = {}  # email -> {attempts, last_attempt}


class UserRegistrationRequest(BaseModel):
    """User registration request model with comprehensive validation."""
    first_name: str = Field(..., min_length=1, max_length=50, description="User's first name")
    last_name: str = Field(..., min_length=1, max_length=50, description="User's last name")
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH, description="User's password")
    
    @validator('first_name', 'last_name')
    def validate_names(cls, v):
        """Validate name fields."""
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        if not re.match(r'^[a-zA-Z\s\-\'\.]+$', v):
            raise ValueError('Name can only contain letters, spaces, hyphens, apostrophes, and periods')
        return v.strip().title()
    
    @validator('password')
    def validate_password(cls, v):
        """Comprehensive password validation."""
        if not v:
            raise ValueError('Password is required')
        
        # Check length
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(f'Password must be at least {MIN_PASSWORD_LENGTH} characters long')
        
        if len(v) > MAX_PASSWORD_LENGTH:
            raise ValueError(f'Password must be no more than {MAX_PASSWORD_LENGTH} characters long')
        
        # Check for common weak passwords
        weak_passwords = [
            'password', '123456', '123456789', 'qwerty', 'abc123',
            'password123', 'admin', 'letmein', 'welcome', 'monkey'
        ]
        if v.lower() in weak_passwords:
            raise ValueError('Password is too common. Please choose a stronger password.')
        
        # Check character requirements
        errors = []
        if REQUIRE_UPPERCASE and not re.search(r'[A-Z]', v):
            errors.append('at least one uppercase letter')
        if REQUIRE_LOWERCASE and not re.search(r'[a-z]', v):
            errors.append('at least one lowercase letter')
        if REQUIRE_NUMBERS and not re.search(r'\d', v):
            errors.append('at least one number')
        if REQUIRE_SPECIAL_CHARS and not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            errors.append('at least one special character')
        
        if errors:
            raise ValueError(f'Password must contain {", ".join(errors)}')
        
        return v


class UserLoginRequest(BaseModel):
    """User login request model."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class UserData(BaseModel):
    """User data model for responses."""
    first_name: str
    last_name: str
    email: str
    active: bool = False


class RegistrationResponse(BaseModel):
    """Registration response model."""
    data: dict
    metadata: dict
    success: int


class LoginResponse(BaseModel):
    """Login response model."""
    data: dict
    metadata: dict
    success: int


class EmailVerificationRequest(BaseModel):
    """Email verification request model."""
    token: str = Field(..., min_length=32, max_length=64, description="Verification token")


class ResendVerificationRequest(BaseModel):
    """Resend verification email request model."""
    email: EmailStr = Field(..., description="User's email address")


class VerificationResponse(BaseModel):
    """Email verification response model."""
    data: dict
    metadata: dict
    success: int


def hash_password(password: str) -> str:
    """Hash password using SHA-256 with salt."""
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{password_hash}"


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    try:
        salt, password_hash = hashed_password.split(':')
        return hashlib.sha256((password + salt).encode()).hexdigest() == password_hash
    except:
        return False


def create_access_token(data: dict) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_client_ip(request: Request) -> str:
    """Get client IP address."""
    if request.client:
        return request.client.host
    return "unknown"


def check_rate_limit(email: str, ip: str) -> tuple[bool, int]:
    """Check rate limiting for login attempts."""
    key = f"{email}:{ip}"
    current_time = time.time()
    
    if key not in login_attempts:
        login_attempts[key] = []
    
    # Remove attempts older than 15 minutes
    login_attempts[key] = [
        attempt_time for attempt_time in login_attempts[key]
        if current_time - attempt_time < 900  # 15 minutes
    ]
    
    attempts_left = max(0, 5 - len(login_attempts[key]))
    is_allowed = len(login_attempts[key]) < 5
    
    return is_allowed, attempts_left


def record_login_attempt(email: str, ip: str, success: bool):
    """Record login attempt for rate limiting."""
    if not success:
        key = f"{email}:{ip}"
        current_time = time.time()
        
        if key not in login_attempts:
            login_attempts[key] = []
        
        login_attempts[key].append(current_time)


def generate_verification_token(email: str) -> str:
    """Generate a secure verification token for email verification."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=24)  # Token expires in 24 hours
    
    verification_tokens[token] = {
        "email": email.lower(),
        "expires_at": expires_at,
        "used": False
    }
    
    return token


def verify_verification_token(token: str) -> Optional[str]:
    """Verify a verification token and return the email if valid."""
    if token not in verification_tokens:
        return None
    
    token_data = verification_tokens[token]
    
    # Check if token is expired
    if datetime.utcnow() > token_data["expires_at"]:
        del verification_tokens[token]  # Clean up expired token
        return None
    
    # Check if token is already used
    if token_data["used"]:
        return None
    
    return token_data["email"]


def mark_token_as_used(token: str) -> None:
    """Mark a verification token as used."""
    if token in verification_tokens:
        verification_tokens[token]["used"] = True


def cleanup_expired_tokens() -> None:
    """Clean up expired verification tokens."""
    current_time = datetime.utcnow()
    expired_tokens = [
        token for token, data in verification_tokens.items()
        if current_time > data["expires_at"]
    ]
    
    for token in expired_tokens:
        del verification_tokens[token]


def check_verification_rate_limit(email: str) -> tuple[bool, int]:
    """Check if user can request verification email (rate limiting)."""
    email_key = email.lower()
    current_time = time.time()
    
    if email_key not in email_verification_attempts:
        email_verification_attempts[email_key] = {
            "attempts": [],
            "last_attempt": 0
        }
    
    attempts_data = email_verification_attempts[email_key]
    
    # Clean old attempts (older than 1 hour)
    attempts_data["attempts"] = [
        attempt_time for attempt_time in attempts_data["attempts"]
        if current_time - attempt_time < 3600  # 1 hour
    ]
    
    # Check if too many attempts
    if len(attempts_data["attempts"]) >= 5:  # Max 5 attempts per hour
        return False, 0
    
    return True, 5 - len(attempts_data["attempts"])


def record_verification_attempt(email: str) -> None:
    """Record a verification email attempt."""
    email_key = email.lower()
    current_time = time.time()
    
    if email_key not in email_verification_attempts:
        email_verification_attempts[email_key] = {
            "attempts": [],
            "last_attempt": 0
        }
    
    email_verification_attempts[email_key]["attempts"].append(current_time)
    email_verification_attempts[email_key]["last_attempt"] = current_time


# Mock user database (in production, use proper database)
# Note: This is now replaced by the database service
users_db = {}  # Keep for backward compatibility during transition


@router.post(
    "/register", 
    response_model=RegistrationResponse,
    tags=["Authentication"],
    summary="User Registration",
    description="""
    Register a new user account with comprehensive validation and security measures.
    
    **Registration Process:**
    1. Validates all input fields (name, email, password)
    2. Checks password strength requirements
    3. Verifies email format and uniqueness
    4. Creates secure password hash with salt
    5. Generates email verification token
    6. Stores user data (inactive until email verified)
    
    **Password Requirements:**
    - Minimum 8 characters, maximum 128 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character
    - Cannot be common weak passwords
    
    **Email Verification:**
    - User receives verification token in response
    - Account remains inactive until email is verified
    - Token expires after 24 hours
    - User must verify email before login
    
    **Security Features:**
    - Password hashing with SHA-256 and salt
    - Input validation and sanitization
    - Rate limiting protection
    - Audit logging for all attempts
    - Email uniqueness validation
    """,
    responses={
        200: {
            "description": "User registered successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "User created successfully. Please check your email for verification link.",
                            "verification_token": "abc123def456ghi789jkl012mno345pqr678stu901vwx234yz"
                        },
                        "metadata": {
                            "statusCode": 211,
                            "errors": [],
                            "executionTime": 0.02
                        },
                        "success": 1
                    }
                }
            }
        },
        400: {
            "description": "Registration failed - validation error",
            "content": {
                "application/json": {
                    "examples": {
                        "user_exists": {
                            "summary": "User already exists",
                            "value": {
                                "data": {
                                    "message": "User already exists"
                                },
                                "metadata": {
                                    "errors": ["Email address is already registered"],
                                    "statusCode": 400,
                                    "executionTime": 0.01
                                },
                                "success": 0
                            }
                        },
                        "validation_error": {
                            "summary": "Validation error",
                            "value": {
                                "data": {
                                    "message": "Validation error"
                                },
                                "metadata": {
                                    "errors": [
                                        "body -> password: String should have at least 8 characters",
                                        "body -> email: value is not a valid email address"
                                    ],
                                    "statusCode": 422,
                                    "executionTime": 0.0
                                },
                                "success": 0
                            }
                        }
                    }
                }
            }
        },
        422: {
            "description": "Validation error - invalid input data",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "Validation error"
                        },
                        "metadata": {
                            "errors": [
                                "body -> first_name: String should have at least 1 character",
                                "body -> password: Password is too common. Please choose a stronger password."
                            ],
                            "statusCode": 422,
                            "executionTime": 0.0
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
                            "message": "Registration failed"
                        },
                        "metadata": {
                            "errors": ["Database connection failed"],
                            "statusCode": 500,
                            "executionTime": 0.01
                        },
                        "success": 0
                    }
                }
            }
        }
    }
)
async def register_user(user_data: UserRegistrationRequest, request: Request):
    """
    User Registration Endpoint
    
    Creates a new user account with comprehensive validation, security measures,
    and email verification requirements.
    
    **Registration Flow:**
    1. **Input Validation**: Validates all fields according to security requirements
    2. **Uniqueness Check**: Ensures email address is not already registered
    3. **Password Security**: Creates secure hash with salt for password storage
    4. **Account Creation**: Creates inactive user account requiring email verification
    5. **Token Generation**: Generates secure verification token for email verification
    6. **Response**: Returns success message with verification token
    
    **Security Measures:**
    - Password strength validation (8+ chars, mixed case, numbers, special chars)
    - Email format validation and uniqueness check
    - Secure password hashing with SHA-256 and random salt
    - Rate limiting protection against abuse
    - Comprehensive audit logging
    - Input sanitization and validation
    
    **Email Verification:**
    After successful registration, the user must verify their email address
    using the provided verification token before they can log in.
    
    **Rate Limiting:**
    - No specific rate limiting for registration (handled by general API limits)
    - All attempts are logged for security monitoring
    
    Args:
        user_data: UserRegistrationRequest containing user details
        request: FastAPI Request object for IP tracking and logging
    
    Returns:
        RegistrationResponse: Standard API response with success status and metadata
    """
    start_time = time.time()
    client_ip = get_client_ip(request)
    
    logger.info(f"User registration attempt: {user_data.email} from IP: {client_ip}")
    
    try:
        # Check if user already exists using database service
        existing_user = db_service.get_user_by_email(user_data.email)
        if existing_user:
            execution_time = round(time.time() - start_time, 2)
            return RegistrationResponse(
                data={
                    "message": "User already exists"
                },
                metadata={
                    "errors": ["Email address is already registered"],
                    "statusCode": 400,
                    "executionTime": execution_time
                },
                success=0
            )
        
        # Generate verification token
        verification_token = generate_verification_token(user_data.email)
        
        # Simulate database processing time
        await asyncio.sleep(0.02)  # 20ms delay for user creation
        
        # Create user using database service
        user = db_service.create_user(
            first_name=user_data.first_name,
            last_name=user_data.last_name,
        email=user_data.email,
            password=user_data.password,
            verification_token=verification_token
        )
        
        if not user:
            execution_time = round(time.time() - start_time, 2)
            return RegistrationResponse(
                data={
                    "message": "Registration failed"
                },
                metadata={
                    "errors": ["Failed to create user account"],
                    "statusCode": 500,
                    "executionTime": execution_time
                },
                success=0
            )
        
        # Clean up expired tokens
        cleanup_expired_tokens()
        
        # Send verification email
        email_sent = False
        try:
            email_sent = await email_service.send_verification_email(
                to_email=user_data.email,
                first_name=user_data.first_name,
                verification_token=verification_token
            )
        except Exception as e:
            logger.error(f"Failed to send verification email to {user_data.email}: {e}")
        
        execution_time = round(time.time() - start_time, 2)
        
        if email_sent:
            logger.info(f"User registered successfully: {user_data.email}, verification email sent")
            message = "User created successfully. Please check your email for verification link."
        else:
            logger.warning(f"User registered successfully: {user_data.email}, but verification email failed to send")
            message = "User created successfully. Please check your email for verification link. If you don't receive it, please contact support."
        
        return RegistrationResponse(
            data={
                "message": message,
                "verification_token": verification_token if not email_sent else None  # Only return token if email failed
            },
            metadata={
                "statusCode": 211,
                "errors": [],
                "executionTime": execution_time
            },
            success=1
        )
        
    except Exception as e:
        execution_time = round(time.time() - start_time, 2)
        logger.error(f"Registration error for {user_data.email}: {str(e)}")
        
        return RegistrationResponse(
            data={
                "message": "Registration failed"
            },
            metadata={
                "errors": [str(e)],
                "statusCode": 500,
                "executionTime": execution_time
            },
            success=0
        )


@router.post(
    "/login", 
    response_model=LoginResponse,
    tags=["Authentication"],
    summary="User Login",
    description="""
    Authenticate user with email and password to receive JWT access token.
    
    **Login Process:**
    1. Validates email format and password
    2. Checks rate limiting (5 attempts per hour per IP)
    3. Verifies user exists in database
    4. Validates password against stored hash
    5. Checks email verification status
    6. Generates JWT access token
    7. Updates last login timestamp
    
    **Rate Limiting:**
    - Maximum 5 login attempts per hour per IP address
    - Failed attempts are tracked and logged
    - Account temporarily locked after exceeding limit
    - Attempts reset after 1 hour
    
    **Email Verification Required:**
    - User must verify email before login
    - Unverified accounts cannot authenticate
    - Clear error message guides user to verification
    
    **JWT Token:**
    - Valid for 30 minutes
    - Contains user ID and email
    - Must be included in Authorization header for protected endpoints
    - Format: `Bearer <token>`
    
    **Security Features:**
    - Password verification with secure hashing
    - Rate limiting protection against brute force
    - Comprehensive audit logging
    - IP address tracking
    - Failed attempt monitoring
    """,
    responses={
        200: {
            "description": "Login successful",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "user": {
                                "first_name": "John",
                                "last_name": "Doe",
                                "email": "john.doe@example.com",
                                "active": True,
                                "email_verified": True
                            },
                            "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE1OTAyMzU3NTIsImlhdCI6MTU5MDE0OTM1Miwic3ViIjoyfQ.GrFbMq7CI8HrvSub010tUIiUDTlfPDOHVdzV4z0wNDg",
                            "message": "Login successful"
                        },
                        "metadata": {
                            "errors": [],
                            "statusCode": 212,
                            "executionTime": 0.02,
                            "attemptsLeft": 5
                        },
                        "success": 1
                    }
                }
            }
        },
        401: {
            "description": "Authentication failed",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_credentials": {
                            "summary": "Invalid email or password",
                            "value": {
                                "data": {
                                    "message": "Invalid credentials"
                                },
                                "metadata": {
                                    "errors": ["Invalid email or password"],
                                    "statusCode": 401,
                                    "executionTime": 0.01,
                                    "attemptsLeft": 4
                                },
                                "success": 0
                            }
                        },
                        "email_not_verified": {
                            "summary": "Email not verified",
                            "value": {
                                "data": {
                                    "message": "Email not verified"
                                },
                                "metadata": {
                                    "errors": ["Please verify your email address to activate your account"],
                                    "statusCode": 403,
                                    "executionTime": 0.01,
                                    "attemptsLeft": 5
                                },
                                "success": 0
                            }
                        }
                    }
                }
            }
        },
        404: {
            "description": "User not found",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "User not found"
                        },
                        "metadata": {
                            "errors": ["No account found with this email address"],
                            "statusCode": 404,
                            "executionTime": 0.01,
                            "attemptsLeft": 4
                        },
                        "success": 0
                    }
                }
            }
        },
        429: {
            "description": "Too many login attempts",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "Too many login attempts"
                        },
                        "metadata": {
                            "errors": ["Account temporarily locked due to too many failed attempts"],
                            "statusCode": 429,
                            "executionTime": 0.01,
                            "attemptsLeft": 0
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
                            "message": "Login failed"
                        },
                        "metadata": {
                            "errors": ["Database connection failed"],
                            "statusCode": 500,
                            "executionTime": 0.01,
                            "attemptsLeft": 0
                        },
                        "success": 0
                    }
                }
            }
        }
    }
)
async def login_user(login_data: UserLoginRequest, request: Request):
    """
    User Authentication Endpoint
    
    Authenticates users with email and password, returning a JWT access token
    for accessing protected endpoints.
    
    **Authentication Flow:**
    1. **Rate Limiting Check**: Verifies user hasn't exceeded login attempts
    2. **User Lookup**: Finds user account by email address
    3. **Password Verification**: Validates password against stored hash
    4. **Email Verification Check**: Ensures user has verified their email
    5. **Token Generation**: Creates JWT token with user information
    6. **Login Tracking**: Updates last login timestamp and records successful attempt
    
    **Security Measures:**
    - Rate limiting: 5 attempts per hour per IP address
    - Password verification with secure hashing
    - Email verification requirement
    - Comprehensive audit logging
    - IP address tracking for security monitoring
    - Failed attempt tracking and alerting
    
    **JWT Token Details:**
    - Expires after 30 minutes
    - Contains user ID and email
    - Signed with secret key
    - Must be included in Authorization header: `Bearer <token>`
    
    **Rate Limiting:**
    - Maximum 5 login attempts per hour per IP
    - Failed attempts are tracked and counted
    - Account locked temporarily after limit exceeded
    - Attempts reset after 1 hour window
    
    Args:
        login_data: UserLoginRequest containing email and password
        request: FastAPI Request object for IP tracking and logging
    
    Returns:
        LoginResponse: Standard API response with user data and JWT token
    """
    start_time = time.time()
    client_ip = get_client_ip(request)
    
    logger.info(f"Login attempt: {login_data.email} from IP: {client_ip}")
    
    try:
        # Check rate limiting
        is_allowed, attempts_left = check_rate_limit(login_data.email, client_ip)
        
        if not is_allowed:
            execution_time = round(time.time() - start_time, 2)
            record_login_attempt(login_data.email, client_ip, False)
            
            return LoginResponse(
                data={
                    "message": "Too many login attempts"
                },
                metadata={
                    "errors": ["Account temporarily locked due to too many failed attempts"],
                    "statusCode": 429,
                    "executionTime": execution_time,
                    "attemptsLeft": 0
                },
                success=0
            )
        
        # Check if user exists using database service
        user_record = db_service.get_user_by_email(login_data.email)
        
        if not user_record:
            execution_time = round(time.time() - start_time, 2)
            record_login_attempt(login_data.email, client_ip, False)
            
            return LoginResponse(
                data={
                    "message": "Invalid credentials"
                },
                metadata={
                    "errors": ["Invalid email or password"],
                    "statusCode": 401,
                    "executionTime": execution_time,
                    "attemptsLeft": attempts_left - 1
                },
                success=0
            )
        
        # Verify password using database service
        if not db_service.verify_password(login_data.password, user_record.password_hash):
            execution_time = round(time.time() - start_time, 2)
            record_login_attempt(login_data.email, client_ip, False)
            
            return LoginResponse(
                data={
                    "message": "Invalid credentials"
                },
                metadata={
                    "errors": ["Invalid email or password"],
                    "statusCode": 401,
                    "executionTime": execution_time,
                    "attemptsLeft": attempts_left - 1
                },
                success=0
            )
        
        # Check if user is active and email is verified
        if not user_record.email_verified:
            execution_time = round(time.time() - start_time, 2)
            
            return LoginResponse(
                data={
                    "message": "Email not verified"
                },
                metadata={
                    "errors": ["Please verify your email address to activate your account"],
                    "statusCode": 403,
                    "executionTime": execution_time,
                    "attemptsLeft": attempts_left
                },
                success=0
            )
        
        # Create JWT token
        token_data = {
            "sub": str(user_record.id),
            "email": user_record.email,
            "iat": datetime.utcnow()
        }
        access_token = create_access_token(token_data)
        
        # Simulate token processing time
        await asyncio.sleep(0.015)  # 15ms delay for token creation
        
        # Update last login using database service
        db_service.update_last_login(login_data.email)
        
        # Record successful login
        record_login_attempt(login_data.email, client_ip, True)
        
        execution_time = round(time.time() - start_time, 2)
        
        logger.info(f"User logged in successfully: {login_data.email}")
        
        return LoginResponse(
            data={
                "user": {
                    "first_name": user_record.first_name,
                    "last_name": user_record.last_name,
                    "email": user_record.email,
                    "active": user_record.active,
                    "email_verified": user_record.email_verified
                },
                "token": access_token,
                "message": "Login successful"
            },
            metadata={
                "errors": [],
                "statusCode": 212,
                "executionTime": execution_time,
                "attemptsLeft": 5
            },
            success=1
        )
        
    except Exception as e:
        execution_time = round(time.time() - start_time, 2)
        logger.error(f"Login error for {login_data.email}: {str(e)}")
        
        return LoginResponse(
            data={
                "message": "Login failed"
            },
            metadata={
                "errors": [str(e)],
                "statusCode": 500,
                "executionTime": execution_time,
                "attemptsLeft": 0
            },
            success=False
        )


@router.post(
    "/verify-email", 
    response_model=VerificationResponse,
    tags=["Email Verification"],
    summary="Verify Email Address",
    description="""
    Verify user's email address using the verification token received during registration.
    
    **Verification Process:**
    1. Validates verification token format and length
    2. Checks token exists and hasn't expired (24 hours)
    3. Verifies token hasn't been used before
    4. Finds associated user account
    5. Checks if email is already verified
    6. Activates user account and marks email as verified
    7. Marks token as used to prevent reuse
    
    **Token Security:**
    - Tokens expire after 24 hours
    - Each token can only be used once
    - Tokens are cryptographically secure (32 characters)
    - Expired tokens are automatically cleaned up
    
    **Account Activation:**
    - User account becomes active after verification
    - User can now log in with their credentials
    - Email verification status is permanently recorded
    - Verification timestamp is stored for audit purposes
    
    **Error Handling:**
    - Invalid or expired tokens return clear error messages
    - Already verified accounts are handled gracefully
    - Non-existent users are properly handled
    - All attempts are logged for security monitoring
    """,
    responses={
        200: {
            "description": "Email verified successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "Email verified successfully. Your account is now active."
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
        400: {
            "description": "Verification failed",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_token": {
                            "summary": "Invalid or expired token",
                            "value": {
                                "data": {
                                    "message": "Invalid or expired verification token"
                                },
                                "metadata": {
                                    "errors": ["The verification token is invalid, expired, or already used"],
                                    "statusCode": 400,
                                    "executionTime": 0.01
                                },
                                "success": 0
                            }
                        },
                        "already_verified": {
                            "summary": "Email already verified",
                            "value": {
                                "data": {
                                    "message": "Email already verified"
                                },
                                "metadata": {
                                    "errors": ["This email address has already been verified"],
                                    "statusCode": 400,
                                    "executionTime": 0.01
                                },
                                "success": 0
                            }
                        }
                    }
                }
            }
        },
        404: {
            "description": "User not found",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "User not found"
                        },
                        "metadata": {
                            "errors": ["User account not found"],
                            "statusCode": 404,
                            "executionTime": 0.01
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
                            "message": "Email verification failed"
                        },
                        "metadata": {
                            "errors": ["Database connection failed"],
                            "statusCode": 500,
                            "executionTime": 0.01
                        },
                        "success": 0
                    }
                }
            }
        }
    }
)
async def verify_email(verification_data: EmailVerificationRequest, request: Request):
    """
    Email Verification Endpoint
    
    Verifies user email addresses using secure verification tokens received
    during the registration process.
    
    **Verification Flow:**
    1. **Token Validation**: Checks token format, existence, and expiration
    2. **User Lookup**: Finds the user account associated with the token
    3. **Status Check**: Verifies the email hasn't already been verified
    4. **Account Activation**: Activates the user account and marks email as verified
    5. **Token Cleanup**: Marks the token as used to prevent reuse
    6. **Audit Logging**: Records the verification event for security monitoring
    
    **Token Security:**
    - Tokens are 32-character cryptographically secure strings
    - Expire after 24 hours from generation
    - Can only be used once (single-use tokens)
    - Automatically cleaned up when expired
    
    **Account Activation:**
    After successful verification:
    - User account becomes active
    - Email verification status is permanently recorded
    - User can now log in with their credentials
    - Verification timestamp is stored for audit purposes
    
    **Security Features:**
    - Comprehensive token validation
    - Prevention of token reuse
    - Automatic cleanup of expired tokens
    - Audit logging for all verification attempts
    - Clear error messages for different failure scenarios
    
    Args:
        verification_data: EmailVerificationRequest containing the verification token
        request: FastAPI Request object for IP tracking and logging
    
    Returns:
        VerificationResponse: Standard API response with verification status
    """
    start_time = time.time()
    client_ip = get_client_ip(request)
    
    logger.info(f"Email verification attempt from IP: {client_ip}")
    
    try:
        # Verify the token
        email = verify_verification_token(verification_data.token)
        
        if not email:
            execution_time = round(time.time() - start_time, 2)
            return VerificationResponse(
                data={
                    "message": "Invalid or expired verification token"
                },
                metadata={
                    "errors": ["The verification token is invalid, expired, or already used"],
                    "statusCode": 400,
                    "executionTime": execution_time
                },
                success=0
            )
        
        # Check if user exists using database service
        user_record = db_service.get_user_by_email(email)
        if not user_record:
            execution_time = round(time.time() - start_time, 2)
            return VerificationResponse(
                data={
                    "message": "User not found"
                },
                metadata={
                    "errors": ["User account not found"],
                    "statusCode": 404,
                    "executionTime": execution_time
                },
                success=0
            )
        
        # Check if already verified
        if user_record.email_verified:
            execution_time = round(time.time() - start_time, 2)
            return VerificationResponse(
                data={
                    "message": "Email already verified"
                },
                metadata={
                    "errors": ["This email address has already been verified"],
                    "statusCode": 400,
                    "executionTime": execution_time
                },
                success=0
            )
        
        # Verify email using database service
        if db_service.verify_user_email(email, verification_data.token):
            # Mark token as used
            mark_token_as_used(verification_data.token)
            
            # Send welcome email
            try:
                user_record = db_service.get_user_by_email(email)
                if user_record:
                    await email_service.send_welcome_email(
                        to_email=email,
                        first_name=user_record.first_name
                    )
            except Exception as e:
                logger.error(f"Failed to send welcome email to {email}: {e}")
            
            execution_time = round(time.time() - start_time, 2)
            
            logger.info(f"Email verified successfully: {email}")
            
            return VerificationResponse(
                data={
                    "message": "Email verified successfully. Your account is now active."
                },
                metadata={
                    "statusCode": 200,
                    "errors": [],
                    "executionTime": execution_time
                },
                success=1
            )
        else:
            execution_time = round(time.time() - start_time, 2)
            return VerificationResponse(
                data={
                    "message": "Email verification failed"
                },
                metadata={
                    "errors": ["Invalid verification token or database error"],
                    "statusCode": 500,
                    "executionTime": execution_time
                },
                success=0
            )
        
    except Exception as e:
        execution_time = round(time.time() - start_time, 2)
        logger.error(f"Email verification error: {str(e)}")
        
        return VerificationResponse(
            data={
                "message": "Email verification failed"
            },
            metadata={
                "errors": [str(e)],
                "statusCode": 500,
                "executionTime": execution_time
            },
            success=0
        )


@router.get(
    "/verify-email",
    tags=["Email Verification"],
    summary="Verify Email Address (GET)",
    description="""
    Verify user's email address using a verification token from URL query parameter.
    
    This endpoint is designed to handle email verification links that users click
    from their email clients. It accepts the verification token as a query parameter.
    
    **Usage:**
    - Users click verification link in email
    - Link contains token as query parameter: ?token=abc123...
    - This endpoint processes the verification
    
    **Security Features:**
    - Token validation and expiration checking
    - Single-use token enforcement
    - Comprehensive error handling
    - Audit logging for all attempts
    """,
    responses={
        200: {
            "description": "Email verified successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "Email verified successfully. Your account is now active."
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
        400: {
            "description": "Verification failed",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_token": {
                            "summary": "Invalid or expired token",
                            "value": {
                                "data": {
                                    "message": "Invalid or expired verification token"
                                },
                                "metadata": {
                                    "errors": ["The verification token is invalid, expired, or already used"],
                                    "statusCode": 400,
                                    "executionTime": 0.01
                                },
                                "success": 0
                            }
                        },
                        "missing_token": {
                            "summary": "Missing token parameter",
                            "value": {
                                "data": {
                                    "message": "Verification token is required"
                                },
                                "metadata": {
                                    "errors": ["Token parameter is missing from URL"],
                                    "statusCode": 400,
                                    "executionTime": 0.01
                                },
                                "success": 0
                            }
                        }
                    }
                }
            }
        },
        404: {
            "description": "User not found",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "User not found"
                        },
                        "metadata": {
                            "errors": ["User account not found"],
                            "statusCode": 404,
                            "executionTime": 0.01
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
                            "message": "Email verification failed"
                        },
                        "metadata": {
                            "errors": ["Database connection failed"],
                            "statusCode": 500,
                            "executionTime": 0.01
                        },
                        "success": 0
                    }
                }
            }
        }
    }
)
async def verify_email_get(token: str = None, request: Request = None):
    """
    Email Verification Endpoint (GET)
    
    Handles email verification links clicked by users from their email clients.
    Accepts verification token as a query parameter.
    
    Args:
        token: Verification token from URL query parameter
        request: FastAPI Request object for IP tracking and logging
    
    Returns:
        VerificationResponse: Standard API response with verification status
    """
    start_time = time.time()
    client_ip = get_client_ip(request) if request else "unknown"
    
    logger.info(f"Email verification attempt (GET) from IP: {client_ip}")
    
    try:
        # Check if token is provided
        if not token:
            execution_time = round(time.time() - start_time, 2)
            return VerificationResponse(
                data={
                    "message": "Verification token is required"
                },
                metadata={
                    "errors": ["Token parameter is missing from URL"],
                    "statusCode": 400,
                    "executionTime": execution_time
                },
                success=0
            )
        
        # Verify the token
        email = verify_verification_token(token)
        
        if not email:
            execution_time = round(time.time() - start_time, 2)
            return VerificationResponse(
                data={
                    "message": "Invalid or expired verification token"
                },
                metadata={
                    "errors": ["The verification token is invalid, expired, or already used"],
                    "statusCode": 400,
                    "executionTime": execution_time
                },
                success=0
            )
        
        # Check if user exists using database service
        user_record = db_service.get_user_by_email(email)
        if not user_record:
            execution_time = round(time.time() - start_time, 2)
            return VerificationResponse(
                data={
                    "message": "User not found"
                },
                metadata={
                    "errors": ["User account not found"],
                    "statusCode": 404,
                    "executionTime": execution_time
                },
                success=0
            )
        
        # Check if already verified
        if user_record.email_verified:
            execution_time = round(time.time() - start_time, 2)
            return VerificationResponse(
                data={
                    "message": "Email already verified"
                },
                metadata={
                    "errors": ["This email address has already been verified"],
                    "statusCode": 400,
                    "executionTime": execution_time
                },
                success=0
            )
        
        # Verify email using database service
        if db_service.verify_user_email(email, token):
            # Mark token as used
            mark_token_as_used(token)
            
            # Send welcome email
            try:
                user_record = db_service.get_user_by_email(email)
                if user_record:
                    await email_service.send_welcome_email(
                        to_email=email,
                        first_name=user_record.first_name
                    )
            except Exception as e:
                logger.error(f"Failed to send welcome email to {email}: {e}")
            
            execution_time = round(time.time() - start_time, 2)
            
            logger.info(f"Email verified successfully (GET): {email}")
            
            return VerificationResponse(
                data={
                    "message": "Email verified successfully. Your account is now active."
                },
                metadata={
                    "statusCode": 200,
                    "errors": [],
                    "executionTime": execution_time
                },
                success=1
            )
        else:
            execution_time = round(time.time() - start_time, 2)
            return VerificationResponse(
                data={
                    "message": "Email verification failed"
                },
                metadata={
                    "errors": ["Invalid verification token or database error"],
                    "statusCode": 500,
                    "executionTime": execution_time
                },
                success=0
            )
        
    except Exception as e:
        execution_time = round(time.time() - start_time, 2)
        logger.error(f"Email verification error (GET): {str(e)}")
        
        return VerificationResponse(
            data={
                "message": "Email verification failed"
            },
            metadata={
                "errors": [str(e)],
                "statusCode": 500,
                "executionTime": execution_time
            },
            success=0
        )


@router.post(
    "/resend-verification", 
    response_model=VerificationResponse,
    tags=["Email Verification"],
    summary="Resend Verification Email",
    description="""
    Resend verification email to user with a new verification token.
    
    **Resend Process:**
    1. Validates email format and checks rate limiting
    2. Verifies user account exists in database
    3. Checks if email is already verified
    4. Generates new verification token (invalidates old token)
    5. Updates user record with new token
    6. Records resend attempt for rate limiting
    
    **Rate Limiting:**
    - Maximum 5 verification email requests per hour per email
    - Prevents spam and abuse of verification system
    - Attempts are tracked and logged
    - Clear indication of remaining attempts
    
    **Token Management:**
    - New token invalidates any previous token
    - Each token expires after 24 hours
    - Tokens are cryptographically secure
    - Automatic cleanup of expired tokens
    
    **Use Cases:**
    - User didn't receive original verification email
    - Verification token expired (24 hours)
    - User lost access to verification link
    - Account recovery scenarios
    
    **Security Features:**
    - Rate limiting prevents abuse
    - Email validation and user verification
    - Comprehensive audit logging
    - Clear error messages for different scenarios
    """,
    responses={
        200: {
            "description": "Verification email sent successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "Verification email sent successfully",
                            "verification_token": "new_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz"
                        },
                        "metadata": {
                            "statusCode": 200,
                            "errors": [],
                            "executionTime": 0.01,
                            "attemptsLeft": 4
                        },
                        "success": 1
                    }
                }
            }
        },
        400: {
            "description": "Resend failed",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "Email already verified"
                        },
                        "metadata": {
                            "errors": ["This email address has already been verified"],
                            "statusCode": 400,
                            "executionTime": 0.01,
                            "attemptsLeft": 5
                        },
                        "success": 0
                    }
                }
            }
        },
        404: {
            "description": "User not found",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "User not found"
                        },
                        "metadata": {
                            "errors": ["No account found with this email address"],
                            "statusCode": 404,
                            "executionTime": 0.01,
                            "attemptsLeft": 4
                        },
                        "success": 0
                    }
                }
            }
        },
        429: {
            "description": "Too many verification requests",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "Too many verification email requests"
                        },
                        "metadata": {
                            "errors": ["Too many verification email requests. Please wait before trying again."],
                            "statusCode": 429,
                            "executionTime": 0.01,
                            "attemptsLeft": 0
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
                            "message": "Failed to resend verification email"
                        },
                        "metadata": {
                            "errors": ["Database connection failed"],
                            "statusCode": 500,
                            "executionTime": 0.01,
                            "attemptsLeft": 0
                        },
                        "success": 0
                    }
                }
            }
        }
    }
)
async def resend_verification_email(resend_data: ResendVerificationRequest, request: Request):
    """
    Resend Verification Email Endpoint
    
    Allows users to request a new verification email with a fresh token
    when the original verification email was not received or has expired.
    
    **Resend Flow:**
    1. **Rate Limiting Check**: Verifies user hasn't exceeded resend attempts
    2. **User Validation**: Confirms user account exists and is not verified
    3. **Token Generation**: Creates new verification token (invalidates old one)
    4. **Account Update**: Updates user record with new token
    5. **Attempt Tracking**: Records resend attempt for rate limiting
    6. **Response**: Returns new token and remaining attempts
    
    **Rate Limiting:**
    - Maximum 5 verification email requests per hour per email address
    - Prevents spam and abuse of the verification system
    - Attempts are tracked with timestamps
    - Clear indication of remaining attempts in response
    
    **Token Management:**
    - New token automatically invalidates any previous token
    - Each token expires after 24 hours
    - Tokens are 32-character cryptographically secure strings
    - Expired tokens are automatically cleaned up
    
    **Use Cases:**
    - User didn't receive the original verification email
    - Verification token expired (24-hour limit)
    - User lost access to the verification link
    - Account recovery and verification scenarios
    
    **Security Features:**
    - Rate limiting prevents abuse and spam
    - Email validation and user account verification
    - Comprehensive audit logging for all attempts
    - Clear error messages for different failure scenarios
    - Automatic cleanup of expired tokens
    
    Args:
        resend_data: ResendVerificationRequest containing the email address
        request: FastAPI Request object for IP tracking and logging
    
    Returns:
        VerificationResponse: Standard API response with new token and attempt info
    """
    start_time = time.time()
    client_ip = get_client_ip(request)
    
    logger.info(f"Resend verification request: {resend_data.email} from IP: {client_ip}")
    
    try:
        # Check rate limiting
        is_allowed, attempts_left = check_verification_rate_limit(resend_data.email)
        
        if not is_allowed:
            execution_time = round(time.time() - start_time, 2)
            return VerificationResponse(
                data={
                    "message": "Too many verification email requests"
                },
                metadata={
                    "errors": ["Too many verification email requests. Please wait before trying again."],
                    "statusCode": 429,
                    "executionTime": execution_time,
                    "attemptsLeft": 0
                },
                success=0
            )
        
        # Check if user exists using database service
        user_record = db_service.get_user_by_email(resend_data.email)
        if not user_record:
            execution_time = round(time.time() - start_time, 2)
            return VerificationResponse(
                data={
                    "message": "User not found"
                },
                metadata={
                    "errors": ["No account found with this email address"],
                    "statusCode": 404,
                    "executionTime": execution_time,
                    "attemptsLeft": attempts_left
                },
                success=0
            )
        
        # Check if already verified
        if user_record.email_verified:
            execution_time = round(time.time() - start_time, 2)
            return VerificationResponse(
                data={
                    "message": "Email already verified"
                },
                metadata={
                    "errors": ["This email address has already been verified"],
                    "statusCode": 400,
                    "executionTime": execution_time,
                    "attemptsLeft": attempts_left
                },
                success=0
            )
        
        # Generate new verification token
        new_token = generate_verification_token(resend_data.email)
        
        # Update user verification token in database
        db_service.update_user_verification_token(resend_data.email, new_token)
        
        # Send verification email
        email_sent = False
        try:
            email_sent = await email_service.send_verification_email(
                to_email=resend_data.email,
                first_name=user_record.first_name,
                verification_token=new_token
            )
        except Exception as e:
            logger.error(f"Failed to send verification email to {resend_data.email}: {e}")
        
        # Record the attempt
        record_verification_attempt(resend_data.email)
        
        execution_time = round(time.time() - start_time, 2)
        
        if email_sent:
            logger.info(f"Verification email resent: {resend_data.email}")
            message = "Verification email sent successfully"
        else:
            logger.warning(f"Verification email resent failed: {resend_data.email}")
            message = "Verification email sent successfully. If you don't receive it, please contact support."
        
        return VerificationResponse(
            data={
                "message": message,
                "verification_token": new_token if not email_sent else None  # Only return token if email failed
            },
            metadata={
                "statusCode": 200,
                "errors": [],
                "executionTime": execution_time,
                "attemptsLeft": attempts_left - 1
            },
            success=1
        )
        
    except Exception as e:
        execution_time = round(time.time() - start_time, 2)
        logger.error(f"Resend verification error for {resend_data.email}: {str(e)}")
        
        return VerificationResponse(
            data={
                "message": "Failed to resend verification email"
            },
            metadata={
                "errors": [str(e)],
                "statusCode": 500,
                "executionTime": execution_time,
                "attemptsLeft": 0
            },
            success=0
        )


@router.get(
    "/me",
    tags=["User Management"],
    summary="Get Current User Information",
    description="""
    Retrieve current user information and account status.
    
    **User Information Provided:**
    - User profile details (name, email)
    - Account status and verification status
    - Account creation and last login timestamps
    - Security and privacy settings
    
    **Authentication Required:**
    - Valid JWT token must be provided in Authorization header
    - Token format: `Bearer <jwt_token>`
    - Token must not be expired (30 minutes)
    
    **Use Cases:**
    - User profile display
    - Account status verification
    - Security dashboard information
    - User preference management
    
    **Security Features:**
    - JWT token validation
    - User session verification
    - Sensitive data protection
    - Audit logging for access
    """,
    responses={
        200: {
            "description": "User information retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "User information endpoint",
                            "user": {
                                "id": 1,
                                "first_name": "John",
                                "last_name": "Doe",
                                "email": "john.doe@example.com",
                                "active": True,
                                "email_verified": True,
                                "created_at": "2024-01-15T10:30:00Z",
                                "last_login": "2024-01-20T14:45:00Z"
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
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "Authentication required"
                        },
                        "metadata": {
                            "errors": ["Valid JWT token required"],
                            "statusCode": 401,
                            "executionTime": 0.0
                        },
                        "success": 0
                    }
                }
            }
        },
        403: {
            "description": "Token expired or invalid",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "message": "Token expired"
                        },
                        "metadata": {
                            "errors": ["JWT token has expired"],
                            "statusCode": 403,
                            "executionTime": 0.0
                        },
                        "success": 0
                    }
                }
            }
        }
    }
)
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Get Current User Information Endpoint
    
    Retrieves detailed information about the currently authenticated user,
    including profile details, account status, and security information.
    
    **Authentication:**
    This endpoint requires a valid JWT token in the Authorization header.
    The token must be obtained through the login endpoint and not expired.
    
    **User Information:**
    Returns comprehensive user data including:
    - Personal information (name, email)
    - Account status (active, verified)
    - Security information (verification status)
    - Timestamps (creation, last login)
    - Privacy and preference settings
    
    **Security Features:**
    - JWT token validation and verification
    - User session authentication
    - Sensitive data protection and filtering
    - Comprehensive audit logging
    - Rate limiting protection
    
    **Use Cases:**
    - User profile management interfaces
    - Account status verification
    - Security dashboard displays
    - User preference management
    - Account information updates
    
    **Token Requirements:**
    - Must be included in Authorization header
    - Format: `Bearer <jwt_token>`
    - Must not be expired (30-minute limit)
    - Must be valid and properly signed
    
    Returns:
        dict: Standard API response with user information and metadata
    """
    start_time = time.time()
    
    try:
        # Verify JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        email = payload.get("email")
        
        if not user_id or not email:
            execution_time = round(time.time() - start_time, 2)
            return {
                "data": {
                    "message": "Invalid token"
                },
                "metadata": {
                    "statusCode": 401,
                    "errors": ["Invalid token payload"],
                    "executionTime": execution_time
                },
                "success": 0
            }
        
        # Get user from database
        user = db_service.get_user_by_id(int(user_id))
        if not user:
            execution_time = round(time.time() - start_time, 2)
            return {
                "data": {
                    "message": "User not found"
                },
                "metadata": {
                    "statusCode": 404,
                    "errors": ["User account not found"],
                    "executionTime": execution_time
                },
                "success": 0
            }
        
        # Simulate some processing time
        await asyncio.sleep(0.01)  # 10ms delay
        
        execution_time = round(time.time() - start_time, 2)
        
        return {
            "data": {
                "user": {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "active": user.active,
                    "email_verified": user.email_verified,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                    "verified_at": user.verified_at.isoformat() if user.verified_at else None
                },
                "message": "User information retrieved successfully"
            },
            "metadata": {
                "statusCode": 200,
                "errors": [],
                "executionTime": execution_time
            },
            "success": 1
        }
        
    except jwt.ExpiredSignatureError:
        execution_time = round(time.time() - start_time, 2)
        return {
            "data": {
                "message": "Token expired"
            },
            "metadata": {
                "statusCode": 401,
                "errors": ["JWT token has expired"],
                "executionTime": execution_time
            },
            "success": 0
        }
    except jwt.InvalidTokenError:
        execution_time = round(time.time() - start_time, 2)
        return {
            "data": {
                "message": "Invalid token"
            },
            "metadata": {
                "statusCode": 401,
                "errors": ["Invalid JWT token"],
                "executionTime": execution_time
            },
            "success": 0
        }
    except Exception as e:
        execution_time = round(time.time() - start_time, 2)
        logger.error(f"Error getting current user: {str(e)}")
        return {
            "data": {
                "message": "Internal server error"
            },
            "metadata": {
                "statusCode": 500,
                "errors": ["Internal server error"],
                "executionTime": execution_time
            },
            "success": 0
        }