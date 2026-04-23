"""
Security utilities for input sanitization and validation.
"""

import re
import html
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


def sanitize_string(input_str: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize a string input to prevent XSS and injection attacks.
    
    Args:
        input_str: The string to sanitize
        max_length: Optional maximum length to truncate
        
    Returns:
        Sanitized string
    """
    if not isinstance(input_str, str):
        return str(input_str)
    
    # Remove null bytes
    sanitized = input_str.replace('\x00', '')
    
    # HTML escape to prevent XSS
    sanitized = html.escape(sanitized)
    
    # Remove control characters except newlines and tabs
    sanitized = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]', '', sanitized)
    
    # Truncate if max_length specified
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
        logger.warning(f"String truncated to {max_length} characters")
    
    return sanitized


def sanitize_search_query(query: str) -> str:
    """
    Sanitize a search query string.
    
    Args:
        query: Search query string
        
    Returns:
        Sanitized search query
    """
    if not query:
        return ""
    
    # Remove SQL injection patterns (basic)
    dangerous_patterns = [
        r'(\bOR\b|\bAND\b)\s*\d+\s*=\s*\d+',  # SQL injection: OR 1=1
        r';\s*(DROP|DELETE|UPDATE|INSERT|ALTER)',  # SQL commands
        r'--',  # SQL comments
        r'/\*.*?\*/',  # SQL block comments
        r'union\s+select',  # SQL union injection
    ]
    
    sanitized = query
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
    
    # Remove excessive whitespace
    sanitized = ' '.join(sanitized.split())
    
    # Limit length
    if len(sanitized) > 1000:
        sanitized = sanitized[:1000]
    
    return sanitized.strip()


def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not email:
        return False
    
    # Basic email regex (Pydantic also validates, but this is for additional checks)
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email))


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal attacks.
    
    Args:
        filename: Filename to sanitize
        
    Returns:
        Sanitized filename
    """
    if not filename:
        return ""
    
    # Remove path separators and dangerous characters
    sanitized = re.sub(r'[<>:"|?*\x00-\x1f]', '', filename)
    
    # Remove leading dots and slashes
    sanitized = sanitized.lstrip('./')
    
    # Limit length
    if len(sanitized) > 255:
        sanitized = sanitized[:255]
    
    return sanitized


def is_safe_string(input_str: str, allowed_chars: Optional[str] = None) -> bool:
    """
    Check if a string contains only safe characters.
    
    Args:
        input_str: String to check
        allowed_chars: Optional regex pattern of allowed characters
        
    Returns:
        True if string is safe, False otherwise
    """
    if not input_str:
        return True
    
    if allowed_chars:
        return bool(re.match(f'^[{allowed_chars}]+$', input_str))
    
    # Default: alphanumeric, spaces, and common punctuation
    safe_pattern = r'^[a-zA-Z0-9\s\-_.,!?@#$%&*()+=\[\]{}:;"\'<>/\\|`~]*$'
    return bool(re.match(safe_pattern, input_str))
