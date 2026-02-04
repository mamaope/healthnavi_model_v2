"""
Admin API endpoints for Empirico AI CDSS.
Provides dashboard metrics, alerts, and admin functionality.
"""

import logging
import json
from datetime import datetime
from typing import Optional, Union, Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import text

from healthnavi.core.database import get_db
from healthnavi.core.response_utils import create_success_response, create_error_response, ResponseTimer
from healthnavi.models.user import User
from healthnavi.api.v1.auth import require_admin_role, get_password_hash
from healthnavi.services.admin_service import AdminService
from healthnavi.models.admin import SafetyEvent, Survey, Alert, AuditLog, SafetyEventStatus, SafetyEventSeverity, DeviceActivityLog
from healthnavi.schemas import StandardResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_user_ids(user_ids: Optional[str]) -> Optional[list]:
    """Parse comma-separated user IDs from query param."""
    if not user_ids or not user_ids.strip():
        return None
    try:
        ids = [int(x.strip()) for x in user_ids.split(",") if x.strip()]
        return ids if ids else None
    except ValueError:
        return None


@router.get("/metrics", response_model=StandardResponse)
async def get_admin_metrics(
    days: str = Query("30", description="Number of days to analyze (used if start_date/end_date not provided)"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD for exact range"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD for exact range"),
    user_ids: Optional[str] = Query(None, description="Comma-separated user IDs to include (optional)"),
    exclude_user_ids: Optional[str] = Query(None, description="Comma-separated user IDs to exclude from statistics"),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """
    Get all admin dashboard metrics. Filter by date range and optionally include only certain users or exclude users.
    """
    with ResponseTimer() as timer:
        try:
            from healthnavi.core.query_utils import parse_days_parameter, parse_date_range
            days_int = parse_days_parameter(days, default=30, min_days=1, max_days=365)
            period_start, period_end = parse_date_range(start_date, end_date)
            user_ids_list = _parse_user_ids(user_ids)
            excluded_list = _parse_user_ids(exclude_user_ids)
            service = AdminService(db)
            metrics = service.get_all_metrics(
                days=days_int,
                period_start=period_start,
                period_end=period_end,
                user_ids=user_ids_list,
                exclude_user_ids=excluded_list,
            )
            service.log_audit_event(
                user_id=current_user.id,
                action="admin_metrics_viewed",
                description=f"Viewed admin metrics (days={days_int}, start_date={start_date}, end_date={end_date}, user_ids={user_ids})"
            )
            return create_success_response(
                data=metrics,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting admin metrics: {e}", exc_info=True)
            return create_error_response(
                message="Failed to retrieve admin metrics",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/feedback", response_model=StandardResponse)
async def get_feedback_list(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    user_ids: Optional[str] = Query(None, description="Comma-separated user IDs to include"),
    exclude_user_ids: Optional[str] = Query(None, description="Comma-separated user IDs to exclude"),
    feedback_type: Optional[str] = Query(None, description="helpful or not_helpful"),
    has_text_only: bool = Query(False, description="Only feedback with text comments"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    """List feedback comments for admin review. Supports date range and user filters."""
    with ResponseTimer() as timer:
        try:
            service = AdminService(db)
            result = service.get_feedback_list(
                start_date=start_date,
                end_date=end_date,
                user_ids=_parse_user_ids(user_ids),
                exclude_user_ids=_parse_user_ids(exclude_user_ids),
                feedback_type=feedback_type,
                has_text_only=has_text_only,
                limit=limit,
                offset=offset,
            )
            return create_success_response(
                data=result,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting feedback list: {e}", exc_info=True)
            return create_error_response(
                message="Failed to retrieve feedback",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/export/report")
async def export_report(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    user_ids: Optional[str] = Query(None, description="Comma-separated user IDs to include"),
    exclude_user_ids: Optional[str] = Query(None, description="Comma-separated user IDs to exclude"),
    active_users_only: bool = Query(False, description="If true, include only users who have at least one session"),
    format: str = Query("json", description="json or csv"),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    """Export admin report based on current filters. Returns JSON or CSV download."""
    with ResponseTimer() as timer:
        try:
            service = AdminService(db)
            result = service.get_export_report(
                start_date=start_date,
                end_date=end_date,
                user_ids=_parse_user_ids(user_ids),
                exclude_user_ids=_parse_user_ids(exclude_user_ids),
                active_users_only=active_users_only,
                format=format.strip().lower() or "json",
            )
            if format.strip().lower() == "csv" and "content" in result:
                from fastapi.responses import Response
                return Response(
                    content=result["content"],
                    media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={result['filename']}"},
                )
            return create_success_response(
                data=result.get("report", result),
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error exporting report: {e}", exc_info=True)
            return create_error_response(
                message="Failed to export report",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/metrics/usage-over-time", response_model=StandardResponse)
async def get_usage_over_time(
    days: str = Query("30", description="Number of days (used if start_date/end_date not provided)"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    user_ids: Optional[str] = Query(None, description="Comma-separated user IDs to include"),
    exclude_user_ids: Optional[str] = Query(None, description="Comma-separated user IDs to exclude"),
    active_users_only: bool = Query(False, description="If true, include only users who have at least one session"),
    granularity: str = Query("day", description="day or week"),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    """Get usage time-series for charts: per-day active_users, sessions, messages."""
    with ResponseTimer() as timer:
        try:
            from healthnavi.core.query_utils import parse_days_parameter, parse_date_range
            days_int = parse_days_parameter(days, default=30, min_days=1, max_days=365)
            period_start, period_end = parse_date_range(start_date, end_date)
            service = AdminService(db)
            result = service.get_usage_over_time(
                days=days_int,
                period_start=period_start,
                period_end=period_end,
                user_ids=_parse_user_ids(user_ids),
                exclude_user_ids=_parse_user_ids(exclude_user_ids),
                active_users_only=active_users_only,
                granularity=granularity,
            )
            return create_success_response(
                data=result,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting usage over time: {e}", exc_info=True)
            return create_error_response(
                message="Failed to retrieve usage over time",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/metrics/usage", response_model=StandardResponse)
async def get_usage_metrics(
    days: str = Query("30", description="Number of days for statistics"),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """
    Get usage panel metrics.
    
    Example request:
        GET /api/v2/admin/metrics/usage?days=30
    
    Example response (200):
        {
            "success": 1,
            "data": {
                "daily_active_users": 150,
                "weekly_active_users": 450,
                "total_users": 1000,
                ...
            }
        }
    
    Error codes:
        - 401: Unauthorized
        - 403: Forbidden (not admin)
        - 500: Internal server error
    """
    with ResponseTimer() as timer:
        try:
            # Use utility function for days parsing
            from healthnavi.core.query_utils import parse_days_parameter
            days_int = parse_days_parameter(days, default=30, min_days=1, max_days=365)
            
            service = AdminService(db)
            metrics = service.get_usage_metrics(days=days_int)
            return create_success_response(
                data=metrics,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting usage metrics: {e}", exc_info=True)
            return create_error_response(
                message="Failed to retrieve usage metrics",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/metrics/clinical-value", response_model=dict)
async def get_clinical_value_metrics(
    days: str = Query("30", description="Number of days for statistics"),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """
    Get clinical value panel metrics.
    
    Example request:
        GET /api/v2/admin/metrics/clinical-value?days=30
    
    Example response (200):
        {
            "success": 1,
            "data": {
                "helpful_feedback_percentage": 85.5,
                "avg_usefulness_score": 4.2,
                ...
            }
        }
    
    Error codes:
        - 401: Unauthorized
        - 403: Forbidden (not admin)
        - 500: Internal server error
    """
    with ResponseTimer() as timer:
        try:
            # Use utility function for days parsing
            from healthnavi.core.query_utils import parse_days_parameter
            days_int = parse_days_parameter(days, default=30, min_days=1, max_days=365)
            
            service = AdminService(db)
            metrics = service.get_clinical_value_metrics(days=days_int)
            return create_success_response(
                data=metrics,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting clinical value metrics: {e}", exc_info=True)
            return create_error_response(
                message="Failed to retrieve clinical value metrics",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/metrics/safety", response_model=StandardResponse)
async def get_safety_metrics(
    days: str = Query("30", description="Number of days for statistics"),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """
    Get safety panel metrics.
    
    Example request:
        GET /api/v2/admin/metrics/safety?days=30
    
    Example response (200):
        {
            "success": 1,
            "data": {
                "flags_per_100_queries": 2.5,
                "open_safety_events": 5,
                ...
            }
        }
    
    Error codes:
        - 401: Unauthorized
        - 403: Forbidden (not admin)
        - 500: Internal server error
    """
    with ResponseTimer() as timer:
        try:
            # Use utility function for days parsing
            from healthnavi.core.query_utils import parse_days_parameter
            days_int = parse_days_parameter(days, default=30, min_days=1, max_days=365)
            
            service = AdminService(db)
            metrics = service.get_safety_metrics(days=days_int)
            return create_success_response(
                data=metrics,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting safety metrics: {e}", exc_info=True)
            return create_error_response(
                message="Failed to retrieve safety metrics",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/metrics/pmf", response_model=StandardResponse)
async def get_pmf_metrics(
    days: str = Query("30", description="Number of days for statistics"),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """
    Get Product-Market Fit panel metrics.
    
    Example request:
        GET /api/v2/admin/metrics/pmf?days=30
    
    Example response (200):
        {
            "success": 1,
            "data": {
                "heavy_users": 150,
                "users_active_week3": 200,
                ...
            }
        }
    
    Error codes:
        - 401: Unauthorized
        - 403: Forbidden (not admin)
        - 500: Internal server error
    """
    with ResponseTimer() as timer:
        try:
            # Use utility function for days parsing
            from healthnavi.core.query_utils import parse_days_parameter
            days_int = parse_days_parameter(days, default=30, min_days=1, max_days=365)
            
            service = AdminService(db)
            metrics = service.get_pmf_metrics(days=days_int)
            return create_success_response(
                data=metrics,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting PMF metrics: {e}", exc_info=True)
            return create_error_response(
                message="Failed to retrieve PMF metrics",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/metrics/devices", response_model=StandardResponse)
async def get_device_metrics(
    days: str = Query("30", description="Number of days for statistics"),
    debug: Optional[str] = Query(None, description="Set to 1 to include table_exists and raw_count"),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """
    Get device type statistics (phone, tablet, laptop) for the admin dashboard.
    ?debug=1 adds table_exists and raw_count for troubleshooting.
    """
    with ResponseTimer() as timer:
        try:
            from healthnavi.core.query_utils import parse_days_parameter
            days_int = parse_days_parameter(days, default=30, min_days=1, max_days=365)
            service = AdminService(db)
            data = service.get_device_statistics(days=days_int)
            if debug == "1":
                try:
                    raw = db.execute(text("SELECT count(*) FROM device_activity_log")).scalar()
                    data = {**data, "debug": {"table_exists": True, "raw_count": raw}}
                except Exception as e:
                    data = {**data, "debug": {"table_exists": False, "raw_count": 0, "error": str(e)}}
            return create_success_response(
                data=data,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting device metrics: {e}", exc_info=True)
            return create_error_response(
                message="Failed to retrieve device metrics",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.post("/metrics/devices/seed-test", response_model=StandardResponse)
async def seed_test_device_activity(
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """
    Insert one test row (laptop, login) into device_activity_log.
    Use this to verify the table exists and inserts work. Then refresh the Device Usage panel.
    """
    with ResponseTimer() as timer:
        try:
            service = AdminService(db)
            service.insert_test_device_activity(current_user.id)
            return create_success_response(
                data={"message": "Test row inserted. Refresh the Device Usage panel to see it."},
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error seeding test device activity: {e}", exc_info=True)
            return create_error_response(
                message=f"Failed to insert test row: {e}",
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
            from sqlalchemy import text, and_
            
            query = db.query(SafetyEvent)
            
            if status:
                # Convert string to enum and use direct enum comparison
                try:
                    status_enum = SafetyEventStatus[status.upper()]
                    query = query.filter(SafetyEvent.status == status_enum)
                except (KeyError, AttributeError):
                    # If invalid status, return empty results
                    query = query.filter(False)
            if severity:
                # Convert string to enum and use direct enum comparison
                try:
                    severity_enum = SafetyEventSeverity[severity.upper()]
                    query = query.filter(SafetyEvent.severity == severity_enum)
                except (KeyError, AttributeError):
                    # If invalid severity, return empty results
                    query = query.filter(False)
            
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


@router.get("/surveys/statistics", response_model=StandardResponse)
async def get_survey_statistics(
    days: str = Query("30", description="Number of days for statistics"),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """Get survey completion statistics."""
    with ResponseTimer() as timer:
        try:
            from healthnavi.core.query_utils import parse_days_parameter
            days_int = parse_days_parameter(days, default=30, min_days=1, max_days=365)
            
            service = AdminService(db)
            stats = service.get_survey_statistics(days=days_int)
            
            return create_success_response(
                data=stats,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting survey statistics: {e}", exc_info=True)
            return create_error_response(
                message="Failed to retrieve survey statistics",
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
    """Get survey responses with user information."""
    with ResponseTimer() as timer:
        try:
            from sqlalchemy import text
            query = db.query(Survey, User).join(User, Survey.user_id == User.id)
            
            if survey_type:
                query = query.filter(
                    text("LOWER(surveys.survey_type::text) = LOWER(:survey_type)").bindparams(survey_type=survey_type)
                )
            
            total = query.count()
            results = query.order_by(Survey.created_at.desc()).offset(offset).limit(limit).all()
            
            surveys_data = []
            for survey, user in results:
                survey_data = {
                    "id": survey.id,
                    "user_id": survey.user_id,
                    "user_name": user.full_name or user.username or user.email,
                    "user_email": user.email,
                    "survey_type": survey.survey_type.value,
                    "pmf_score": survey.pmf_score,
                    "very_disappointed": survey.very_disappointed,
                    "willingness_to_pay": survey.willingness_to_pay,
                    "replacement_behavior": survey.replacement_behavior,
                    "time_saved_minutes": survey.time_saved_minutes,
                    "usefulness_score": survey.usefulness_score,
                    "query_relevance": survey.query_relevance,
                    "survey_data": json.loads(survey.survey_data) if survey.survey_data else None,
                    "created_at": survey.created_at
                }
                surveys_data.append(survey_data)
            
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
            logger.error(f"Error getting surveys: {e}", exc_info=True)
            return create_error_response(
                message="Failed to retrieve surveys",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


# Pydantic models for user management
class UserUpdateRequest(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[str] = None
    medical_professional_type: Optional[str] = None
    full_name: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    new_password: str


@router.get("/users/statistics", response_model=StandardResponse)
async def get_user_statistics(
    days: str = Query("30", description="Number of days for statistics"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    user_ids: Optional[str] = Query(None, description="Comma-separated user IDs to include"),
    exclude_user_ids: Optional[str] = Query(None, description="Comma-separated user IDs to exclude"),
    active_users_only: bool = Query(False, description="If true, include only users who have at least one session"),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """Get user statistics by type and activity. Supports date range and include/exclude user filters."""
    with ResponseTimer() as timer:
        try:
            from healthnavi.core.query_utils import parse_days_parameter, parse_date_range
            days_int = parse_days_parameter(days, default=30, min_days=1, max_days=365)
            period_start, period_end = parse_date_range(start_date, end_date)
            service = AdminService(db)
            stats = service.get_user_statistics(
                days=days_int,
                period_start=period_start,
                period_end=period_end,
                user_ids=_parse_user_ids(user_ids),
                exclude_user_ids=_parse_user_ids(exclude_user_ids),
                active_users_only=active_users_only,
            )
            return create_success_response(
                data=stats,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except ValueError as ve:
            logger.error(f"ValueError in get_user_statistics: {ve}", exc_info=True)
            return create_error_response(
                message=f"Invalid parameter: {str(ve)}",
                status_code=400,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}", exc_info=True)
            return create_error_response(
                message="Failed to retrieve user statistics",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/users", response_model=StandardResponse)
async def get_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    role: Optional[str] = Query(None, description="Filter by role"),
    medical_professional_type: Optional[str] = Query(None, description="Filter by professional type"),
    search: Optional[str] = Query(None, description="Search by email, username, or name"),
    sort_by: Optional[str] = Query("created_at", description="Field to sort by (id, email, username, created_at)"),
    sort_order: Optional[str] = Query("desc", description="Sort order (asc, desc)"),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """
    Get users with filters, pagination, and sorting.
    
    Example request:
        GET /api/v2/admin/users?limit=20&offset=0&is_active=true&sort_by=created_at&sort_order=desc
    
    Example response (200):
        {
            "success": 1,
            "data": {
                "users": [...],
                "total": 1000
            }
        }
    
    Error codes:
        - 401: Unauthorized
        - 403: Forbidden (not admin)
        - 500: Internal server error
    """
    with ResponseTimer() as timer:
        try:
            # Sanitize search query
            from healthnavi.core.security_utils import sanitize_search_query
            sanitized_search = sanitize_search_query(search) if search else None
            
            # Validate and parse sort parameters
            from healthnavi.core.query_utils import parse_sort_params
            allowed_sort_fields = ["id", "email", "username", "created_at", "updated_at"]
            sort_field, sort_order = parse_sort_params(
                sort_by=sort_by,
                sort_order=sort_order,
                allowed_fields=allowed_sort_fields,
                default_field="created_at",
                default_order="desc"
            )
            
            service = AdminService(db)
            result = service.get_users(
                limit=limit,
                offset=offset,
                is_active=is_active,
                role=role,
                medical_professional_type=medical_professional_type,
                search=sanitized_search,
                sort_by=sort_field,
                sort_order=sort_order
            )
            
            service.log_audit_event(
                user_id=current_user.id,
                action="users_viewed",
                description=f"Viewed users list (limit={limit}, offset={offset})"
            )
            
            return create_success_response(
                data=result,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return create_error_response(
                message="Failed to retrieve users",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/users/{user_id}", response_model=StandardResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """Get a specific user by ID."""
    with ResponseTimer() as timer:
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return create_error_response(
                    message="User not found",
                    status_code=404,
                    execution_time=timer.get_execution_time()
                )
            
            # Get user statistics
            from healthnavi.models.diagnosis_session import DiagnosisSession, ChatMessage
            from sqlalchemy import func
            
            session_count = db.query(func.count(DiagnosisSession.id)).filter(
                DiagnosisSession.user_id == user.id
            ).scalar() or 0
            
            message_count = db.query(func.count(ChatMessage.id)).join(
                DiagnosisSession, DiagnosisSession.id == ChatMessage.session_id
            ).filter(DiagnosisSession.user_id == user.id).scalar() or 0
            
            user_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "medical_professional_type": user.medical_professional_type,
                "is_active": user.is_active,
                "is_email_verified": user.is_email_verified,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "session_count": session_count,
                "message_count": message_count
            }
            
            return create_success_response(
                data=user_data,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return create_error_response(
                message="Failed to retrieve user",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.put("/users/{user_id}", response_model=StandardResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdateRequest,
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """Update user information."""
    with ResponseTimer() as timer:
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return create_error_response(
                    message="User not found",
                    status_code=404,
                    execution_time=timer.get_execution_time()
                )
            
            # Update fields
            if user_data.is_active is not None:
                user.is_active = user_data.is_active
            if user_data.role is not None:
                user.role = user_data.role
            if user_data.medical_professional_type is not None:
                user.medical_professional_type = user_data.medical_professional_type
            if user_data.full_name is not None:
                user.full_name = user_data.full_name
            
            user.updated_at = datetime.utcnow().isoformat()
            db.commit()
            db.refresh(user)
            
            service = AdminService(db)
            service.log_audit_event(
                user_id=current_user.id,
                action="user_updated",
                resource_type="user",
                resource_id=user_id,
                description=f"Updated user {user_id}: {user_data.dict(exclude_none=True)}"
            )
            
            return create_success_response(
                data={
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "is_active": user.is_active,
                    "role": user.role
                },
                status_code=200,
                message="User updated successfully",
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            db.rollback()
            return create_error_response(
                message="Failed to update user",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.post("/users/{user_id}/change-password", response_model=StandardResponse)
async def change_user_password(
    user_id: int,
    password_data: PasswordChangeRequest,
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """Change a user's password (admin action)."""
    with ResponseTimer() as timer:
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return create_error_response(
                    message="User not found",
                    status_code=404,
                    execution_time=timer.get_execution_time()
                )
            
            # Validate password length
            if len(password_data.new_password) < 8:
                return create_error_response(
                    message="Password must be at least 8 characters long",
                    status_code=400,
                    execution_time=timer.get_execution_time()
                )
            
            # Hash and update password
            user.hashed_password = get_password_hash(password_data.new_password)
            user.updated_at = datetime.utcnow().isoformat()
            db.commit()
            
            service = AdminService(db)
            service.log_audit_event(
                user_id=current_user.id,
                action="user_password_changed",
                resource_type="user",
                resource_id=user_id,
                description=f"Admin changed password for user {user_id}"
            )
            
            return create_success_response(
                data={"id": user.id},
                status_code=200,
                message="Password changed successfully",
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error changing user password: {e}")
            db.rollback()
            return create_error_response(
                message="Failed to change password",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/sessions/statistics", response_model=StandardResponse)
async def get_session_statistics(
    days: str = Query("30", description="Number of days for statistics"),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """
    Get session statistics.
    
    Example request:
        GET /api/v2/admin/sessions/statistics?days=30
    
    Example response (200):
        {
            "success": 1,
            "data": {
                "total_sessions": 5000,
                "active_sessions": 1200,
                "avg_session_length": 15.5,
                ...
            }
        }
    
    Error codes:
        - 401: Unauthorized
        - 403: Forbidden (not admin)
        - 500: Internal server error
    """
    with ResponseTimer() as timer:
        try:
            # Use utility function for days parsing
            from healthnavi.core.query_utils import parse_days_parameter
            days_int = parse_days_parameter(days, default=30, min_days=1, max_days=365)
            
            service = AdminService(db)
            stats = service.get_session_statistics(days=days_int)
            return create_success_response(
                data=stats,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting session statistics: {e}", exc_info=True)
            return create_error_response(
                message="Failed to retrieve session statistics",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/ai-responses/statistics", response_model=StandardResponse)
async def get_ai_response_statistics(
    days: str = Query("30", description="Number of days for statistics"),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """
    Get AI response statistics.
    
    Example request:
        GET /api/v2/admin/ai-responses/statistics?days=30
    
    Example response (200):
        {
            "success": 1,
            "data": {
                "total_responses": 10000,
                "helpful_count": 8500,
                "not_helpful_count": 1500,
                "helpful_percentage": 85.0,
                ...
            }
        }
    
    Error codes:
        - 401: Unauthorized
        - 403: Forbidden (not admin)
        - 500: Internal server error
    """
    with ResponseTimer() as timer:
        try:
            # Use utility function for days parsing
            from healthnavi.core.query_utils import parse_days_parameter
            days_int = parse_days_parameter(days, default=30, min_days=1, max_days=365)
            
            service = AdminService(db)
            stats = service.get_ai_response_statistics(days=days_int)
            return create_success_response(
                data=stats,
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting AI response statistics: {e}", exc_info=True)
            return create_error_response(
                message="Failed to retrieve AI response statistics",
                status_code=500,
                execution_time=timer.get_execution_time()
            )
