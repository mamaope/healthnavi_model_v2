"""
Data deletion service for Empirico AI CDSS.

Supports user-initiated data deletion requests for privacy compliance (e.g. GDPR right to erasure).
Deletion is scheduled 6 months after the request to allow for a change-of-mind period.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from healthnavi.models.user import User
from healthnavi.models.diagnosis_session import DiagnosisSession
from healthnavi.models.admin import SafetyEvent, Survey, AuditLog, Alert

logger = logging.getLogger(__name__)

# Deletion is processed 6 months after the user's request
DELETION_DELAY_MONTHS = 6


def request_data_deletion(db: Session, user: User) -> Tuple[bool, str]:
    """
    Record that the user has requested deletion of their data.
    Deletion will be processed 6 months from now. The user can cancel before then.

    Returns:
        (success: bool, message: str)
    """
    try:
        if user.deletion_requested_at:
            return False, "A deletion request is already pending. It will be processed 6 months from your original request."
        user.deletion_requested_at = datetime.utcnow().isoformat()
        user.updated_at = datetime.utcnow().isoformat()
        db.commit()
        db.refresh(user)
        logger.info(f"User {user.id} ({user.email}) requested data deletion. Will be processed in {DELETION_DELAY_MONTHS} months.")
        return True, f"Your data deletion has been scheduled. Your data will be permanently removed 6 months from today. You may cancel this request at any time before then."
    except Exception as e:
        logger.error(f"Error requesting data deletion for user {user.id}: {e}")
        db.rollback()
        return False, "Failed to submit deletion request. Please try again."


def cancel_data_deletion(db: Session, user: User) -> Tuple[bool, str]:
    """
    Cancel a pending data deletion request.

    Returns:
        (success: bool, message: str)
    """
    try:
        if not user.deletion_requested_at:
            return False, "No pending deletion request found."
        user.deletion_requested_at = None
        user.updated_at = datetime.utcnow().isoformat()
        db.commit()
        db.refresh(user)
        logger.info(f"User {user.id} ({user.email}) cancelled their data deletion request.")
        return True, "Your data deletion request has been cancelled. Your data will be retained."
    except Exception as e:
        logger.error(f"Error cancelling data deletion for user {user.id}: {e}")
        db.rollback()
        return False, "Failed to cancel deletion request. Please try again."


def get_deletion_status(user: User) -> dict:
    """
    Return the current deletion status for the user.

    Returns:
        {
            "pending": bool,
            "requested_at": str | None,
            "scheduled_deletion_at": str | None  # ISO datetime, 6 months after request
        }
    """
    if not user.deletion_requested_at:
        return {"pending": False, "requested_at": None, "scheduled_deletion_at": None}
    try:
        requested = datetime.fromisoformat(user.deletion_requested_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        requested = datetime.utcnow()
    scheduled = requested + timedelta(days=30 * DELETION_DELAY_MONTHS)
    return {
        "pending": True,
        "requested_at": user.deletion_requested_at,
        "scheduled_deletion_at": scheduled.isoformat(),
    }


def _delete_user_data(db: Session, user: User) -> None:
    """
    Permanently delete all data associated with a user.
    Handles FKs in the correct order: Alert, SafetyEvent, Survey, AuditLog, then User
    (User cascade deletes DiagnosisSession -> ChatMessage -> MessageFeedback).
    """
    uid = user.id
    session_ids = [s.id for s in user.diagnosis_sessions]

    # 1. Alerts that reference SafetyEvents we are about to delete
    safety_q = SafetyEvent.user_id == uid
    if session_ids:
        safety_q = safety_q | (SafetyEvent.session_id.in_(session_ids))
    safety_event_ids = [r[0] for r in db.query(SafetyEvent.id).filter(safety_q).all()]
    if safety_event_ids:
        db.query(Alert).filter(Alert.safety_event_id.in_(safety_event_ids)).delete(synchronize_session=False)

    # 2. SafetyEvent: clear resolved_by when it references this user, then delete events for this user/sessions
    db.query(SafetyEvent).filter(SafetyEvent.resolved_by == uid).update({"resolved_by": None}, synchronize_session=False)
    db.query(SafetyEvent).filter(safety_q).delete(synchronize_session=False)

    # 3. Alert: clear read_by and resolved_by when they reference this user (for alerts we keep)
    db.query(Alert).filter(Alert.read_by == uid).update({"read_by": None}, synchronize_session=False)
    db.query(Alert).filter(Alert.resolved_by == uid).update({"resolved_by": None}, synchronize_session=False)

    # 4. Survey
    db.query(Survey).filter(Survey.user_id == uid).delete(synchronize_session=False)

    # 5. AuditLog
    db.query(AuditLog).filter(AuditLog.user_id == uid).delete(synchronize_session=False)

    # 6. User (cascades to DiagnosisSession -> ChatMessage -> MessageFeedback)
    db.delete(user)


def process_pending_deletions(db: Session) -> int:
    """
    Find users whose deletion_requested_at is at least 6 months ago and
    permanently delete their data. Uses a single DB session.

    Returns:
        Number of users whose data was deleted.
    """
    threshold = (datetime.utcnow() - timedelta(days=30 * DELETION_DELAY_MONTHS)).isoformat()
    # Compare as strings only if we store ISO format that sorts lexicographically (we do)
    users_to_delete = db.query(User).filter(
        User.deletion_requested_at.isnot(None),
        User.deletion_requested_at <= threshold,
    ).all()

    deleted = 0
    for user in users_to_delete:
        try:
            email = user.email
            _delete_user_data(db, user)
            db.commit()
            deleted += 1
            logger.info(f"Permanently deleted all data for user (former email: {email}) per deferred deletion request.")
        except Exception as e:
            logger.exception(f"Error deleting data for user {user.id}: {e}")
            db.rollback()
    return deleted
