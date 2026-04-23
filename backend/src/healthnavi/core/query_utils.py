"""
Utility functions for common query parameter parsing and validation.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple

import logging

logger = logging.getLogger(__name__)


def parse_date_range(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_days: int = 365,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse and validate start_date and end_date (YYYY-MM-DD).
    Returns (period_start_iso, period_end_iso) for start of start_date and end of end_date.
    If either is invalid or range exceeds max_days, returns (None, None).
    """
    if not start_date or not end_date:
        return None, None
    try:
        start = datetime.strptime(start_date.strip()[:10], "%Y-%m-%d")
        end = datetime.strptime(end_date.strip()[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        logger.warning(f"Invalid date range: start_date={start_date!r}, end_date={end_date!r}")
        return None, None
    if start > end:
        logger.warning("start_date after end_date, swapping")
        start, end = end, start
    if (end - start).days > max_days:
        logger.warning(f"Date range exceeds {max_days} days, clamping")
        end = start + timedelta(days=max_days)
    period_start = start.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    period_end = (end + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    return period_start, period_end


def parse_days_parameter(days: str, default: int = 30, min_days: int = 1, max_days: int = 365) -> int:
    """
    Parse and validate days parameter from query string.
    
    Args:
        days: Days parameter as string
        default: Default value if parsing fails
        min_days: Minimum allowed value
        max_days: Maximum allowed value
        
    Returns:
        Validated integer days value
    """
    try:
        days_int = int(days) if days else default
    except (ValueError, TypeError):
        logger.warning(f"Invalid days parameter: {days}, using default: {default}")
        days_int = default
    
    # Clamp to valid range
    if days_int < min_days:
        logger.warning(f"Days parameter {days_int} below minimum {min_days}, using {min_days}")
        days_int = min_days
    elif days_int > max_days:
        logger.warning(f"Days parameter {days_int} above maximum {max_days}, using {max_days}")
        days_int = max_days
    
    return days_int


def parse_pagination_params(
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    default_limit: int = 50,
    max_limit: int = 200
) -> Tuple[int, int]:
    """
    Parse pagination parameters from either limit/offset or page/per_page.
    
    Args:
        limit: Limit parameter
        offset: Offset parameter
        page: Page number (1-indexed)
        per_page: Items per page
        default_limit: Default limit if not provided
        max_limit: Maximum allowed limit
        
    Returns:
        Tuple of (limit, offset)
    """
    # Handle page/per_page style
    if page is not None and per_page is not None:
        if page < 1:
            page = 1
        if per_page < 1:
            per_page = default_limit
        if per_page > max_limit:
            per_page = max_limit
        offset = (page - 1) * per_page
        limit = per_page
    
    # Handle limit/offset style
    if limit is None:
        limit = default_limit
    if offset is None:
        offset = 0
    
    # Validate
    if limit < 1:
        limit = default_limit
    if limit > max_limit:
        limit = max_limit
    if offset < 0:
        offset = 0
    
    return limit, offset


def parse_sort_params(
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
    allowed_fields: Optional[list] = None,
    default_field: str = "created_at",
    default_order: str = "desc"
) -> Tuple[str, str]:
    """
    Parse and validate sorting parameters.
    
    Args:
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        allowed_fields: List of allowed field names
        default_field: Default field if not provided or invalid
        default_order: Default order if not provided or invalid
        
    Returns:
        Tuple of (sort_field, sort_order)
    """
    # Validate sort_by
    if not sort_by:
        sort_by = default_field
    elif allowed_fields and sort_by not in allowed_fields:
        logger.warning(f"Invalid sort_by field: {sort_by}, using default: {default_field}")
        sort_by = default_field
    
    # Validate sort_order
    if not sort_order:
        sort_order = default_order
    elif sort_order.lower() not in ["asc", "desc"]:
        logger.warning(f"Invalid sort_order: {sort_order}, using default: {default_order}")
        sort_order = default_order
    else:
        sort_order = sort_order.lower()
    
    return sort_by, sort_order
