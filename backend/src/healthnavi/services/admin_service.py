"""
Admin Service for HealthNavi AI CDSS.
Provides metrics, analytics, and admin functionality.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, case, String, text
from sqlalchemy.sql import label

from healthnavi.models.user import User
from healthnavi.models.diagnosis_session import DiagnosisSession, ChatMessage, MessageFeedback
from healthnavi.models.admin import SafetyEvent, Survey, Alert, AuditLog, SafetyEventSeverity, SafetyEventStatus, SurveyType, DeviceActivityLog

logger = logging.getLogger(__name__)

# Human-readable names and how each metric is calculated (for export reports)
METRIC_META = {
    "usage.daily_active_users": ("Daily active users", "Number of unique users who had at least one chat session today."),
    "usage.weekly_active_users": ("Weekly active users", "Number of unique users who had at least one chat session in the last 7 days."),
    "usage.activated_users": ("Activated users", "Number of users who have ever started at least one chat session."),
    "usage.total_users": ("Total users", "Total number of user accounts in the system."),
    "usage.activation_rate": ("Activation rate (%)", "Percentage of all users who have started at least one session (activated users ÷ total users × 100)."),
    "usage.queries_per_clinician": ("Average queries per user", "Average number of user messages (queries) per user in the period."),
    "usage.sessions_per_user": ("Average sessions per user", "Average number of chat sessions per user in the period."),
    "usage.retention_week1_to_week3": ("Retention rate (%)", "Of users active in week 1 (7–14 days ago), the percentage who were also active in week 3 (last 7 days)."),
    "usage.week1_users": ("Week 1 users", "Number of unique users active in the window 7–14 days ago."),
    "usage.week3_active_users": ("Week 3 active users", "Of Week 1 users, how many were also active in the last 7 days."),
    "clinical_value.helpful_feedback_percentage": ("Helpful feedback (%)", "Percentage of all feedback that was marked as helpful."),
    "clinical_value.total_feedback": ("Total feedback count", "Total number of feedback submissions in the period."),
    "clinical_value.helpful_feedback": ("Helpful feedback count", "Number of feedback submissions marked as helpful."),
    "clinical_value.not_helpful_feedback": ("Not helpful feedback count", "Number of feedback submissions marked as not helpful."),
    "clinical_value.avg_usefulness_score": ("Average usefulness score", "Average rating (1–5) given by users when submitting feedback."),
    "clinical_value.relevant_queries_percentage": ("Relevant queries (%)", "From surveys: percentage of queries users said were relevant to their work."),
    "clinical_value.avg_time_saved_minutes": ("Average time saved (minutes)", "From surveys: average minutes saved per session reported by users."),
    "safety.total_queries": ("Total user queries", "Total number of user messages in the period."),
    "safety.total_flags": ("Safety flags", "Number of safety events or flags raised in the period."),
    "safety.flags_per_100_queries": ("Flags per 100 queries", "Safety flags per 100 user queries (rate)."),
    "safety.open_safety_events": ("Open safety events", "Number of safety events currently in open status."),
    "safety.critical_incidents": ("Critical incidents", "Number of safety events marked as critical."),
    "safety.citations_percentage": ("Responses with citations (%)", "Percentage of AI responses that included guideline citations."),
    "safety.red_flag_accuracy_percentage": ("Red-flag accuracy (%)", "Of red-flag queries, percentage that were correctly flagged."),
    "pmf.heavy_users": ("Heavy users", "Users with more than 20 queries in the last 7 days."),
    "pmf.total_pmf_responses": ("PMF survey responses", "Number of Product-Market Fit survey responses in the period."),
    "pmf.very_disappointed_percentage": ("Very disappointed (%)", "Percentage of PMF respondents who said they would be very disappointed without the product."),
    "pmf.avg_pmf_score": ("Average PMF score", "Average score from PMF surveys."),
    "surveys.overall.total_completed": ("Surveys completed (overall)", "Total survey submissions in the period across all survey types."),
    "surveys.overall.total_unique_users_completed": ("Unique users who completed surveys", "Number of distinct users who submitted at least one survey in the period."),
    "surveys.overall.total_users": ("Total users (for survey stats)", "Total number of users in the system (used as denominator for completion rate)."),
    "surveys.overall.overall_completion_percentage": ("Survey completion rate (%)", "Percentage of total users who completed at least one survey."),
    "devices.total": ("Device log entries", "Total device activity log entries (e.g. logins, session creates) in the period."),
    "devices.by_type": ("Device breakdown", "Counts by device type (phone, tablet, laptop)."),
}


class AdminService:
    """Service for admin dashboard metrics and analytics."""
    
    def __init__(self, db: Session):
        self.db = db

    def _resolve_period(
        self,
        days: Optional[int] = 30,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
    ) -> tuple:
        """Return (period_start_iso, period_end_iso). If period_start/period_end given, use them; else derive from days."""
        if period_start and period_end:
            return period_start, period_end
        d = days if days is not None else 30
        now = datetime.utcnow()
        end = now.isoformat()
        start = (now - timedelta(days=d)).isoformat()
        return start, end
    
    def parse_datetime(self, date_str: str) -> Optional[datetime]:
        """Parse ISO datetime string to datetime object."""
        try:
            if 'T' in date_str:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return datetime.fromisoformat(date_str)
        except:
            return None
    
    def get_usage_metrics(
        self,
        days: Optional[int] = 30,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        user_ids: Optional[List[int]] = None,
        exclude_user_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Get usage panel metrics. Use period_start/period_end for exact date range, or days."""
        try:
            period_start, period_end = self._resolve_period(days, period_start, period_end)
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = today_start - timedelta(days=7)
            three_weeks_ago = today_start - timedelta(days=21)
            # Daily Active Users (DAU) - use subquery for distinct count
            dau_subquery = self.db.query(DiagnosisSession.user_id).filter(
                DiagnosisSession.created_at >= today_start.isoformat(),
                DiagnosisSession.created_at < (today_start + timedelta(days=1)).isoformat()
            )
            if user_ids:
                dau_subquery = dau_subquery.filter(DiagnosisSession.user_id.in_(user_ids))
            if exclude_user_ids:
                dau_subquery = dau_subquery.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
            dau_subquery = dau_subquery.distinct().subquery()
            dau = self.db.query(func.count(dau_subquery.c.user_id)).scalar() or 0
            
            # Weekly Active Users (WAU) - use subquery for distinct count
            wau_subquery = self.db.query(DiagnosisSession.user_id).filter(
                DiagnosisSession.created_at >= week_start.isoformat()
            )
            if user_ids:
                wau_subquery = wau_subquery.filter(DiagnosisSession.user_id.in_(user_ids))
            if exclude_user_ids:
                wau_subquery = wau_subquery.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
            wau_subquery = wau_subquery.distinct().subquery()
            wau = self.db.query(func.count(wau_subquery.c.user_id)).scalar() or 0
            
            # Activated users (users with at least one session)
            activated_q = self.db.query(DiagnosisSession.user_id).distinct()
            if exclude_user_ids:
                activated_q = activated_q.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
            activated_user_ids_list = [row[0] for row in activated_q.all() if row[0] is not None]
            if activated_user_ids_list:
                activated_users = self.db.query(func.count(User.id)).filter(
                    User.id.in_(activated_user_ids_list)
                ).scalar() or 0
            else:
                activated_users = 0

            # Total users (all users on the system, not just active)
            total_users_q = self.db.query(func.count(User.id))
            if exclude_user_ids:
                total_users_q = total_users_q.filter(User.id.notin_(exclude_user_ids))
            total_users = total_users_q.scalar() or 0
            
            # Queries per clinician (average messages per user)
            # Use subquery to count messages per user, then average
            # Note: created_at is stored as ISO string, compare as strings
            user_message_counts = self.db.query(
                DiagnosisSession.user_id,
                func.count(ChatMessage.id).label('message_count')
            ).join(
                ChatMessage, ChatMessage.session_id == DiagnosisSession.id
            ).filter(
                ChatMessage.message_type == 'user',
                text("diagnosis_sessions.created_at >= :period_start AND diagnosis_sessions.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end),
                text("diagnosis_sessions.created_at < :period_end").bindparams(period_end=period_end),
            )
            if user_ids:
                user_message_counts = user_message_counts.filter(DiagnosisSession.user_id.in_(user_ids))
            if exclude_user_ids:
                user_message_counts = user_message_counts.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
            user_message_counts = user_message_counts.group_by(DiagnosisSession.user_id).subquery()
            
            queries_per_clinician_result = self.db.query(
                func.avg(user_message_counts.c.message_count)
            ).scalar()
            queries_per_clinician = float(queries_per_clinician_result) if queries_per_clinician_result is not None else 0.0
            
            # Sessions per user (average)
            user_session_counts = self.db.query(
                DiagnosisSession.user_id,
                func.count(DiagnosisSession.id).label('session_count')
            ).filter(
                text("diagnosis_sessions.created_at >= :period_start AND diagnosis_sessions.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end),
                text("diagnosis_sessions.created_at < :period_end").bindparams(period_end=period_end),
            )
            if user_ids:
                user_session_counts = user_session_counts.filter(DiagnosisSession.user_id.in_(user_ids))
            if exclude_user_ids:
                user_session_counts = user_session_counts.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
            user_session_counts = user_session_counts.group_by(DiagnosisSession.user_id).subquery()
            
            sessions_per_user_result = self.db.query(
                func.avg(user_session_counts.c.session_count)
            ).scalar()
            sessions_per_user = float(sessions_per_user_result) if sessions_per_user_result is not None else 0.0
            
            # Retention: Week 1 → Week 3
            # Users active in week 1 (7-14 days ago)
            week1_start = (today_start - timedelta(days=14)).isoformat()
            week1_end = (today_start - timedelta(days=7)).isoformat()
            
            week1_user_ids_query = self.db.query(DiagnosisSession.user_id).filter(
                and_(
                    DiagnosisSession.created_at >= week1_start,
                    DiagnosisSession.created_at < week1_end
                )
            )
            if user_ids:
                week1_user_ids_query = week1_user_ids_query.filter(DiagnosisSession.user_id.in_(user_ids))
            if exclude_user_ids:
                week1_user_ids_query = week1_user_ids_query.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
            week1_user_ids = [row[0] for row in week1_user_ids_query.distinct().all() if row[0] is not None]
            week1_count = len(week1_user_ids)
            
            # Users from week 1 who were also active in week 3 (0-7 days ago)
            week3_start = (today_start - timedelta(days=7)).isoformat()
            if week1_user_ids:
                week3_subquery = self.db.query(DiagnosisSession.user_id).filter(
                    and_(
                        DiagnosisSession.user_id.in_(week1_user_ids),
                        DiagnosisSession.created_at >= week3_start
                    )
                ).distinct().subquery()
                week3_active = self.db.query(func.count(week3_subquery.c.user_id)).scalar() or 0
            else:
                week3_active = 0
            
            retention_rate = (week3_active / week1_count * 100) if week1_count > 0 else 0.0
            
            return {
                "daily_active_users": dau,
                "weekly_active_users": wau,
                "activated_users": activated_users,
                "total_users": total_users,
                "activation_rate": (activated_users / total_users * 100) if total_users > 0 else 0.0,
                "queries_per_clinician": round(queries_per_clinician, 2),
                "sessions_per_user": round(sessions_per_user, 2),
                "retention_week1_to_week3": round(retention_rate, 2),
                "week1_users": week1_count,
                "week3_active_users": week3_active
            }
        except Exception as e:
            logger.error(f"Error getting usage metrics: {e}")
            raise

    def get_usage_over_time(
        self,
        days: Optional[int] = 30,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        user_ids: Optional[List[int]] = None,
        exclude_user_ids: Optional[List[int]] = None,
        active_users_only: bool = False,
        granularity: str = "day",
    ) -> Dict[str, Any]:
        """Get usage time-series: per-day (or per-week) active_users, sessions, messages."""
        try:
            if active_users_only:
                active_ids = self._get_active_user_ids(user_ids=user_ids, exclude_user_ids=exclude_user_ids)
                user_ids = active_ids if active_ids else None
                exclude_user_ids = None
            period_start, period_end = self._resolve_period(days, period_start, period_end)
            # Fetch sessions in range
            sessions_q = self.db.query(
                DiagnosisSession.created_at,
                DiagnosisSession.user_id,
            ).filter(
                text("diagnosis_sessions.created_at >= :period_start AND diagnosis_sessions.created_at < :period_end").bindparams(
                    period_start=period_start, period_end=period_end
                )
            )
            if user_ids:
                sessions_q = sessions_q.filter(DiagnosisSession.user_id.in_(user_ids))
            if exclude_user_ids:
                sessions_q = sessions_q.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
            sessions_rows = sessions_q.all()
            # Bucket by date (YYYY-MM-DD)
            day_sessions = {}
            day_users = {}
            for created_at, uid in sessions_rows:
                if not created_at:
                    continue
                day = created_at[:10] if len(created_at) >= 10 else created_at.split("T")[0]
                day_sessions[day] = day_sessions.get(day, 0) + 1
                if day not in day_users:
                    day_users[day] = set()
                if uid is not None:
                    day_users[day].add(uid)
            # User messages (queries) per day - by message created_at
            messages_q = self.db.query(ChatMessage.created_at).join(
                DiagnosisSession, DiagnosisSession.id == ChatMessage.session_id
            ).filter(
                ChatMessage.message_type == "user",
                text("chat_messages.created_at >= :period_start AND chat_messages.created_at < :period_end").bindparams(
                    period_start=period_start, period_end=period_end
                )
            )
            if user_ids:
                messages_q = messages_q.filter(DiagnosisSession.user_id.in_(user_ids))
            if exclude_user_ids:
                messages_q = messages_q.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
            messages_rows = messages_q.all()
            day_messages = {}
            for (created_at,) in messages_rows:
                if not created_at:
                    continue
                day = created_at[:10] if len(created_at) >= 10 else created_at.split("T")[0]
                day_messages[day] = day_messages.get(day, 0) + 1
            # Build ordered list of dates in range
            try:
                start_dt = datetime.fromisoformat(period_start.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(period_end.replace("Z", "+00:00"))
            except Exception:
                start_dt = datetime.utcnow() - timedelta(days=days or 30)
                end_dt = datetime.utcnow()
            series = []
            current = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date_only = end_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            while current < end_date_only:
                day_str = current.strftime("%Y-%m-%d")
                series.append({
                    "date": day_str,
                    "active_users": len(day_users.get(day_str, set())),
                    "sessions": day_sessions.get(day_str, 0),
                    "messages": day_messages.get(day_str, 0),
                })
                current += timedelta(days=1)
            return {"series": series, "period_start": period_start, "period_end": period_end}
        except Exception as e:
            logger.error(f"Error getting usage over time: {e}", exc_info=True)
            raise
    
    def get_clinical_value_metrics(
        self,
        days: Optional[int] = 30,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        user_ids: Optional[List[int]] = None,
        exclude_user_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Get clinical value panel metrics."""
        try:
            period_start, period_end = self._resolve_period(days, period_start, period_end)

            def _fb_query():
                q = self.db.query(MessageFeedback).filter(
                    text("message_feedback.created_at >= :period_start AND message_feedback.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
                )
                if user_ids:
                    q = q.filter(MessageFeedback.user_id.in_(user_ids))
                if exclude_user_ids:
                    q = q.filter(MessageFeedback.user_id.notin_(exclude_user_ids))
                return q

            # Total feedback - use text() for string date comparison
            total_feedback = _fb_query().count()
            
            # Helpful feedback - use text() for string date comparison
            helpful_feedback = _fb_query().filter(MessageFeedback.feedback_type == 'helpful').count()
            
            helpful_percentage = (helpful_feedback / total_feedback * 100) if total_feedback > 0 else 0.0
            
            # Average usefulness score (rating) - use text() for string date comparison
            avg_rating_q = self.db.query(func.avg(MessageFeedback.rating)).filter(
                MessageFeedback.rating.isnot(None),
                text("message_feedback.created_at >= :period_start AND message_feedback.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
            )
            if user_ids:
                avg_rating_q = avg_rating_q.filter(MessageFeedback.user_id.in_(user_ids))
            if exclude_user_ids:
                avg_rating_q = avg_rating_q.filter(MessageFeedback.user_id.notin_(exclude_user_ids))
            avg_rating_result = avg_rating_q.scalar()
            avg_rating = float(avg_rating_result) if avg_rating_result is not None else 0.0
            
            def _survey_query(*extra_filters):
                q = self.db.query(Survey).filter(
                    text("surveys.created_at >= :period_start AND surveys.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
                )
                if user_ids:
                    q = q.filter(Survey.user_id.in_(user_ids))
                if exclude_user_ids:
                    q = q.filter(Survey.user_id.notin_(exclude_user_ids))
                for f in extra_filters:
                    q = q.filter(f)
                return q

            # Relevant queries (from surveys) - use text() for string date comparison
            relevant_queries = _survey_query(Survey.query_relevance == True).count()
            total_survey_queries = _survey_query(Survey.query_relevance.isnot(None)).count()
            relevant_percentage = (relevant_queries / total_survey_queries * 100) if total_survey_queries > 0 else 0.0
            
            # Average time saved (from surveys) - use text() for string date comparison
            avg_time_saved_q = self.db.query(func.avg(Survey.time_saved_minutes)).filter(
                Survey.time_saved_minutes.isnot(None),
                text("surveys.created_at >= :period_start AND surveys.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
            )
            if user_ids:
                avg_time_saved_q = avg_time_saved_q.filter(Survey.user_id.in_(user_ids))
            if exclude_user_ids:
                avg_time_saved_q = avg_time_saved_q.filter(Survey.user_id.notin_(exclude_user_ids))
            avg_time_saved_result = avg_time_saved_q.scalar()
            avg_time_saved = float(avg_time_saved_result) if avg_time_saved_result is not None else 0.0
            
            return {
                "helpful_feedback_percentage": round(helpful_percentage, 2),
                "total_feedback": total_feedback,
                "helpful_feedback": helpful_feedback,
                "not_helpful_feedback": total_feedback - helpful_feedback,
                "avg_usefulness_score": round(avg_rating, 2),
                "relevant_queries_percentage": round(relevant_percentage, 2),
                "total_survey_queries": total_survey_queries,
                "relevant_queries": relevant_queries,
                "avg_time_saved_minutes": round(avg_time_saved, 2)
            }
        except Exception as e:
            logger.error(f"Error getting clinical value metrics: {e}")
            raise
    
    def get_safety_metrics(
        self,
        days: Optional[int] = 30,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        user_ids: Optional[List[int]] = None,
        exclude_user_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Get safety panel metrics."""
        try:
            period_start, period_end = self._resolve_period(days, period_start, period_end)
            last_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()
            
            # Total queries in period - use text() for string date comparison
            total_queries_q = self.db.query(func.count(ChatMessage.id)).join(
                DiagnosisSession, DiagnosisSession.id == ChatMessage.session_id
            ).filter(
                ChatMessage.message_type == 'user',
                text("chat_messages.created_at >= :period_start AND chat_messages.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
            )
            if user_ids:
                total_queries_q = total_queries_q.filter(DiagnosisSession.user_id.in_(user_ids))
            if exclude_user_ids:
                total_queries_q = total_queries_q.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
            total_queries = total_queries_q.scalar() or 0
            
            # Total queries in last 24h - use text() for string date comparison
            queries_24h = self.db.query(func.count(ChatMessage.id)).filter(
                and_(
                    ChatMessage.message_type == 'user',
                    text("chat_messages.created_at >= :last_24h").bindparams(last_24h=last_24h)
                )
            ).scalar() or 0
            
            # Safety flags/events - use text() for string date comparison
            total_flags_q = self.db.query(func.count(SafetyEvent.id)).filter(
                text("safety_events.created_at >= :period_start AND safety_events.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
            )
            if exclude_user_ids:
                total_flags_q = total_flags_q.filter(SafetyEvent.user_id.notin_(exclude_user_ids))
            total_flags = total_flags_q.scalar() or 0
            
            flags_per_100_queries = (total_flags / total_queries * 100) if total_queries > 0 else 0.0
            
            # Open safety events - use text comparison to handle enum case issues
            # Cast enum to text and compare (works regardless of enum case in DB)
            open_events = self.db.query(func.count(SafetyEvent.id)).filter(
                text("LOWER(safety_events.status::text) = LOWER(:status)").bindparams(status=SafetyEventStatus.OPEN.value)
            ).scalar() or 0
            
            # Critical incidents - use text() for string date comparison
            critical_incidents = self.db.query(func.count(SafetyEvent.id)).filter(
                and_(
                    SafetyEvent.is_critical == True,
                    text("safety_events.created_at >= :period_start AND safety_events.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
                )
            ).scalar() or 0
            
            # Responses with guideline citations - use text() for string date comparison
            messages_with_citations = self.db.query(func.count(ChatMessage.id)).filter(
                and_(
                    ChatMessage.message_type == 'assistant',
                    ChatMessage.content.contains('citation') | ChatMessage.content.contains('guideline'),
                    text("chat_messages.created_at >= :period_start AND chat_messages.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
                )
            ).scalar() or 0
            
            total_assistant_messages = self.db.query(func.count(ChatMessage.id)).filter(
                and_(
                    ChatMessage.message_type == 'assistant',
                    text("chat_messages.created_at >= :period_start AND chat_messages.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
                )
            ).scalar() or 0
            
            citations_percentage = (messages_with_citations / total_assistant_messages * 100) if total_assistant_messages > 0 else 0.0
            
            # Red flag queries correctly flagged - use text() for string date comparison
            red_flag_events = self.db.query(func.count(SafetyEvent.id)).filter(
                and_(
                    SafetyEvent.was_red_flag_queried == True,
                    text("safety_events.created_at >= :period_start AND safety_events.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
                )
            ).scalar() or 0
            
            correctly_flagged = self.db.query(func.count(SafetyEvent.id)).filter(
                and_(
                    SafetyEvent.was_red_flag_queried == True,
                    SafetyEvent.was_red_flag_correctly_flagged == True,
                    text("safety_events.created_at >= :period_start AND safety_events.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
                )
            ).scalar() or 0
            
            red_flag_accuracy = (correctly_flagged / red_flag_events * 100) if red_flag_events > 0 else 0.0
            
            # Flag rate in last 24h - use text() for string date comparison
            flags_24h = self.db.query(func.count(SafetyEvent.id)).filter(
                text("safety_events.created_at >= :last_24h").bindparams(last_24h=last_24h)
            ).scalar() or 0
            
            flag_rate_24h = (flags_24h / queries_24h * 100) if queries_24h > 0 else 0.0
            
            return {
                "flags_per_100_queries": round(flags_per_100_queries, 2),
                "total_flags": total_flags,
                "total_queries": total_queries,
                "open_safety_events": open_events,
                "critical_incidents": critical_incidents,
                "citations_percentage": round(citations_percentage, 2),
                "red_flag_accuracy_percentage": round(red_flag_accuracy, 2),
                "red_flag_queries": red_flag_events,
                "correctly_flagged_red_flags": correctly_flagged,
                "flag_rate_24h": round(flag_rate_24h, 2),
                "flags_24h": flags_24h,
                "queries_24h": queries_24h
            }
        except Exception as e:
            logger.error(f"Error getting safety metrics: {e}")
            raise
    
    def get_pmf_metrics(
        self,
        days: Optional[int] = 30,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        user_ids: Optional[List[int]] = None,
        exclude_user_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Get Product-Market Fit panel metrics."""
        try:
            period_start, period_end = self._resolve_period(days, period_start, period_end)
            week_start = (datetime.utcnow() - timedelta(days=7)).isoformat()
            three_weeks_ago = (datetime.utcnow() - timedelta(days=21)).isoformat()
            two_weeks_ago = (datetime.utcnow() - timedelta(days=14)).isoformat()
            
            # Heavy users (>20 queries/week)
            user_message_counts_q = self.db.query(
                DiagnosisSession.user_id,
                func.count(ChatMessage.id).label('message_count')
            ).join(
                ChatMessage, ChatMessage.session_id == DiagnosisSession.id
            ).filter(
                ChatMessage.message_type == 'user',
                DiagnosisSession.created_at >= week_start
            )
            if user_ids:
                user_message_counts_q = user_message_counts_q.filter(DiagnosisSession.user_id.in_(user_ids))
            if exclude_user_ids:
                user_message_counts_q = user_message_counts_q.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
            user_message_counts = user_message_counts_q.group_by(DiagnosisSession.user_id).having(
                func.count(ChatMessage.id) > 20
            ).subquery()
            
            # Count distinct heavy users
            heavy_users_subquery = self.db.query(user_message_counts.c.user_id).distinct().subquery()
            heavy_users = self.db.query(func.count(heavy_users_subquery.c.user_id)).scalar() or 0
            
            # Users active in week 3
            week3_q = self.db.query(DiagnosisSession.user_id).filter(
                and_(
                    DiagnosisSession.created_at >= three_weeks_ago,
                    DiagnosisSession.created_at < two_weeks_ago
                )
            )
            if user_ids:
                week3_q = week3_q.filter(DiagnosisSession.user_id.in_(user_ids))
            if exclude_user_ids:
                week3_q = week3_q.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
            week3_subquery = week3_q.distinct().subquery()
            week3_active = self.db.query(func.count(week3_subquery.c.user_id)).scalar() or 0
            
            # PMF survey responses - use text comparison to handle enum case issues
            pmf_surveys_q = self.db.query(Survey).filter(
                and_(
                    text("LOWER(surveys.survey_type::text) = LOWER(:survey_type)").bindparams(survey_type=SurveyType.PMF.value),
                    text("surveys.created_at >= :period_start AND surveys.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
                )
            )
            if user_ids:
                pmf_surveys_q = pmf_surveys_q.filter(Survey.user_id.in_(user_ids))
            if exclude_user_ids:
                pmf_surveys_q = pmf_surveys_q.filter(Survey.user_id.notin_(exclude_user_ids))
            pmf_surveys = pmf_surveys_q.all()
            
            total_pmf_responses = len(pmf_surveys)
            very_disappointed_count = sum(1 for s in pmf_surveys if s.very_disappointed == True)
            very_disappointed_percentage = (very_disappointed_count / total_pmf_responses * 100) if total_pmf_responses > 0 else 0.0
            
            # Average PMF score - use text comparison to handle enum case issues
            avg_pmf_score_result = self.db.query(func.avg(Survey.pmf_score)).filter(
                and_(
                    text("LOWER(surveys.survey_type::text) = LOWER(:survey_type)").bindparams(survey_type=SurveyType.PMF.value),
                    Survey.pmf_score.isnot(None),
                    text("surveys.created_at >= :period_start AND surveys.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
                )
            ).scalar()
            avg_pmf_score = float(avg_pmf_score_result) if avg_pmf_score_result is not None else 0.0
            
            # Replacement behavior
            replacement_counts = {}
            for survey in pmf_surveys:
                if survey.replacement_behavior:
                    replacement_counts[survey.replacement_behavior] = replacement_counts.get(survey.replacement_behavior, 0) + 1
            
            # Willingness to pay - use text comparison to handle enum case issues
            avg_wtp_result = self.db.query(func.avg(Survey.willingness_to_pay)).filter(
                and_(
                    text("LOWER(surveys.survey_type::text) = LOWER(:survey_type)").bindparams(survey_type=SurveyType.PMF.value),
                    Survey.willingness_to_pay.isnot(None),
                    text("surveys.created_at >= :period_start AND surveys.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
                )
            ).scalar()
            avg_wtp = float(avg_wtp_result) if avg_wtp_result is not None else 0.0
            
            return {
                "heavy_users": heavy_users,
                "users_active_week3": week3_active,
                "very_disappointed_percentage": round(very_disappointed_percentage, 2),
                "total_pmf_responses": total_pmf_responses,
                "very_disappointed_count": very_disappointed_count,
                "avg_pmf_score": round(avg_pmf_score, 2),
                "replacement_behavior": replacement_counts,
                "avg_willingness_to_pay": round(avg_wtp, 2)
            }
        except Exception as e:
            logger.error(f"Error getting PMF metrics: {e}")
            raise
    
    def get_survey_statistics(
        self,
        days: Optional[int] = 30,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        user_ids: Optional[List[int]] = None,
        exclude_user_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Get survey completion statistics."""
        try:
            period_start, period_end = self._resolve_period(days, period_start, period_end)
            
            # Get total users
            total_users_q = self.db.query(func.count(User.id))
            if exclude_user_ids:
                total_users_q = total_users_q.filter(User.id.notin_(exclude_user_ids))
            total_users = total_users_q.scalar() or 0
            
            # Get survey statistics by type
            survey_stats = {}
            for survey_type in [SurveyType.BASELINE, SurveyType.MID, SurveyType.FINAL]:
                completed_q = self.db.query(func.count(Survey.id)).filter(
                    and_(
                        text("LOWER(surveys.survey_type::text) = LOWER(:survey_type)").bindparams(survey_type=survey_type.value),
                        text("surveys.created_at >= :period_start AND surveys.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
                    )
                )
                if user_ids:
                    completed_q = completed_q.filter(Survey.user_id.in_(user_ids))
                if exclude_user_ids:
                    completed_q = completed_q.filter(Survey.user_id.notin_(exclude_user_ids))
                completed_count = completed_q.scalar() or 0

                unique_q = self.db.query(func.count(func.distinct(Survey.user_id))).filter(
                    and_(
                        text("LOWER(surveys.survey_type::text) = LOWER(:survey_type)").bindparams(survey_type=survey_type.value),
                        text("surveys.created_at >= :period_start AND surveys.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
                    )
                )
                if user_ids:
                    unique_q = unique_q.filter(Survey.user_id.in_(user_ids))
                if exclude_user_ids:
                    unique_q = unique_q.filter(Survey.user_id.notin_(exclude_user_ids))
                unique_users = unique_q.scalar() or 0
                
                # Calculate pending (users who haven't completed)
                pending_count = max(0, total_users - unique_users)
                
                # Calculate completion percentage
                completion_percentage = (unique_users / total_users * 100) if total_users > 0 else 0
                
                survey_stats[survey_type.value] = {
                    "completed": completed_count,
                    "unique_users_completed": unique_users,
                    "pending": pending_count,
                    "completion_percentage": round(completion_percentage, 2),
                    "total_users": total_users
                }
            
            # Overall statistics
            total_completed = sum(stats["completed"] for stats in survey_stats.values())
            total_unique_q = self.db.query(func.count(func.distinct(Survey.user_id))).filter(
                text("surveys.created_at >= :period_start AND surveys.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
            )
            if user_ids:
                total_unique_q = total_unique_q.filter(Survey.user_id.in_(user_ids))
            if exclude_user_ids:
                total_unique_q = total_unique_q.filter(Survey.user_id.notin_(exclude_user_ids))
            total_unique_users = total_unique_q.scalar() or 0
            
            return {
                "by_type": survey_stats,
                "overall": {
                    "total_completed": total_completed,
                    "total_unique_users_completed": total_unique_users,
                    "total_users": total_users,
                    "overall_completion_percentage": round((total_unique_users / total_users * 100) if total_users > 0 else 0, 2)
                }
            }
        except Exception as e:
            logger.error(f"Error getting survey statistics: {e}")
            raise
    
    def get_device_statistics(
        self,
        days: Optional[int] = 30,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        user_ids: Optional[List[int]] = None,
        exclude_user_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Get device type statistics (phone, tablet, laptop) for the admin dashboard."""
        try:
            period_start, period_end = self._resolve_period(days, period_start, period_end)
            device_q = self.db.query(
                DeviceActivityLog.device_type,
                func.count(DeviceActivityLog.id).label("cnt")
            ).filter(
                text("device_activity_log.created_at >= :period_start AND device_activity_log.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
            )
            if user_ids:
                device_q = device_q.filter(DeviceActivityLog.user_id.in_(user_ids))
            if exclude_user_ids:
                device_q = device_q.filter(DeviceActivityLog.user_id.notin_(exclude_user_ids))
            rows = device_q.group_by(DeviceActivityLog.device_type).all()

            by_type = {"phone": 0, "tablet": 0, "laptop": 0, "unknown": 0}
            for device_type, cnt in rows:
                key = (device_type or "unknown").lower()
                if key not in by_type:
                    by_type[key] = 0
                by_type[key] += int(cnt) if cnt else 0

            total = sum(by_type.values())
            return {"by_type": by_type, "total": total}
        except Exception as e:
            logger.warning(f"Error getting device statistics: {e}")
            return {"by_type": {"phone": 0, "tablet": 0, "laptop": 0, "unknown": 0}, "total": 0}

    def log_device_activity(
        self,
        user_id: Optional[int],
        device_type: str,
        activity: str,
    ) -> None:
        """Log a device activity (login, session_create) for statistics. Fails silently."""
        try:
            normalized = (device_type or "").strip().lower()
            if normalized not in ("phone", "tablet", "laptop"):
                normalized = "unknown"
            entry = DeviceActivityLog(
                user_id=user_id,
                device_type=normalized,
                activity=activity,
                created_at=datetime.utcnow().isoformat(),
            )
            self.db.add(entry)
            self.db.commit()
        except Exception as e:
            logger.warning(f"Failed to log device activity: {e}", exc_info=True)
            try:
                self.db.rollback()
            except Exception:
                pass

    def insert_test_device_activity(self, user_id: int) -> None:
        """Insert one test row (laptop, login) for admin verification. Raises on failure."""
        entry = DeviceActivityLog(
            user_id=user_id,
            device_type="laptop",
            activity="login",
            created_at=datetime.utcnow().isoformat(),
        )
        self.db.add(entry)
        self.db.commit()

    def get_all_metrics(
        self,
        days: Optional[int] = 30,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        user_ids: Optional[List[int]] = None,
        exclude_user_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Get all dashboard metrics. Use period_start/period_end for exact date range, or days."""
        period_start_resolved, period_end_resolved = self._resolve_period(days, period_start, period_end)
        return {
            "usage": self.get_usage_metrics(days=days, period_start=period_start, period_end=period_end, user_ids=user_ids, exclude_user_ids=exclude_user_ids),
            "clinical_value": self.get_clinical_value_metrics(days=days, period_start=period_start, period_end=period_end, user_ids=user_ids, exclude_user_ids=exclude_user_ids),
            "safety": self.get_safety_metrics(days=days, period_start=period_start, period_end=period_end, user_ids=user_ids, exclude_user_ids=exclude_user_ids),
            "pmf": self.get_pmf_metrics(days=days, period_start=period_start, period_end=period_end, user_ids=user_ids, exclude_user_ids=exclude_user_ids),
            "surveys": self.get_survey_statistics(days=days, period_start=period_start, period_end=period_end, user_ids=user_ids, exclude_user_ids=exclude_user_ids),
            "devices": self.get_device_statistics(days=days, period_start=period_start, period_end=period_end, user_ids=user_ids, exclude_user_ids=exclude_user_ids),
            "period_days": days,
            "period_start": period_start_resolved,
            "period_end": period_end_resolved,
            "user_ids_filter": user_ids,
            "exclude_user_ids_filter": exclude_user_ids,
            "generated_at": datetime.utcnow().isoformat(),
        }

    def get_feedback_list(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_ids: Optional[List[int]] = None,
        exclude_user_ids: Optional[List[int]] = None,
        feedback_type: Optional[str] = None,
        has_text_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List feedback comments with optional filters. Dates as YYYY-MM-DD."""
        from healthnavi.core.query_utils import parse_date_range
        period_start, period_end = parse_date_range(start_date, end_date)
        if not period_start or not period_end:
            period_start = (datetime.utcnow() - timedelta(days=30)).isoformat()
            period_end = datetime.utcnow().isoformat()
        query = self.db.query(MessageFeedback, User.email, User.full_name).join(
            User, User.id == MessageFeedback.user_id
        ).filter(
            text("message_feedback.created_at >= :period_start AND message_feedback.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
        )
        if user_ids:
            query = query.filter(MessageFeedback.user_id.in_(user_ids))
        if exclude_user_ids:
            query = query.filter(MessageFeedback.user_id.notin_(exclude_user_ids))
        if feedback_type and feedback_type.lower() in ("helpful", "not_helpful"):
            query = query.filter(MessageFeedback.feedback_type == feedback_type.lower())
        if has_text_only:
            query = query.filter(MessageFeedback.feedback_text.isnot(None), MessageFeedback.feedback_text != "")
        total = query.count()
        rows = query.order_by(desc(MessageFeedback.created_at)).offset(offset).limit(limit).all()
        items = []
        for fb, email, full_name in rows:
            items.append({
                "id": fb.id,
                "message_id": fb.message_id,
                "user_id": fb.user_id,
                "user_email": email,
                "user_name": full_name,
                "feedback_type": fb.feedback_type,
                "feedback_text": fb.feedback_text,
                "rating": fb.rating,
                "created_at": fb.created_at,
                "updated_at": fb.updated_at,
            })
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def _get_active_user_ids(
        self,
        user_ids: Optional[List[int]] = None,
        exclude_user_ids: Optional[List[int]] = None,
    ) -> List[int]:
        """Return user IDs that have at least one diagnosis session (active users)."""
        q = self.db.query(DiagnosisSession.user_id).distinct()
        if user_ids:
            q = q.filter(DiagnosisSession.user_id.in_(user_ids))
        if exclude_user_ids:
            q = q.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
        return [row[0] for row in q.all() if row[0] is not None]

    def _metrics_to_rows(self, metrics_dict: Dict[str, Any]) -> List[tuple]:
        """Flatten metrics into (metric_name, value, description) using METRIC_META."""
        rows = []
        skip_keys = ("period_days", "period_start", "period_end", "user_ids_filter", "exclude_user_ids_filter", "generated_at")
        for section in ["usage", "clinical_value", "safety", "pmf", "surveys", "devices"]:
            data = metrics_dict.get(section)
            if not isinstance(data, dict):
                continue
            for key, val in data.items():
                if section == "surveys" and key == "by_type":
                    continue
                if section == "surveys" and key == "overall":
                    for ok, ov in (val or {}).items():
                        meta_key = f"surveys.overall.{ok}"
                        name, desc = METRIC_META.get(meta_key, (ok.replace("_", " ").title(), "See dashboard for definition."))
                        rows.append((name, ov, desc))
                    continue
                if section == "devices" and key == "by_type":
                    for device, count in (val or {}).items():
                        rows.append((f"Device: {device}", count, "Number of device activity log entries for this device type."))
                    continue
                meta_key = f"{section}.{key}"
                name, desc = METRIC_META.get(meta_key, (key.replace("_", " ").title(), "See dashboard for definition."))
                if isinstance(val, dict):
                    val = str(val)
                rows.append((name, val, desc))
        return rows

    def get_export_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_ids: Optional[List[int]] = None,
        exclude_user_ids: Optional[List[int]] = None,
        active_users_only: bool = False,
        format: str = "json",
    ) -> Dict[str, Any]:
        """Build report: overall statistics first, then period-selected statistics, with description column; include feedback comments.
        When active_users_only is True, only users who have at least one session are included in statistics."""
        from healthnavi.core.query_utils import parse_date_range
        import io
        import csv as csv_module

        effective_user_ids = user_ids
        effective_exclude = exclude_user_ids
        if active_users_only:
            active_ids = self._get_active_user_ids(user_ids=user_ids, exclude_user_ids=exclude_user_ids)
            effective_user_ids = active_ids if active_ids else None
            effective_exclude = None

        now_iso = datetime.utcnow().isoformat()
        overall_start = "2000-01-01T00:00:00"
        period_start, period_end = parse_date_range(start_date, end_date)
        days = 30
        if period_start and period_end:
            try:
                start_dt = datetime.fromisoformat(period_start.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(period_end.replace("Z", "+00:00"))
                days = max(1, (end_dt - start_dt).days)
            except Exception:
                pass

        # Overall (all-time) statistics
        overall_metrics = self.get_all_metrics(
            days=365 * 10,
            period_start=overall_start,
            period_end=now_iso,
            user_ids=effective_user_ids,
            exclude_user_ids=effective_exclude,
        )
        overall_rows = self._metrics_to_rows(
            {k: v for k, v in overall_metrics.items() if k not in ("period_start", "period_end", "user_ids_filter", "exclude_user_ids_filter", "generated_at")}
        )

        # Period-selected statistics
        period_metrics = self.get_all_metrics(
            days=days,
            period_start=period_start,
            period_end=period_end,
            user_ids=effective_user_ids,
            exclude_user_ids=effective_exclude,
        )
        period_rows = self._metrics_to_rows(
            {k: v for k, v in period_metrics.items() if k not in ("period_start", "period_end", "user_ids_filter", "exclude_user_ids_filter", "generated_at")}
        )

        # Feedback comments (full list for the period)
        feedback_data = self.get_feedback_list(
            start_date=start_date,
            end_date=end_date,
            user_ids=effective_user_ids,
            exclude_user_ids=effective_exclude,
            limit=5000,
            has_text_only=False,
        )
        feedback_items = feedback_data.get("items") or []

        report = {
            "filters": {"start_date": start_date, "end_date": end_date, "user_ids": user_ids, "exclude_user_ids": exclude_user_ids, "active_users_only": active_users_only},
            "period_selected": {"period_start": period_metrics.get("period_start"), "period_end": period_metrics.get("period_end")},
            "generated_at": now_iso,
            "overall_statistics": [{"metric_name": n, "value": v, "description": d} for n, v, d in overall_rows],
            "period_statistics": [{"metric_name": n, "value": v, "description": d} for n, v, d in period_rows],
            "feedback_count": feedback_data.get("total", 0),
            "feedback_comments": feedback_items,
        }

        if format == "csv":
            buf = io.StringIO()
            w = csv_module.writer(buf)
            w.writerow(["Admin Report", "Generated", report["generated_at"]])
            w.writerow(["Filters", "Start", start_date or "—", "End", end_date or "—", "Excluded users", exclude_user_ids or "—", "Active users only", active_users_only])
            w.writerow([])
            w.writerow(["OVERALL STATISTICS (all time)"])
            w.writerow(["Metric name", "Value", "How it was calculated"])
            for name, value, desc in overall_rows:
                w.writerow([name, value, desc])
            w.writerow([])
            w.writerow(["PERIOD SELECTED STATISTICS", report["period_selected"].get("period_start", ""), "to", report["period_selected"].get("period_end", "")])
            w.writerow(["Metric name", "Value", "How it was calculated"])
            for name, value, desc in period_rows:
                w.writerow([name, value, desc])
            w.writerow([])
            w.writerow(["FEEDBACK COMMENTS", f"Total: {report['feedback_count']}"])
            w.writerow(["Date", "User email", "User name", "Type", "Rating", "Comment"])
            for row in feedback_items:
                w.writerow([
                    row.get("created_at", ""),
                    row.get("user_email", ""),
                    row.get("user_name", ""),
                    row.get("feedback_type", ""),
                    row.get("rating", ""),
                    (row.get("feedback_text") or "").replace("\n", " ")[:1000],
                ])
            content = buf.getvalue()
            filename = f"admin_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            return {"content": content, "filename": filename, "report": report}
        return {"report": report}
    
    def check_and_create_alerts(self) -> List[Alert]:
        """Check conditions and create alerts if thresholds are exceeded."""
        alerts_created = []
        try:
            last_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()
            
            # Check for critical safety events - use text() with enum value for proper type handling
            critical_events = self.db.query(SafetyEvent).filter(
                and_(
                    SafetyEvent.is_critical == True,
                    text("LOWER(safety_events.status::text) = LOWER(:status)").bindparams(status=SafetyEventStatus.OPEN.value),
                    text("safety_events.created_at >= :last_24h").bindparams(last_24h=last_24h)
                )
            ).all()
            
            for event in critical_events:
                # Check if alert already exists
                existing_alert = self.db.query(Alert).filter(
                    and_(
                        Alert.safety_event_id == event.id,
                        Alert.alert_type == "critical_safety_event",
                        Alert.is_resolved == False
                    )
                ).first()
                
                if not existing_alert:
                    alert = Alert(
                        alert_type="critical_safety_event",
                        severity=SafetyEventSeverity.CRITICAL,
                        title=f"Critical Safety Event: {event.title}",
                        message=f"A critical safety event has been created: {event.description or event.title}",
                        safety_event_id=event.id,
                        created_at=datetime.utcnow().isoformat()
                    )
                    self.db.add(alert)
                    alerts_created.append(alert)
            
            # Check flag rate > 5% in last 24h - use text() for string date comparison
            queries_24h = self.db.query(func.count(ChatMessage.id)).filter(
                and_(
                    ChatMessage.message_type == 'user',
                    text("chat_messages.created_at >= :last_24h").bindparams(last_24h=last_24h)
                )
            ).scalar() or 0
            
            flags_24h = self.db.query(func.count(SafetyEvent.id)).filter(
                text("safety_events.created_at >= :last_24h").bindparams(last_24h=last_24h)
            ).scalar() or 0
            
            flag_rate = (flags_24h / queries_24h * 100) if queries_24h > 0 else 0.0
            
            if flag_rate > 5.0:
                # Check if alert already exists for this period
                existing_alert = self.db.query(Alert).filter(
                    and_(
                        Alert.alert_type == "high_flag_rate",
                        text("alerts.created_at >= :last_24h").bindparams(last_24h=last_24h),
                        Alert.is_resolved == False
                    )
                ).first()
                
                if not existing_alert:
                    alert = Alert(
                        alert_type="high_flag_rate",
                        severity=SafetyEventSeverity.HIGH,
                        title="High Flag Rate Detected",
                        message=f"Flag rate is {flag_rate:.2f}% in the last 24 hours (threshold: 5%). Total flags: {flags_24h}, Total queries: {queries_24h}",
                        created_at=datetime.utcnow().isoformat()
                    )
                    self.db.add(alert)
                    alerts_created.append(alert)
            
            # Check for high-risk queries without citations - use text() for string date comparison
            high_risk_queries = self.db.query(ChatMessage).join(
                SafetyEvent, SafetyEvent.message_id == ChatMessage.id
            ).filter(
                and_(
                    SafetyEvent.was_red_flag_queried == True,
                    SafetyEvent.has_guideline_citation == False,
                    text("chat_messages.created_at >= :last_24h").bindparams(last_24h=last_24h)
                )
            ).all()
            
            if high_risk_queries:
                existing_alert = self.db.query(Alert).filter(
                    and_(
                        Alert.alert_type == "missing_citations_high_risk",
                        text("alerts.created_at >= :last_24h").bindparams(last_24h=last_24h),
                        Alert.is_resolved == False
                    )
                ).first()
                
                if not existing_alert:
                    alert = Alert(
                        alert_type="missing_citations_high_risk",
                        severity=SafetyEventSeverity.HIGH,
                        title="High-Risk Queries Without Citations",
                        message=f"{len(high_risk_queries)} high-risk queries returned responses without guideline citations in the last 24 hours",
                        created_at=datetime.utcnow().isoformat()
                    )
                    self.db.add(alert)
                    alerts_created.append(alert)
            
            if alerts_created:
                self.db.commit()
                for alert in alerts_created:
                    self.db.refresh(alert)
            
            return alerts_created
        except Exception as e:
            logger.error(f"Error checking and creating alerts: {e}")
            self.db.rollback()
            raise
    
    def log_audit_event(
        self,
        user_id: Optional[int],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        description: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> AuditLog:
        """Create an immutable audit log entry."""
        import json
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata=json.dumps(metadata) if metadata else None,
            created_at=datetime.utcnow().isoformat()
        )
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)
        return audit_log
    
    def get_users(
        self,
        limit: int = 50,
        offset: int = 0,
        is_active: Optional[bool] = None,
        role: Optional[str] = None,
        medical_professional_type: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """Get users with filters, pagination, and sorting."""
        try:
            query = self.db.query(User)
            
            if is_active is not None:
                query = query.filter(User.is_active == is_active)
            if role:
                query = query.filter(User.role == role)
            if medical_professional_type:
                query = query.filter(User.medical_professional_type == medical_professional_type)
            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    or_(
                        User.email.ilike(search_pattern),
                        User.username.ilike(search_pattern),
                        User.full_name.ilike(search_pattern)
                    )
                )
            
            # Apply sorting
            sort_column = getattr(User, sort_by, User.created_at)
            if sort_order.lower() == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(sort_column)
            
            total = query.count()
            users = query.offset(offset).limit(limit).all()
            
            users_data = []
            for user in users:
                # Get user statistics
                session_count = self.db.query(func.count(DiagnosisSession.id)).filter(
                    DiagnosisSession.user_id == user.id
                ).scalar() or 0
                
                message_count = self.db.query(func.count(ChatMessage.id)).join(
                    DiagnosisSession, DiagnosisSession.id == ChatMessage.session_id
                ).filter(DiagnosisSession.user_id == user.id).scalar() or 0
                
                users_data.append({
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
                })
            
            return {
                "users": users_data,
                "total": total,
                "limit": limit,
                "offset": offset
            }
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            raise
    
    def get_user_statistics(
        self,
        days: Optional[int] = 30,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        user_ids: Optional[List[int]] = None,
        exclude_user_ids: Optional[List[int]] = None,
        active_users_only: bool = False,
    ) -> Dict[str, Any]:
        """Get user statistics by type and activity."""
        try:
            if active_users_only:
                active_ids = self._get_active_user_ids(user_ids=user_ids, exclude_user_ids=exclude_user_ids)
                user_ids = active_ids if active_ids else None
                exclude_user_ids = None
            period_start, period_end = self._resolve_period(days, period_start, period_end)
            base_user_query = self.db.query(User)
            if user_ids:
                base_user_query = base_user_query.filter(User.id.in_(user_ids))
            if exclude_user_ids:
                base_user_query = base_user_query.filter(User.id.notin_(exclude_user_ids))

            # Total users
            total_users = base_user_query.count()

            # Active users
            active_users = base_user_query.filter(User.is_active == True).count()

            # Users by role
            users_by_role = {}
            roles = base_user_query.with_entities(User.role, func.count(User.id)).group_by(User.role).all()
            for role, count in roles:
                # Ensure role is not None and count is valid
                if role is not None:
                    users_by_role[str(role)] = int(count) if count is not None else 0
                else:
                    users_by_role["Unknown"] = users_by_role.get("Unknown", 0) + (int(count) if count is not None else 0)
            
            # Users by medical professional type
            users_by_type = {}
            types_q = base_user_query.filter(User.medical_professional_type.isnot(None))
            types = types_q.with_entities(User.medical_professional_type, func.count(User.id)).group_by(User.medical_professional_type).all()
            for prof_type, count in types:
                # Ensure prof_type is not None and is a valid string
                if prof_type is not None and isinstance(prof_type, str) and prof_type.strip():
                    users_by_type[str(prof_type)] = int(count) if count is not None else 0
                elif prof_type is None:
                    # Handle edge case where None might slip through
                    users_by_type["Unknown"] = users_by_type.get("Unknown", 0) + (int(count) if count is not None else 0)
            
            # Count users without a professional type
            users_without_type_q = base_user_query.filter(
                or_(
                    User.medical_professional_type.is_(None),
                    User.medical_professional_type == ""
                )
            )
            users_without_type = users_without_type_q.count()
            if users_without_type > 0:
                users_by_type["Not Specified"] = users_without_type
            
            # Activated users (users with at least one session)
            activated_q = self.db.query(DiagnosisSession.user_id).distinct()
            if user_ids:
                activated_q = activated_q.filter(DiagnosisSession.user_id.in_(user_ids))
            if exclude_user_ids:
                activated_q = activated_q.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
            activated_user_ids_list = [row[0] for row in activated_q.all() if row[0] is not None]
            activated_users = len(activated_user_ids_list)

            # New users in period
            new_users_q = self.db.query(func.count(User.id)).filter(
                text("users.created_at >= :period_start AND users.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
            )
            if user_ids:
                new_users_q = new_users_q.filter(User.id.in_(user_ids))
            if exclude_user_ids:
                new_users_q = new_users_q.filter(User.id.notin_(exclude_user_ids))
            new_users = new_users_q.scalar() or 0

            # Users active in period (users with sessions in period)
            active_in_period_q = self.db.query(func.count(func.distinct(DiagnosisSession.user_id))).filter(
                text("diagnosis_sessions.created_at >= :period_start AND diagnosis_sessions.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
            )
            if user_ids:
                active_in_period_q = active_in_period_q.filter(DiagnosisSession.user_id.in_(user_ids))
            if exclude_user_ids:
                active_in_period_q = active_in_period_q.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
            active_in_period = active_in_period_q.scalar() or 0
            
            # Ensure all counts are integers
            return {
                "total_users": int(total_users) if total_users is not None else 0,
                "active_users": int(active_users) if active_users is not None else 0,
                "inactive_users": int(total_users - active_users) if total_users is not None and active_users is not None else 0,
                "activated_users": int(activated_users) if activated_users is not None else 0,
                "users_by_role": users_by_role,  # Already converted to int in the loop above
                "users_by_type": users_by_type,  # Already converted to int in the loop above
                "new_users": int(new_users) if new_users is not None else 0,
                "active_in_period": int(active_in_period) if active_in_period is not None else 0
            }
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            raise
    
    def get_session_statistics(
        self,
        days: Optional[int] = 30,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        user_ids: Optional[List[int]] = None,
        exclude_user_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Get session statistics including active sessions and average length."""
        try:
            period_start, period_end = self._resolve_period(days, period_start, period_end)
            now = datetime.utcnow()
            
            # Total sessions
            total_sessions_q = self.db.query(func.count(DiagnosisSession.id)).filter(
                text("diagnosis_sessions.created_at >= :period_start AND diagnosis_sessions.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
            )
            if user_ids:
                total_sessions_q = total_sessions_q.filter(DiagnosisSession.user_id.in_(user_ids))
            if exclude_user_ids:
                total_sessions_q = total_sessions_q.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
            total_sessions = total_sessions_q.scalar() or 0
            
            # Active sessions (sessions updated in last 24 hours)
            last_24h = (now - timedelta(hours=24)).isoformat()
            active_sessions = self.db.query(func.count(DiagnosisSession.id)).filter(
                text("diagnosis_sessions.updated_at >= :last_24h").bindparams(last_24h=last_24h)
            ).scalar() or 0
            
            # Average session length (in messages)
            session_lengths_q = self.db.query(
                DiagnosisSession.id,
                func.count(ChatMessage.id).label('message_count')
            ).join(
                ChatMessage, ChatMessage.session_id == DiagnosisSession.id
            ).filter(
                text("diagnosis_sessions.created_at >= :period_start AND diagnosis_sessions.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
            )
            if user_ids:
                session_lengths_q = session_lengths_q.filter(DiagnosisSession.user_id.in_(user_ids))
            if exclude_user_ids:
                session_lengths_q = session_lengths_q.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
            session_lengths = session_lengths_q.group_by(DiagnosisSession.id).subquery()
            
            avg_length_result = self.db.query(func.avg(session_lengths.c.message_count)).scalar()
            avg_session_length = float(avg_length_result) if avg_length_result is not None else 0.0
            
            # Average session duration (time between first and last message)
            # This is approximate - we'll use created_at and updated_at
            sessions_with_duration_q = self.db.query(
                DiagnosisSession.id,
                DiagnosisSession.created_at,
                DiagnosisSession.updated_at
            ).filter(
                text("diagnosis_sessions.created_at >= :period_start AND diagnosis_sessions.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
            )
            if user_ids:
                sessions_with_duration_q = sessions_with_duration_q.filter(DiagnosisSession.user_id.in_(user_ids))
            if exclude_user_ids:
                sessions_with_duration_q = sessions_with_duration_q.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
            sessions_with_duration = sessions_with_duration_q.all()
            
            durations = []
            for session in sessions_with_duration:
                try:
                    created = self.parse_datetime(session.created_at) if session.created_at else None
                    updated = self.parse_datetime(session.updated_at) if session.updated_at else None
                    if created and updated:
                        duration_seconds = (updated - created).total_seconds()
                        if duration_seconds > 0:
                            durations.append(duration_seconds / 60)  # Convert to minutes
                except:
                    continue
            
            avg_duration_minutes = sum(durations) / len(durations) if durations else 0.0
            
            return {
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "avg_session_length": round(avg_session_length, 2),
                "avg_duration_minutes": round(avg_duration_minutes, 2)
            }
        except Exception as e:
            logger.error(f"Error getting session statistics: {e}")
            raise
    
    def get_ai_response_statistics(
        self,
        days: Optional[int] = 30,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        user_ids: Optional[List[int]] = None,
        exclude_user_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Get AI response statistics including feedback and response times."""
        try:
            period_start, period_end = self._resolve_period(days, period_start, period_end)
            
            # Total AI responses (assistant messages) - join session for user filter
            total_responses_q = self.db.query(func.count(ChatMessage.id)).join(
                DiagnosisSession, DiagnosisSession.id == ChatMessage.session_id
            ).filter(
                ChatMessage.message_type == 'assistant',
                text("chat_messages.created_at >= :period_start AND chat_messages.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
            )
            if user_ids:
                total_responses_q = total_responses_q.filter(DiagnosisSession.user_id.in_(user_ids))
            if exclude_user_ids:
                total_responses_q = total_responses_q.filter(DiagnosisSession.user_id.notin_(exclude_user_ids))
            total_responses = total_responses_q.scalar() or 0

            # Responses with feedback - filter by feedback creation date to see recent feedback
            responses_with_feedback_q = self.db.query(func.count(MessageFeedback.id)).filter(
                text("message_feedback.created_at >= :period_start AND message_feedback.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
            )
            if user_ids:
                responses_with_feedback_q = responses_with_feedback_q.filter(MessageFeedback.user_id.in_(user_ids))
            if exclude_user_ids:
                responses_with_feedback_q = responses_with_feedback_q.filter(MessageFeedback.user_id.notin_(exclude_user_ids))
            responses_with_feedback = responses_with_feedback_q.scalar() or 0

            # Helpful feedback - filter by feedback creation date
            helpful_count_q = self.db.query(func.count(MessageFeedback.id)).filter(
                MessageFeedback.feedback_type == 'helpful',
                text("message_feedback.created_at >= :period_start AND message_feedback.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
            )
            if user_ids:
                helpful_count_q = helpful_count_q.filter(MessageFeedback.user_id.in_(user_ids))
            if exclude_user_ids:
                helpful_count_q = helpful_count_q.filter(MessageFeedback.user_id.notin_(exclude_user_ids))
            helpful_count = helpful_count_q.scalar() or 0

            # Not helpful feedback - filter by feedback creation date
            not_helpful_count_q = self.db.query(func.count(MessageFeedback.id)).filter(
                MessageFeedback.feedback_type == 'not_helpful',
                text("message_feedback.created_at >= :period_start AND message_feedback.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
            )
            if user_ids:
                not_helpful_count_q = not_helpful_count_q.filter(MessageFeedback.user_id.in_(user_ids))
            if exclude_user_ids:
                not_helpful_count_q = not_helpful_count_q.filter(MessageFeedback.user_id.notin_(exclude_user_ids))
            not_helpful_count = not_helpful_count_q.scalar() or 0

            # Average rating - filter by feedback creation date
            avg_rating_q = self.db.query(func.avg(MessageFeedback.rating)).filter(
                MessageFeedback.rating.isnot(None),
                text("message_feedback.created_at >= :period_start AND message_feedback.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
            )
            if user_ids:
                avg_rating_q = avg_rating_q.filter(MessageFeedback.user_id.in_(user_ids))
            if exclude_user_ids:
                avg_rating_q = avg_rating_q.filter(MessageFeedback.user_id.notin_(exclude_user_ids))
            avg_rating_result = avg_rating_q.scalar()
            avg_rating = float(avg_rating_result) if avg_rating_result is not None else 0.0
            
            # Response time calculation (time between user message and AI response)
            # Get pairs of user messages and their following assistant messages
            user_messages = self.db.query(
                ChatMessage.id,
                ChatMessage.session_id,
                ChatMessage.created_at
            ).filter(
                and_(
                    ChatMessage.message_type == 'user',
                    text("chat_messages.created_at >= :period_start AND chat_messages.created_at < :period_end").bindparams(period_start=period_start, period_end=period_end)
                )
            ).order_by(ChatMessage.created_at).all()
            
            response_times = []
            for user_msg in user_messages:
                # Find the next assistant message in the same session
                next_assistant = self.db.query(ChatMessage).filter(
                    and_(
                        ChatMessage.session_id == user_msg.session_id,
                        ChatMessage.message_type == 'assistant',
                        text("chat_messages.created_at > :user_time").bindparams(user_time=user_msg.created_at)
                    )
                ).order_by(ChatMessage.created_at).first()
                
                if next_assistant:
                    try:
                        user_time = self.parse_datetime(user_msg.created_at)
                        ai_time = self.parse_datetime(next_assistant.created_at)
                        if user_time and ai_time:
                            response_time_seconds = (ai_time - user_time).total_seconds()
                            if 0 < response_time_seconds < 300:  # Reasonable range: 0-5 minutes
                                response_times.append(response_time_seconds)
                    except:
                        continue
            
            avg_response_time_seconds = sum(response_times) / len(response_times) if response_times else 0.0
            avg_response_time_ms = avg_response_time_seconds * 1000
            
            return {
                "total_responses": total_responses,
                "responses_with_feedback": responses_with_feedback,
                "helpful_count": helpful_count,
                "not_helpful_count": not_helpful_count,
                "helpful_percentage": round((helpful_count / responses_with_feedback * 100) if responses_with_feedback > 0 else 0, 2),
                "not_helpful_percentage": round((not_helpful_count / responses_with_feedback * 100) if responses_with_feedback > 0 else 0, 2),
                "avg_rating": round(avg_rating, 2),
                "avg_response_time_ms": round(avg_response_time_ms, 2),
                "avg_response_time_seconds": round(avg_response_time_seconds, 2)
            }
        except Exception as e:
            logger.error(f"Error getting AI response statistics: {e}")
            raise
