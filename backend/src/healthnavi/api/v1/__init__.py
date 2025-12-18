"""
API v1 endpoints.
"""

from . import auth, diagnosis, chat_sessions

# Conditionally import transcription (requires whisper/torch)
try:
    from . import transcription
    __all__ = ["auth", "diagnosis", "chat_sessions", "transcription"]
except ImportError:
    # Transcription not available - whisper/torch not installed
    __all__ = ["auth", "diagnosis", "chat_sessions"]
