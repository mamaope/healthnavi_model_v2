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
            
            # Total users
            total_users = self.db.query(func.count(User.id)).filter(
                User.is_active == True
            ).scalar() or 0
            
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
            
            # Total feedback - cast to string for proper comparison
            total_feedback = self.db.query(func.count(MessageFeedback.id)).filter(
                MessageFeedback.created_at >= period_start
            ).scalar() or 0
            
            # Helpful feedback - cast to string for proper comparison
            helpful_feedback = self.db.query(func.count(MessageFeedback.id)).filter(
                and_(
                    MessageFeedback.feedback_type == 'helpful',
                    MessageFeedback.created_at >= period_start
                )
            ).scalar() or 0
            
            helpful_percentage = (helpful_feedback / total_feedback * 100) if total_feedback > 0 else 0.0
            
            # Average usefulness score (rating) - direct string comparison
            avg_rating_result = self.db.query(func.avg(MessageFeedback.rating)).filter(
                and_(
                    MessageFeedback.rating.isnot(None),
                    MessageFeedback.created_at >= period_start
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
            
            # Log for debugging
            logger.debug(f"Clinical Value Metrics - Period: {days} days, Start: {period_start}")
            logger.debug(f"  Total feedback: {total_feedback}, Helpful: {helpful_feedback}, Percentage: {helpful_percentage:.2f}%")
            logger.debug(f"  Total survey queries: {total_survey_queries}, Relevant: {relevant_queries}, Percentage: {relevant_percentage:.2f}%")
            
            # Log for debugging - helps verify calculations match database
            logger.info(f"Clinical Value Metrics (last {days} days):")
            logger.info(f"  Total feedback: {total_feedback}, Helpful: {helpful_feedback}, Percentage: {helpful_percentage:.2f}%")
            logger.info(f"  Total survey queries: {total_survey_queries}, Relevant: {relevant_queries}, Percentage: {relevant_percentage:.2f}%")
            logger.info(f"  Avg usefulness score: {avg_rating:.2f}, Avg time saved: {avg_time_saved:.2f} min")
            
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
            
            # Open safety events - use text() to force string comparison and avoid enum conversion
            open_events = self.db.query(func.count(SafetyEvent.id)).filter(
                text("safety_events.status = 'open'")
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
            
            # PMF survey responses - use text() to force string comparison
            pmf_surveys = self.db.query(Survey).filter(
                and_(
                    text("surveys.survey_type = 'pmf'"),
                    text("surveys.created_at >= :period_start").bindparams(period_start=period_start)
                )
            ).all()
            
            total_pmf_responses = len(pmf_surveys)
            very_disappointed_count = sum(1 for s in pmf_surveys if s.very_disappointed == True)
            very_disappointed_percentage = (very_disappointed_count / total_pmf_responses * 100) if total_pmf_responses > 0 else 0.0
            
            # Average PMF score - use text() to force string comparison
            avg_pmf_score_result = self.db.query(func.avg(Survey.pmf_score)).filter(
                and_(
                    text("surveys.survey_type = 'pmf'"),
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
            
            # Willingness to pay - use text() to force string comparison
            avg_wtp_result = self.db.query(func.avg(Survey.willingness_to_pay)).filter(
                and_(
                    text("surveys.survey_type = 'pmf'"),
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
            
            # Check for critical safety events - use text() to force string comparison
            critical_events = self.db.query(SafetyEvent).filter(
                and_(
                    SafetyEvent.is_critical == True,
                    text("safety_events.status = 'open'"),
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
