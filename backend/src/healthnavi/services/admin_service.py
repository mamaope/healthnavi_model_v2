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
from healthnavi.models.admin import SafetyEvent, Survey, Alert, AuditLog, SafetyEventSeverity, SafetyEventStatus, SurveyType

logger = logging.getLogger(__name__)


class AdminService:
    """Service for admin dashboard metrics and analytics."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def parse_datetime(self, date_str: str) -> Optional[datetime]:
        """Parse ISO datetime string to datetime object."""
        try:
            if 'T' in date_str:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return datetime.fromisoformat(date_str)
        except:
            return None
    
    def get_usage_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Get usage panel metrics."""
        try:
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = today_start - timedelta(days=7)
            three_weeks_ago = today_start - timedelta(days=21)
            period_start = (today_start - timedelta(days=days)).isoformat()
            
            # Daily Active Users (DAU) - use subquery for distinct count
            dau_subquery = self.db.query(DiagnosisSession.user_id).filter(
                DiagnosisSession.created_at >= today_start.isoformat(),
                DiagnosisSession.created_at < (today_start + timedelta(days=1)).isoformat()
            ).distinct().subquery()
            dau = self.db.query(func.count(dau_subquery.c.user_id)).scalar() or 0
            
            # Weekly Active Users (WAU) - use subquery for distinct count
            wau_subquery = self.db.query(DiagnosisSession.user_id).filter(
                DiagnosisSession.created_at >= week_start.isoformat()
            ).distinct().subquery()
            wau = self.db.query(func.count(wau_subquery.c.user_id)).scalar() or 0
            
            # Activated users (users with at least one session)
            activated_user_ids = self.db.query(DiagnosisSession.user_id).distinct().all()
            activated_user_ids_list = [row[0] for row in activated_user_ids if row[0] is not None]
            if activated_user_ids_list:
                activated_users = self.db.query(func.count(User.id)).filter(
                    User.id.in_(activated_user_ids_list)
                ).scalar() or 0
            else:
                activated_users = 0
            
            # Total users (all users on the system, not just active)
            total_users = self.db.query(func.count(User.id)).scalar() or 0
            
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
                text("diagnosis_sessions.created_at >= :period_start").bindparams(period_start=period_start)
            ).group_by(DiagnosisSession.user_id).subquery()
            
            queries_per_clinician_result = self.db.query(
                func.avg(user_message_counts.c.message_count)
            ).scalar()
            queries_per_clinician = float(queries_per_clinician_result) if queries_per_clinician_result is not None else 0.0
            
            # Sessions per user (average)
            user_session_counts = self.db.query(
                DiagnosisSession.user_id,
                func.count(DiagnosisSession.id).label('session_count')
            ).filter(
                text("diagnosis_sessions.created_at >= :period_start").bindparams(period_start=period_start)
            ).group_by(DiagnosisSession.user_id).subquery()
            
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
            ).distinct()
            week1_user_ids = [row[0] for row in week1_user_ids_query.all() if row[0] is not None]
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
    
    def get_clinical_value_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Get clinical value panel metrics."""
        try:
            period_start = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            # Total feedback - use text() for string date comparison
            total_feedback = self.db.query(func.count(MessageFeedback.id)).filter(
                text("message_feedback.created_at >= :period_start").bindparams(period_start=period_start)
            ).scalar() or 0
            
            # Helpful feedback - use text() for string date comparison
            helpful_feedback = self.db.query(func.count(MessageFeedback.id)).filter(
                and_(
                    MessageFeedback.feedback_type == 'helpful',
                    text("message_feedback.created_at >= :period_start").bindparams(period_start=period_start)
                )
            ).scalar() or 0
            
            helpful_percentage = (helpful_feedback / total_feedback * 100) if total_feedback > 0 else 0.0
            
            # Average usefulness score (rating) - use text() for string date comparison
            avg_rating_result = self.db.query(func.avg(MessageFeedback.rating)).filter(
                and_(
                    MessageFeedback.rating.isnot(None),
                    text("message_feedback.created_at >= :period_start").bindparams(period_start=period_start)
                )
            ).scalar()
            avg_rating = float(avg_rating_result) if avg_rating_result is not None else 0.0
            
            # Relevant queries (from surveys) - use text() for string date comparison
            relevant_queries = self.db.query(func.count(Survey.id)).filter(
                and_(
                    Survey.query_relevance == True,
                    text("surveys.created_at >= :period_start").bindparams(period_start=period_start)
                )
            ).scalar() or 0
            
            total_survey_queries = self.db.query(func.count(Survey.id)).filter(
                and_(
                    Survey.query_relevance.isnot(None),
                    text("surveys.created_at >= :period_start").bindparams(period_start=period_start)
                )
            ).scalar() or 0
            
            relevant_percentage = (relevant_queries / total_survey_queries * 100) if total_survey_queries > 0 else 0.0
            
            # Average time saved (from surveys) - use text() for string date comparison
            avg_time_saved_result = self.db.query(func.avg(Survey.time_saved_minutes)).filter(
                and_(
                    Survey.time_saved_minutes.isnot(None),
                    text("surveys.created_at >= :period_start").bindparams(period_start=period_start)
                )
            ).scalar()
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
    
    def get_safety_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Get safety panel metrics."""
        try:
            period_start = (datetime.utcnow() - timedelta(days=days)).isoformat()
            last_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()
            
            # Total queries in period - use text() for string date comparison
            total_queries = self.db.query(func.count(ChatMessage.id)).filter(
                and_(
                    ChatMessage.message_type == 'user',
                    text("chat_messages.created_at >= :period_start").bindparams(period_start=period_start)
                )
            ).scalar() or 0
            
            # Total queries in last 24h - use text() for string date comparison
            queries_24h = self.db.query(func.count(ChatMessage.id)).filter(
                and_(
                    ChatMessage.message_type == 'user',
                    text("chat_messages.created_at >= :last_24h").bindparams(last_24h=last_24h)
                )
            ).scalar() or 0
            
            # Safety flags/events - use text() for string date comparison
            total_flags = self.db.query(func.count(SafetyEvent.id)).filter(
                text("safety_events.created_at >= :period_start").bindparams(period_start=period_start)
            ).scalar() or 0
            
            flags_per_100_queries = (total_flags / total_queries * 100) if total_queries > 0 else 0.0
            
            # Open safety events - use enum directly for proper type handling
            open_events = self.db.query(func.count(SafetyEvent.id)).filter(
                SafetyEvent.status == SafetyEventStatus.OPEN
            ).scalar() or 0
            
            # Critical incidents - use text() for string date comparison
            critical_incidents = self.db.query(func.count(SafetyEvent.id)).filter(
                and_(
                    SafetyEvent.is_critical == True,
                    text("safety_events.created_at >= :period_start").bindparams(period_start=period_start)
                )
            ).scalar() or 0
            
            # Responses with guideline citations - use text() for string date comparison
            messages_with_citations = self.db.query(func.count(ChatMessage.id)).filter(
                and_(
                    ChatMessage.message_type == 'assistant',
                    ChatMessage.content.contains('citation') | ChatMessage.content.contains('guideline'),
                    text("chat_messages.created_at >= :period_start").bindparams(period_start=period_start)
                )
            ).scalar() or 0
            
            total_assistant_messages = self.db.query(func.count(ChatMessage.id)).filter(
                and_(
                    ChatMessage.message_type == 'assistant',
                    text("chat_messages.created_at >= :period_start").bindparams(period_start=period_start)
                )
            ).scalar() or 0
            
            citations_percentage = (messages_with_citations / total_assistant_messages * 100) if total_assistant_messages > 0 else 0.0
            
            # Red flag queries correctly flagged - use text() for string date comparison
            red_flag_events = self.db.query(func.count(SafetyEvent.id)).filter(
                and_(
                    SafetyEvent.was_red_flag_queried == True,
                    text("safety_events.created_at >= :period_start").bindparams(period_start=period_start)
                )
            ).scalar() or 0
            
            correctly_flagged = self.db.query(func.count(SafetyEvent.id)).filter(
                and_(
                    SafetyEvent.was_red_flag_queried == True,
                    SafetyEvent.was_red_flag_correctly_flagged == True,
                    text("safety_events.created_at >= :period_start").bindparams(period_start=period_start)
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
    
    def get_pmf_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Get Product-Market Fit panel metrics."""
        try:
            period_start = (datetime.utcnow() - timedelta(days=days)).isoformat()
            week_start = (datetime.utcnow() - timedelta(days=7)).isoformat()
            three_weeks_ago = (datetime.utcnow() - timedelta(days=21)).isoformat()
            two_weeks_ago = (datetime.utcnow() - timedelta(days=14)).isoformat()
            
            # Heavy users (>20 queries/week)
            # Count messages per user in the last week
            user_message_counts = self.db.query(
                DiagnosisSession.user_id,
                func.count(ChatMessage.id).label('message_count')
            ).join(
                ChatMessage, ChatMessage.session_id == DiagnosisSession.id
            ).filter(
                ChatMessage.message_type == 'user',
                DiagnosisSession.created_at >= week_start
            ).group_by(DiagnosisSession.user_id).having(
                func.count(ChatMessage.id) > 20
            ).subquery()
            
            # Count distinct heavy users
            heavy_users_subquery = self.db.query(user_message_counts.c.user_id).distinct().subquery()
            heavy_users = self.db.query(func.count(heavy_users_subquery.c.user_id)).scalar() or 0
            
            # Users active in week 3
            week3_subquery = self.db.query(DiagnosisSession.user_id).filter(
                and_(
                    DiagnosisSession.created_at >= three_weeks_ago,
                    DiagnosisSession.created_at < two_weeks_ago
                )
            ).distinct().subquery()
            week3_active = self.db.query(func.count(week3_subquery.c.user_id)).scalar() or 0
            
            # PMF survey responses - use enum directly for proper type handling
            pmf_surveys = self.db.query(Survey).filter(
                and_(
                    Survey.survey_type == SurveyType.PMF,
                    text("surveys.created_at >= :period_start").bindparams(period_start=period_start)
                )
            ).all()
            
            total_pmf_responses = len(pmf_surveys)
            very_disappointed_count = sum(1 for s in pmf_surveys if s.very_disappointed == True)
            very_disappointed_percentage = (very_disappointed_count / total_pmf_responses * 100) if total_pmf_responses > 0 else 0.0
            
            # Average PMF score - use enum directly for proper type handling
            avg_pmf_score_result = self.db.query(func.avg(Survey.pmf_score)).filter(
                and_(
                    Survey.survey_type == SurveyType.PMF,
                    Survey.pmf_score.isnot(None),
                    text("surveys.created_at >= :period_start").bindparams(period_start=period_start)
                )
            ).scalar()
            avg_pmf_score = float(avg_pmf_score_result) if avg_pmf_score_result is not None else 0.0
            
            # Replacement behavior
            replacement_counts = {}
            for survey in pmf_surveys:
                if survey.replacement_behavior:
                    replacement_counts[survey.replacement_behavior] = replacement_counts.get(survey.replacement_behavior, 0) + 1
            
            # Willingness to pay - use enum directly for proper type handling
            avg_wtp_result = self.db.query(func.avg(Survey.willingness_to_pay)).filter(
                and_(
                    Survey.survey_type == SurveyType.PMF,
                    Survey.willingness_to_pay.isnot(None),
                    text("surveys.created_at >= :period_start").bindparams(period_start=period_start)
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
    
    def get_all_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Get all dashboard metrics."""
        return {
            "usage": self.get_usage_metrics(days),
            "clinical_value": self.get_clinical_value_metrics(days),
            "safety": self.get_safety_metrics(days),
            "pmf": self.get_pmf_metrics(days),
            "period_days": days,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    def check_and_create_alerts(self) -> List[Alert]:
        """Check conditions and create alerts if thresholds are exceeded."""
        alerts_created = []
        try:
            last_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()
            
            # Check for critical safety events - use enum directly for proper type handling
            critical_events = self.db.query(SafetyEvent).filter(
                and_(
                    SafetyEvent.is_critical == True,
                    SafetyEvent.status == SafetyEventStatus.OPEN,
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
    
    def get_user_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get user statistics by type and activity."""
        try:
            period_start = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            # Total users
            total_users = self.db.query(func.count(User.id)).scalar() or 0
            
            # Active users
            active_users = self.db.query(func.count(User.id)).filter(
                User.is_active == True
            ).scalar() or 0
            
            # Users by role
            users_by_role = {}
            roles = self.db.query(User.role, func.count(User.id)).group_by(User.role).all()
            for role, count in roles:
                # Ensure role is not None and count is valid
                if role is not None:
                    users_by_role[str(role)] = int(count) if count is not None else 0
                else:
                    users_by_role["Unknown"] = users_by_role.get("Unknown", 0) + (int(count) if count is not None else 0)
            
            # Users by medical professional type
            users_by_type = {}
            types = self.db.query(
                User.medical_professional_type,
                func.count(User.id)
            ).filter(
                User.medical_professional_type.isnot(None)
            ).group_by(User.medical_professional_type).all()
            for prof_type, count in types:
                # Ensure prof_type is not None and is a valid string
                if prof_type is not None and isinstance(prof_type, str) and prof_type.strip():
                    users_by_type[str(prof_type)] = int(count) if count is not None else 0
                elif prof_type is None:
                    # Handle edge case where None might slip through
                    users_by_type["Unknown"] = users_by_type.get("Unknown", 0) + (int(count) if count is not None else 0)
            
            # Count users without a professional type
            users_without_type = self.db.query(func.count(User.id)).filter(
                or_(
                    User.medical_professional_type.is_(None),
                    User.medical_professional_type == ""
                )
            ).scalar() or 0
            if users_without_type > 0:
                users_by_type["Not Specified"] = users_without_type
            
            # Activated users (users with at least one session)
            activated_user_ids = self.db.query(DiagnosisSession.user_id).distinct().all()
            activated_user_ids_list = [row[0] for row in activated_user_ids if row[0] is not None]
            activated_users = len(activated_user_ids_list) if activated_user_ids_list else 0
            
            # New users in period
            new_users = self.db.query(func.count(User.id)).filter(
                text("users.created_at >= :period_start").bindparams(period_start=period_start)
            ).scalar() or 0
            
            # Users active in period (users with sessions in period)
            active_in_period = self.db.query(func.count(func.distinct(DiagnosisSession.user_id))).filter(
                text("diagnosis_sessions.created_at >= :period_start").bindparams(period_start=period_start)
            ).scalar() or 0
            
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
    
    def get_session_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get session statistics including active sessions and average length."""
        try:
            period_start = (datetime.utcnow() - timedelta(days=days)).isoformat()
            now = datetime.utcnow()
            
            # Total sessions
            total_sessions = self.db.query(func.count(DiagnosisSession.id)).filter(
                text("diagnosis_sessions.created_at >= :period_start").bindparams(period_start=period_start)
            ).scalar() or 0
            
            # Active sessions (sessions updated in last 24 hours)
            last_24h = (now - timedelta(hours=24)).isoformat()
            active_sessions = self.db.query(func.count(DiagnosisSession.id)).filter(
                text("diagnosis_sessions.updated_at >= :last_24h").bindparams(last_24h=last_24h)
            ).scalar() or 0
            
            # Average session length (in messages)
            session_lengths = self.db.query(
                DiagnosisSession.id,
                func.count(ChatMessage.id).label('message_count')
            ).join(
                ChatMessage, ChatMessage.session_id == DiagnosisSession.id
            ).filter(
                text("diagnosis_sessions.created_at >= :period_start").bindparams(period_start=period_start)
            ).group_by(DiagnosisSession.id).subquery()
            
            avg_length_result = self.db.query(func.avg(session_lengths.c.message_count)).scalar()
            avg_session_length = float(avg_length_result) if avg_length_result is not None else 0.0
            
            # Average session duration (time between first and last message)
            # This is approximate - we'll use created_at and updated_at
            sessions_with_duration = self.db.query(
                DiagnosisSession.id,
                DiagnosisSession.created_at,
                DiagnosisSession.updated_at
            ).filter(
                text("diagnosis_sessions.created_at >= :period_start").bindparams(period_start=period_start)
            ).all()
            
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
    
    def get_ai_response_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get AI response statistics including feedback and response times."""
        try:
            period_start = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            # Total AI responses (assistant messages)
            total_responses = self.db.query(func.count(ChatMessage.id)).filter(
                and_(
                    ChatMessage.message_type == 'assistant',
                    text("chat_messages.created_at >= :period_start").bindparams(period_start=period_start)
                )
            ).scalar() or 0
            
            # Responses with feedback - filter by feedback creation date to see recent feedback
            responses_with_feedback = self.db.query(func.count(MessageFeedback.id)).filter(
                text("message_feedback.created_at >= :period_start").bindparams(period_start=period_start)
            ).scalar() or 0
            
            # Helpful feedback - filter by feedback creation date
            helpful_count = self.db.query(func.count(MessageFeedback.id)).filter(
                and_(
                    MessageFeedback.feedback_type == 'helpful',
                    text("message_feedback.created_at >= :period_start").bindparams(period_start=period_start)
                )
            ).scalar() or 0
            
            # Not helpful feedback - filter by feedback creation date
            not_helpful_count = self.db.query(func.count(MessageFeedback.id)).filter(
                and_(
                    MessageFeedback.feedback_type == 'not_helpful',
                    text("message_feedback.created_at >= :period_start").bindparams(period_start=period_start)
                )
            ).scalar() or 0
            
            # Average rating - filter by feedback creation date
            avg_rating_result = self.db.query(func.avg(MessageFeedback.rating)).filter(
                and_(
                    MessageFeedback.rating.isnot(None),
                    text("message_feedback.created_at >= :period_start").bindparams(period_start=period_start)
                )
            ).scalar()
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
                    text("chat_messages.created_at >= :period_start").bindparams(period_start=period_start)
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
