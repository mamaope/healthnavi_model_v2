"""
Survey API endpoints for pilot surveys.
Allows users to view and submit survey responses.
"""
import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, text
from pydantic import BaseModel, Field

from healthnavi.core.database import get_db
from healthnavi.api.v1.auth import get_current_user, require_admin_role
from healthnavi.core.response_utils import create_success_response, create_error_response, ResponseTimer
from healthnavi.schemas import StandardResponse
from healthnavi.models.user import User
from healthnavi.models.admin import Survey, SurveyConfig, SurveyType

logger = logging.getLogger(__name__)

router = APIRouter()


# Survey question definitions
SURVEY_QUESTIONS = {
    "baseline": {
        "title": "Pre-Pilot Survey",
        "description": "Baseline survey before pilot starts",
        "sections": [
            {
                "title": "SECTION 1: Clinician Profile",
                "questions": [
                    {
                        "id": "Q1",
                        "text": "What is your clinical role?",
                        "type": "single_choice",
                        "options": ["Medical Officer", "Intern doctor", "Clinical Officer", "Specialist", "Other"],
                        "required": True
                    },
                    {
                        "id": "Q2",
                        "text": "Years of clinical practice",
                        "type": "single_choice",
                        "options": ["Less than 2 years", "2–5 years", "6–10 years", "More than 10 years"],
                        "required": True
                    },
                    {
                        "id": "Q3",
                        "text": "Primary care setting",
                        "type": "single_choice",
                        "options": ["Primary care clinic", "Telemedicine", "Outpatient hospital", "Inpatient hospital", "Other"],
                        "required": True
                    }
                ]
            },
            {
                "title": "SECTION 2: Current Information-Seeking Behavior",
                "questions": [
                    {
                        "id": "Q4",
                        "text": "How often do you need clinical information during patient care?",
                        "type": "single_choice",
                        "options": ["Multiple times per day", "Daily", "Weekly", "Rarely"],
                        "required": True
                    },
                    {
                        "id": "Q5",
                        "text": "What tools do you currently use to find clinical information?",
                        "type": "multiple_choice",
                        "options": ["Google search", "Medical textbooks", "UpToDate or similar", "WhatsApp / peer groups", "Asking a colleague", "National or WHO guidelines (PDFs)"],
                        "required": True
                    },
                    {
                        "id": "Q6",
                        "text": "What frustrates you most about your current approach?",
                        "type": "text",
                        "required": True
                    }
                ]
            },
            {
                "title": "SECTION 3: Time & Confidence",
                "questions": [
                    {
                        "id": "Q7",
                        "text": "On average, how long does it take to find a reliable answer?",
                        "type": "single_choice",
                        "options": ["Less than 2 minutes", "3–5 minutes", "6–10 minutes", "More than 10 minutes"],
                        "required": True
                    }
                ]
            }
        ]
    },
    "mid": {
        "title": "Mid-Pilot Survey",
        "description": "This short survey helps us improve the platform during the pilot. Responses are confidential and take less than 5 minutes.",
        "sections": [
            {
                "title": "SECTION 1: Usage",
                "questions": [
                    {
                        "id": "Q1",
                        "text": "How often have you used the platform in the last 7 days?",
                        "type": "single_choice",
                        "options": ["Daily", "3–4 times", "1–2 times", "I did not use it"],
                        "required": True
                    },
                    {
                        "id": "Q2",
                        "text": "What clinical scenarios did you use it for?",
                        "type": "multiple_choice",
                        "options": ["Differential diagnosis", "Treatment guidance", "Drug dosing / contraindications", "Identifying red flags", "Patient explanations"],
                        "required": True
                    }
                ]
            },
            {
                "title": "SECTION 2: Replacement Test",
                "questions": [
                    {
                        "id": "Q3",
                        "text": "What does this platform most often replace for you?",
                        "type": "single_choice",
                        "options": ["Google search", "Asking a colleague", "Textbooks", "WhatsApp / peer groups", "It does not replace anything yet"],
                        "required": True
                    }
                ]
            },
            {
                "title": "SECTION 3: Value & Time",
                "questions": [
                    {
                        "id": "Q4",
                        "text": "Compared to your usual approach, how much time does this save?",
                        "type": "single_choice",
                        "options": ["No time saved", "Less than 3 minutes", "3–5 minutes", "5–10 minutes", "More than 10 minutes"],
                        "required": True
                    },
                    {
                        "id": "Q5",
                        "text": "Did it improve clarity or confidence in your decision-making?",
                        "type": "single_choice",
                        "options": ["Yes, significantly", "Yes, somewhat", "No"],
                        "required": True
                    }
                ]
            },
            {
                "title": "SECTION 4: Trust & Safety",
                "questions": [
                    {
                        "id": "Q6",
                        "text": "How often do you double-check responses from the platform?",
                        "type": "single_choice",
                        "options": ["Always", "Often", "Sometimes", "Rarely"],
                        "required": True
                    },
                    {
                        "id": "Q7",
                        "text": "Have you encountered any incorrect or unsafe information?",
                        "type": "single_choice",
                        "options": ["No", "Yes (please describe)"],
                        "required": True
                    },
                    {
                        "id": "Q7a",
                        "text": "Please briefly describe the issue",
                        "type": "text",
                        "required": False,
                        "conditional": {"question": "Q7", "value": "Yes (please describe)"}
                    }
                ]
            }
        ]
    },
    "final": {
        "title": "Post-Pilot Survey",
        "description": "This survey helps us decide whether and how to scale the platform. Your honest feedback is essential.",
        "sections": [
            {
                "title": "SECTION 1: PMF CORE QUESTION",
                "questions": [
                    {
                        "id": "Q1",
                        "text": "How would you feel if you could no longer use this platform?",
                        "type": "single_choice",
                        "options": ["Very disappointed", "Somewhat disappointed", "Not disappointed"],
                        "required": True
                    }
                ]
            },
            {
                "title": "SECTION 2: Core Value",
                "questions": [
                    {
                        "id": "Q2",
                        "text": "What is the single biggest benefit of this platform for you?",
                        "type": "text",
                        "required": True
                    },
                    {
                        "id": "Q3",
                        "text": "What is the biggest limitation today?",
                        "type": "text",
                        "required": True
                    }
                ]
            },
            {
                "title": "SECTION 3: Habit Formation",
                "questions": [
                    {
                        "id": "Q4",
                        "text": "When you have a clinical question, what do you reach for first?",
                        "type": "single_choice",
                        "options": ["This platform", "Google search", "Asking a colleague", "Guidelines / textbooks"],
                        "required": True
                    }
                ]
            },
            {
                "title": "SECTION 4: Willingness to Pay",
                "questions": [
                    {
                        "id": "Q5",
                        "text": "Would you personally pay for this tool if it were available?",
                        "type": "single_choice",
                        "options": ["Yes", "Maybe", "No"],
                        "required": True
                    },
                    {
                        "id": "Q6",
                        "text": "Would you recommend this platform to your clinic or medical director?",
                        "type": "single_choice",
                        "options": ["Yes", "Maybe", "No"],
                        "required": True
                    },
                    {
                        "id": "Q7",
                        "text": "What would be a reasonable monthly price? (Optional)",
                        "type": "text",
                        "required": False
                    },
                    {
                        "id": "Q8",
                        "text": "If you were to add 2 features to this product, what would they be? What more would you like it to do for you?",
                        "type": "text",
                        "required": True
                    }
                ]
            },
            {
                "title": "SECTION 5: Advocacy",
                "questions": [
                    {
                        "id": "Q8",
                        "text": "Who else should definitely be using this platform?",
                        "type": "multiple_choice",
                        "options": ["Primary care clinicians", "Telemedicine clinicians", "Specialists", "Medical trainees"],
                        "required": True
                    }
                ]
            }
        ]
    }
}


