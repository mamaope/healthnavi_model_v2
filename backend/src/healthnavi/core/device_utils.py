"""
Device detection utilities for logging device type (phone, tablet, laptop).
Uses X-Device-Type header when provided by clients, otherwise infers from User-Agent.
"""
import re

# User-Agent patterns (order matters: tablet before phone for Android)
_UA_TABLET = re.compile(
    r"iPad|Android(?!.*Mobile)|Tablet|Kindle|Silk|PlayBook|webOS",
    re.IGNORECASE
)
_UA_PHONE = re.compile(
    r"Mobile|Android|iPhone|iPod|webOS|BlackBerry|IEMobile|Opera Mini|MiuiBrowser",
    re.IGNORECASE
)


def get_device_type(request) -> str:
    """
    Determine device type from request.
    Prefers X-Device-Type header (phone, tablet, laptop). Falls back to User-Agent.
    """
    # 1. Explicit header from frontend/mobile
    raw = (request.headers.get("X-Device-Type") or "").strip().lower()
    if raw in (DEVICE_PHONE, DEVICE_TABLET, DEVICE_LAPTOP):
        return raw

    # 2. Infer from User-Agent
    ua = request.headers.get("User-Agent") or ""
    if _UA_TABLET.search(ua):
        return DEVICE_TABLET
    if _UA_PHONE.search(ua):
        return DEVICE_PHONE
    return DEVICE_LAPTOP  # treat desktop browsers as laptop
