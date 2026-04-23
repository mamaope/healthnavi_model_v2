"""
Rate limiting utilities for API endpoints.
"""

import time
from typing import Dict, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class SimpleRateLimiter:
    """
    Simple in-memory rate limiter.
    For production, consider using Redis-based rate limiting.
    """
    
    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock_until: Dict[str, float] = {}
    
    def is_allowed(
        self,
        key: str,
        max_requests: int = 5,
        window_seconds: int = 60,
        lockout_seconds: int = 900  # 15 minutes
    ) -> Tuple[bool, str]:
        """
        Check if request is allowed based on rate limit.
        
        Args:
            key: Unique identifier for the rate limit (e.g., IP address, user ID)
            max_requests: Maximum number of requests allowed
            window_seconds: Time window in seconds
            lockout_seconds: Lockout period after exceeding limit
            
        Returns:
            Tuple of (is_allowed, message)
        """
        current_time = time.time()
        
        # Check if currently locked out
        if key in self._lock_until:
            if current_time < self._lock_until[key]:
                remaining = int(self._lock_until[key] - current_time)
                return False, f"Rate limit exceeded. Try again in {remaining} seconds."
            else:
                # Lockout expired, remove it
                del self._lock_until[key]
        
        # Clean old requests outside the window
        cutoff_time = current_time - window_seconds
        self._requests[key] = [
            req_time for req_time in self._requests[key]
            if req_time > cutoff_time
        ]
        
        # Check if limit exceeded
        if len(self._requests[key]) >= max_requests:
            # Lock out for specified period
            self._lock_until[key] = current_time + lockout_seconds
            logger.warning(f"Rate limit exceeded for {key}. Locking for {lockout_seconds} seconds.")
            return False, f"Rate limit exceeded. Too many requests. Try again in {lockout_seconds} seconds."
        
        # Record this request
        self._requests[key].append(current_time)
        return True, "OK"
    
    def reset(self, key: str):
        """Reset rate limit for a key."""
        if key in self._requests:
            del self._requests[key]
        if key in self._lock_until:
            del self._lock_until[key]


# Global rate limiter instance
_rate_limiter = SimpleRateLimiter()


def get_rate_limiter() -> SimpleRateLimiter:
    """Get the global rate limiter instance."""
    return _rate_limiter