class SurveySubmissionRequest(BaseModel):
    """Request model for submitting a survey."""
    survey_type: str = Field(..., description="Type of survey: baseline, mid, or final")
    responses: Dict[str, Any] = Field(..., description="Survey responses as key-value pairs")
    
    # Optional fields for backward compatibility with existing survey structure
    pmf_score: Optional[int] = Field(None, description="PMF score (0-10)")
    very_disappointed: Optional[bool] = Field(None, description="Very disappointed if product disappeared")
    willingness_to_pay: Optional[int] = Field(None, description="Willingness to pay amount")
    replacement_behavior: Optional[str] = Field(None, description="Replacement behavior")
    time_saved_minutes: Optional[int] = Field(None, description="Time saved in minutes")
    usefulness_score: Optional[int] = Field(None, description="Usefulness score (1-5)")
    query_relevance: Optional[bool] = Field(None, description="Query relevance")


@router.get("/available", response_model=StandardResponse)
async def get_available_surveys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of available surveys for the current user.
    Returns surveys that are visible and whether the user has already completed them.
    """
    with ResponseTimer() as timer:
        try:
            # Get all survey configs
            configs = db.query(SurveyConfig).all()
            config_dict = {config.survey_type: config for config in configs}
            
            # Get user's completed surveys
            user_surveys = db.query(Survey).filter(Survey.user_id == current_user.id).all()
            completed_types = {survey.survey_type.value for survey in user_surveys}
            
            available_surveys = []
            for survey_type in ["baseline", "mid", "final"]:
                config = config_dict.get(survey_type)
                if config and config.is_visible:
                    survey_def = SURVEY_QUESTIONS.get(survey_type, {})
                    available_surveys.append({
                        "survey_type": survey_type,
                        "title": config.title or survey_def.get("title", survey_type),
                        "description": config.description or survey_def.get("description", ""),
                        "is_completed": survey_type in completed_types,
                        "completed_at": next(
                            (s.created_at for s in user_surveys if s.survey_type.value == survey_type),
                            None
                        )
                    })
            
            return create_success_response(
                data={"surveys": available_surveys},
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting available surveys: {e}", exc_info=True)
            return create_error_response(
                message="Failed to retrieve available surveys",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/questions/{survey_type}", response_model=StandardResponse)
async def get_survey_questions(
    survey_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get survey questions for a specific survey type.
    """
    with ResponseTimer() as timer:
        try:
            # Check if survey is visible
            try:
                config = db.query(SurveyConfig).filter(SurveyConfig.survey_type == survey_type).first()
            except Exception as config_error:
                logger.error(f"Error querying SurveyConfig: {config_error}", exc_info=True)
                return create_error_response(
                    message=f"Database error: {str(config_error)}",
                    status_code=500,
                    execution_time=timer.get_execution_time()
                )
            
            if not config:
                logger.warning(f"Survey config not found for type: {survey_type}")
                return create_error_response(
                    message="Survey configuration not found. Please contact an administrator.",
                    status_code=404,
                    execution_time=timer.get_execution_time()
                )
            
            if not config.is_visible:
                return create_error_response(
                    message="Survey is not available",
                    status_code=404,
                    execution_time=timer.get_execution_time()
                )
            
            # Check if user already completed this survey
            survey_type_enum = None
            try:
                survey_type_enum = SurveyType[survey_type.upper()]
            except KeyError:
                logger.warning(f"Invalid survey type: {survey_type}")
                return create_error_response(
                    message="Invalid survey type",
                    status_code=400,
                    execution_time=timer.get_execution_time()
                )
            
            # Query for existing survey - use text() with enum value for proper type handling
            try:
                existing_survey = db.query(Survey).filter(
                    and_(
                        Survey.user_id == current_user.id,
                        text("surveys.survey_type = :survey_type").bindparams(survey_type=survey_type_enum.value)
                    )
                ).first()
            except Exception as survey_query_error:
                logger.error(f"Error querying Survey: {survey_query_error}", exc_info=True)
                # Continue without checking existing survey - not critical
                existing_survey = None
            
            survey_def = SURVEY_QUESTIONS.get(survey_type)
            if not survey_def:
                logger.warning(f"Survey definition not found for type: {survey_type}")
                return create_error_response(
                    message="Survey questions not found",
                    status_code=404,
                    execution_time=timer.get_execution_time()
                )
            
            # Safely get config attributes
            title = getattr(config, 'title', None) or survey_def.get("title", survey_type)
            description = getattr(config, 'description', None) or survey_def.get("description", "")
            
            return create_success_response(
                data={
                    "survey_type": survey_type,
                    "title": title,
                    "description": description,
                    "sections": survey_def.get("sections", []),
                    "is_completed": existing_survey is not None,
                    "completed_at": existing_survey.created_at if existing_survey else None
                },
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting survey questions for {survey_type}: {e}", exc_info=True)
            # Include more details in error message for debugging
            error_details = str(e)
            from healthnavi.core.config import get_config
            config = get_config()
            if config.application.debug:
                error_details = f"{type(e).__name__}: {str(e)}"
            
            return create_error_response(
                message=f"Failed to retrieve survey questions. {error_details}",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.post("/submit", response_model=StandardResponse)
async def submit_survey(
    survey_data: SurveySubmissionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit a survey response.
    """
    with ResponseTimer() as timer:
        try:
            # Validate survey type
            if survey_data.survey_type not in ["baseline", "mid", "final"]:
                return create_error_response(
                    message="Invalid survey type",
                    status_code=400,
                    execution_time=timer.get_execution_time()
                )
            
            # Check if survey is visible
            config = db.query(SurveyConfig).filter(SurveyConfig.survey_type == survey_data.survey_type).first()
            if not config or not config.is_visible:
                return create_error_response(
                    message="Survey is not available",
                    status_code=404,
                    execution_time=timer.get_execution_time()
                )
            
            # Check if user already completed this survey
            survey_type_enum = SurveyType[survey_data.survey_type.upper()]
            # Use text() with enum value for proper type handling
            existing_survey = db.query(Survey).filter(
                and_(
                    Survey.user_id == current_user.id,
                    text("surveys.survey_type = :survey_type").bindparams(survey_type=survey_type_enum.value)
                )
            ).first()
            
            if existing_survey:
                return create_error_response(
                    message="Survey already completed",
                    status_code=400,
                    execution_time=timer.get_execution_time()
                )
            
            # Extract PMF-related fields from responses for final survey
            very_disappointed = None
            willingness_to_pay = None
            replacement_behavior = None
            time_saved_minutes = None
            
            if survey_data.survey_type == "final":
                # Extract from responses
                responses = survey_data.responses
                if "Q1" in responses:
                    very_disappointed = responses["Q1"] == "Very disappointed"
                if "Q7" in responses and responses["Q7"]:
                    try:
                        willingness_to_pay = int(responses["Q7"])
                    except (ValueError, TypeError):
                        pass
                if "Q3" in responses:
                    replacement_behavior = responses["Q3"]
                if "Q4" in responses:
                    # Map time saved options to minutes
                    time_map = {
                        "No time saved": 0,
                        "Less than 3 minutes": 2,
                        "3–5 minutes": 4,
                        "5–10 minutes": 7,
                        "More than 10 minutes": 10
                    }
                    time_saved_minutes = time_map.get(responses["Q4"])
            
            # Use provided values or extracted values
            very_disappointed = survey_data.very_disappointed or very_disappointed
            willingness_to_pay = survey_data.willingness_to_pay or willingness_to_pay
            replacement_behavior = survey_data.replacement_behavior or replacement_behavior
            time_saved_minutes = survey_data.time_saved_minutes or time_saved_minutes
            
            # Create survey record
            from datetime import datetime
            now = datetime.utcnow().isoformat()
            
            # Create survey record
            # SQLEnum with values_callable should now use enum value (lowercase) instead of name (uppercase)
            survey = Survey(
                user_id=current_user.id,
                survey_type=survey_type_enum,  # SQLEnum will use the enum value thanks to values_callable
                pmf_score=survey_data.pmf_score,
                very_disappointed=very_disappointed,
                willingness_to_pay=willingness_to_pay,
                replacement_behavior=replacement_behavior,
                time_saved_minutes=time_saved_minutes,
                usefulness_score=survey_data.usefulness_score,
                query_relevance=survey_data.query_relevance,
                survey_data=json.dumps(survey_data.responses),
                created_at=now,
                updated_at=now
            )
            
            db.add(survey)
            db.commit()
            db.refresh(survey)
            
            return create_success_response(
                data={
                    "survey_id": survey.id,
                    "survey_type": survey.survey_type.value,
                    "message": "Survey submitted successfully"
                },
                status_code=201,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error submitting survey: {e}", exc_info=True)
            db.rollback()
            return create_error_response(
                message="Failed to submit survey",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/my-surveys", response_model=StandardResponse)
async def get_my_surveys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all surveys submitted by the current user.
    """
    with ResponseTimer() as timer:
        try:
            surveys = db.query(Survey).filter(Survey.user_id == current_user.id).order_by(Survey.created_at.desc()).all()
            
            surveys_data = []
            for survey in surveys:
                survey_dict = {
                    "id": survey.id,
                    "survey_type": survey.survey_type.value,
                    "created_at": survey.created_at,
                    "responses": json.loads(survey.survey_data) if survey.survey_data else {}
                }
                surveys_data.append(survey_dict)
            
            return create_success_response(
                data={"surveys": surveys_data},
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting user surveys: {e}", exc_info=True)
            return create_error_response(
                message="Failed to retrieve surveys",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/notification", response_model=StandardResponse)
async def get_survey_notification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if user should be notified about pending surveys.
    Returns notification status if there are pending surveys and it's been 2+ days since last reminder.
    """
    with ResponseTimer() as timer:
        try:
            from datetime import datetime, timedelta
            
            # Get all visible survey configs
            configs = db.query(SurveyConfig).filter(SurveyConfig.is_visible == True).all()
            
            pending_surveys = []
            for config in configs:
                # Check if user has already completed this survey
                survey_type_enum = SurveyType[config.survey_type.upper()]
                existing_survey = db.query(Survey).filter(
                    and_(
                        Survey.user_id == current_user.id,
                        text("surveys.survey_type = :survey_type").bindparams(survey_type=survey_type_enum.value)
                    )
                ).first()
                
                if not existing_survey:
                    pending_surveys.append({
                        "survey_type": config.survey_type,
                        "title": config.title
                    })
            
            # If no pending surveys, no notification needed
            if not pending_surveys:
                return create_success_response(
                    data={"has_notification": False, "pending_count": 0},
                    status_code=200,
                    execution_time=timer.get_execution_time()
                )
            
            # Check if it's been 2+ days since last reminder
            should_show_notification = True
            if current_user.survey_reminder_date:
                try:
                    last_reminder = datetime.fromisoformat(current_user.survey_reminder_date.replace('Z', '+00:00'))
                    days_since_reminder = (datetime.utcnow() - last_reminder.replace(tzinfo=None)).days
                    # Only show notification if it's been 2 or more days
                    should_show_notification = days_since_reminder >= 2
                except (ValueError, AttributeError):
                    # If date parsing fails, show notification
                    should_show_notification = True
            else:
                # If never reminded before, show notification
                should_show_notification = True
            
            return create_success_response(
                data={
                    "has_notification": should_show_notification,
                    "pending_count": len(pending_surveys),
                    "pending_surveys": pending_surveys
                },
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting survey notification: {e}", exc_info=True)
            return create_error_response(
                message="Failed to check survey notification",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.post("/notification/dismiss", response_model=StandardResponse)
async def dismiss_survey_notification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update the survey reminder date to now (dismisses the notification for 2 days).
    """
    with ResponseTimer() as timer:
        try:
            from datetime import datetime
            current_user.survey_reminder_date = datetime.utcnow().isoformat()
            db.commit()
            db.refresh(current_user)
            
            return create_success_response(
                data={"message": "Notification dismissed"},
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error dismissing survey notification: {e}", exc_info=True)
            db.rollback()
            return create_error_response(
                message="Failed to dismiss notification",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


# Admin endpoints
@router.put("/admin/config/{survey_type}/visibility", response_model=StandardResponse)
async def toggle_survey_visibility(
    survey_type: str,
    is_visible: bool = Query(..., description="Set survey visibility"),
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to toggle survey visibility.
    """
    with ResponseTimer() as timer:
        try:
            config = db.query(SurveyConfig).filter(SurveyConfig.survey_type == survey_type).first()
            if not config:
                return create_error_response(
                    message="Survey config not found",
                    status_code=404,
                    execution_time=timer.get_execution_time()
                )
            
            from datetime import datetime
            config.is_visible = is_visible
            config.updated_at = datetime.utcnow().isoformat()
            
            db.commit()
            db.refresh(config)
            
            return create_success_response(
                data={
                    "survey_type": config.survey_type,
                    "is_visible": config.is_visible,
                    "message": f"Survey visibility updated to {is_visible}"
                },
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error updating survey visibility: {e}", exc_info=True)
            db.rollback()
            return create_error_response(
                message="Failed to update survey visibility",
                status_code=500,
                execution_time=timer.get_execution_time()
            )


@router.get("/admin/config", response_model=StandardResponse)
async def get_survey_configs(
    current_user: User = Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to get all survey configurations.
    """
    with ResponseTimer() as timer:
        try:
            configs = db.query(SurveyConfig).order_by(SurveyConfig.survey_type).all()
            
            configs_data = [{
                "id": config.id,
                "survey_type": config.survey_type,
                "is_visible": config.is_visible,
                "title": config.title,
                "description": config.description,
                "created_at": config.created_at,
                "updated_at": config.updated_at
            } for config in configs]
            
            return create_success_response(
                data={"configs": configs_data},
                status_code=200,
                execution_time=timer.get_execution_time()
            )
        except Exception as e:
            logger.error(f"Error getting survey configs: {e}", exc_info=True)
            return create_error_response(
                message="Failed to retrieve survey configurations",
                status_code=500,
                execution_time=timer.get_execution_time()
            )
