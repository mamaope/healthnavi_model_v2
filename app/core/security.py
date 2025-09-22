"""
Core security module for HealthNavi AI CDSS.

This module contains security utilities, password hashing,
JWT token handling, and encryption services.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Union
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status
from cryptography.fernet import Fernet
import base64

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class SecurityService:
    """Security service for password and token operations."""
    
    def __init__(self, secret_key: str, encryption_key: str):
        self.secret_key = secret_key
        self.encryption_key = encryption_key
        self.algorithm = "HS256"
        
        # Initialize encryption
        try:
            # Ensure encryption key is 32 bytes
            key_bytes = encryption_key.encode()[:32].ljust(32, b'0')
            self.cipher = Fernet(base64.urlsafe_b64encode(key_bytes))
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            self.cipher = None
    
    def hash_password(self, password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=60)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> dict:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.error(f"Token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data."""
        if not self.cipher:
            logger.warning("Encryption not available, returning plain data")
            return data
        
        try:
            encrypted_data = self.cipher.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return data
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        if not self.cipher:
            logger.warning("Decryption not available, returning encrypted data")
            return encrypted_data
        
        try:
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self.cipher.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return encrypted_data

class InputValidator:
    """Input validation utilities."""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, str]:
        """Validate password strength."""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        
        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one digit"
        
        return True, "Password is valid"
    
    @staticmethod
    def validate_username(username: str) -> tuple[bool, str]:
        """Validate username format."""
        if len(username) < 3:
            return False, "Username must be at least 3 characters long"
        
        if len(username) > 50:
            return False, "Username must be less than 50 characters"
        
        if not username.replace("_", "").replace("-", "").isalnum():
            return False, "Username can only contain letters, numbers, underscores, and hyphens"
        
        return True, "Username is valid"

class SecureLogger:
    """Secure logging utilities."""
    
    @staticmethod
    def log_user_action(user_id: int, action: str, details: Optional[str] = None):
        """Log user actions securely."""
        log_data = {
            "user_id": user_id,
            "action": action,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details
        }
        logger.info(f"User action: {log_data}")
    
    @staticmethod
    def log_security_event(event_type: str, details: str, user_id: Optional[int] = None):
        """Log security events."""
        log_data = {
            "event_type": event_type,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details
        }
        logger.warning(f"Security event: {log_data}")

# Initialize security service
def get_security_service() -> SecurityService:
    """Get security service instance."""
    secret_key = os.getenv("SECRET_KEY", "your-super-secure-secret-key-min-32-characters-long")
    encryption_key = os.getenv("ENCRYPTION_KEY", "your-encryption-key-for-sensitive-data-32-chars")
    return SecurityService(secret_key, encryption_key)
