"""
Admin API endpoints for HealthNavi AI CDSS.
Provides dashboard metrics, alerts, and admin functionality.
"""

import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from healthnavi.core.database import get_db
from healthnavi.core.response_utils import create_success_response, create_error_response, ResponseTimer
from healthnavi.models.user import User
from healthnavi.api.v1.auth import require_admin_role
from healthnavi.services.admin_service import AdminService
from healthnavi.models.admin import SafetyEvent, Survey, Alert, AuditLog
from healthnavi.schemas import StandardResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/metrics", response_model=StandardResponse)
async def get_admin_metrics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """Get all admin dashboard metrics."""
    with ResponseTimer() as timer:
        try:
            service = AdminService(db)
            metrics = service.get_all_metrics(days=days)
            
            # Log admin access
            service.log_audit_event(
                user_id=current_user.id,
                action="admin_metrics_viewed",
                description=f"Viewed admin metrics for {days} days"
            )
            
            return create_success_response(
                data=metrics,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting admin metrics: {e}")
            return create_error_response(
                message="Failed to retrieve admin metrics",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/metrics/usage", response_model=StandardResponse)
async def get_usage_metrics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """Get usage panel metrics."""
    with ResponseTimer() as timer:
        try:
            service = AdminService(db)
            metrics = service.get_usage_metrics(days=days)
            return create_success_response(
                data=metrics,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting usage metrics: {e}")
            return create_error_response(
                message="Failed to retrieve usage metrics",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/metrics/clinical-value", response_model=dict)
async def get_clinical_value_metrics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """Get clinical value panel metrics."""
    with ResponseTimer() as timer:
        try:
            service = AdminService(db)
            metrics = service.get_clinical_value_metrics(days=days)
            return create_success_response(
                data=metrics,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting clinical value metrics: {e}")
            return create_error_response(
                message="Failed to retrieve clinical value metrics",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/metrics/safety", response_model=StandardResponse)
async def get_safety_metrics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """Get safety panel metrics."""
    with ResponseTimer() as timer:
        try:
            service = AdminService(db)
            metrics = service.get_safety_metrics(days=days)
            return create_success_response(
                data=metrics,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting safety metrics: {e}")
            return create_error_response(
                message="Failed to retrieve safety metrics",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/metrics/pmf", response_model=StandardResponse)
async def get_pmf_metrics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """Get Product-Market Fit panel metrics."""
    with ResponseTimer() as timer:
        try:
            service = AdminService(db)
            metrics = service.get_pmf_metrics(days=days)
            return create_success_response(
                data=metrics,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting PMF metrics: {e}")
            return create_error_response(
                message="Failed to retrieve PMF metrics",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/alerts", response_model=StandardResponse)
async def get_alerts(
    unread_only: bool = Query(False, description="Return only unread alerts"),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """Get all alerts."""
    with ResponseTimer() as timer:
        try:
            query = db.query(Alert)
            if unread_only:
                query = query.filter(Alert.is_read == False)
            
            alerts = query.order_by(Alert.created_at.desc()).limit(100).all()
            
            alerts_data = [{
                "id": alert.id,
                "alert_type": alert.alert_type,
                "severity": alert.severity.value,
                "title": alert.title,
                "message": alert.message,
                "is_read": alert.is_read,
                "is_resolved": alert.is_resolved,
                "created_at": alert.created_at,
                "safety_event_id": alert.safety_event_id
            } for alert in alerts]
            
            return create_success_response(
                data={"alerts": alerts_data, "count": len(alerts_data)},
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            return create_error_response(
                message="Failed to retrieve alerts",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.post("/alerts/check", response_model=StandardResponse)
async def check_alerts(
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """Manually trigger alert checking."""
    with ResponseTimer() as timer:
        try:
            service = AdminService(db)
            alerts_created = service.check_and_create_alerts()
            
            service.log_audit_event(
                user_id=current_user.id,
                action="alerts_checked",
                description=f"Manually triggered alert check, created {len(alerts_created)} alerts"
            )
            
            return create_success_response(
                data={"alerts_created": len(alerts_created)},
                status_code=200,
                message=f"Alert check completed. {len(alerts_created)} new alerts created.",
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
            return create_error_response(
                message="Failed to check alerts",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.put("/alerts/{alert_id}/read", response_model=StandardResponse)
async def mark_alert_read(
    alert_id: int,
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """Mark an alert as read."""
    with ResponseTimer() as timer:
        try:
            alert = db.query(Alert).filter(Alert.id == alert_id).first()
            if not alert:
                return create_error_response(
                    message="Alert not found",
                    status_code=404,
                    execution_time=timer.get_execution_time()
                )
            
            alert.is_read = True
            alert.read_by = current_user.id
            alert.updated_at = datetime.utcnow().isoformat()
            db.commit()
            
            service = AdminService(db)
            service.log_audit_event(
                user_id=current_user.id,
                action="alert_marked_read",
                resource_type="alert",
                resource_id=alert_id
            )
            
            return create_success_response(
                data={"id": alert.id, "is_read": True},
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error marking alert as read: {e}")
            db.rollback()
            return create_error_response(
                message="Failed to mark alert as read",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/audit-logs", response_model=StandardResponse)
async def get_audit_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    action: Optional[str] = Query(None, description="Filter by action"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """Get audit logs."""
    with ResponseTimer() as timer:
        try:
            query = db.query(AuditLog)
            
            if action:
                query = query.filter(AuditLog.action == action)
            if user_id:
                query = query.filter(AuditLog.user_id == user_id)
            
            total = query.count()
            logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
            
            logs_data = [{
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "description": log.description,
                "ip_address": log.ip_address,
                "created_at": log.created_at,
                "metadata": log.event_metadata
            } for log in logs]
            
            return create_success_response(
                data={
                    "logs": logs_data,
                    "total": total,
                    "limit": limit,
                    "offset": offset
                },
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting audit logs: {e}")
            return create_error_response(
                message="Failed to retrieve audit logs",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/safety-events", response_model=StandardResponse)
async def get_safety_events(
    status: Optional[str] = Query(None, description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """Get safety events."""
    with ResponseTimer() as timer:
        try:
            query = db.query(SafetyEvent)
            
            if status:
                query = query.filter(SafetyEvent.status == status)
            if severity:
                query = query.filter(SafetyEvent.severity == severity)
            
            total = query.count()
            events = query.order_by(SafetyEvent.created_at.desc()).offset(offset).limit(limit).all()
            
            events_data = [{
                "id": event.id,
                "user_id": event.user_id,
                "message_id": event.message_id,
                "session_id": event.session_id,
                "severity": event.severity.value,
                "status": event.status.value,
                "title": event.title,
                "description": event.description,
                "event_type": event.event_type,
                "is_critical": event.is_critical,
                "has_guideline_citation": event.has_guideline_citation,
                "was_red_flag_queried": event.was_red_flag_queried,
                "was_red_flag_correctly_flagged": event.was_red_flag_correctly_flagged,
                "created_at": event.created_at,
                "updated_at": event.updated_at
            } for event in events]
            
            return create_success_response(
                data={
                    "events": events_data,
                    "total": total,
                    "limit": limit,
                    "offset": offset
                },
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting safety events: {e}")
            return create_error_response(
                message="Failed to retrieve safety events",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/surveys", response_model=StandardResponse)
async def get_surveys(
    survey_type: Optional[str] = Query(None, description="Filter by survey type"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """Get survey responses."""
    with ResponseTimer() as timer:
        try:
            query = db.query(Survey)
            
            if survey_type:
                query = query.filter(Survey.survey_type == survey_type)
            
            total = query.count()
            surveys = query.order_by(Survey.created_at.desc()).offset(offset).limit(limit).all()
            
            surveys_data = [{
                "id": survey.id,
                "user_id": survey.user_id,
                "survey_type": survey.survey_type.value,
                "pmf_score": survey.pmf_score,
                "very_disappointed": survey.very_disappointed,
                "willingness_to_pay": survey.willingness_to_pay,
                "replacement_behavior": survey.replacement_behavior,
                "time_saved_minutes": survey.time_saved_minutes,
                "usefulness_score": survey.usefulness_score,
                "query_relevance": survey.query_relevance,
                "created_at": survey.created_at
            } for survey in surveys]
            
            return create_success_response(
                data={
                    "surveys": surveys_data,
                    "total": total,
                    "limit": limit,
                    "offset": offset
                },
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting surveys: {e}")
            return create_error_response(
                message="Failed to retrieve surveys",
                status_code=500,
                execution_time=timer.get_execution_time()
            )
