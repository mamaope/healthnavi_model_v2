"""
Test script to verify admin metrics calculations match database.
Run this to debug metric calculation issues.
"""

import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, func, text, and_
from sqlalchemy.orm import sessionmaker
from healthnavi.models.user import User
from healthnavi.models.diagnosis_session import DiagnosisSession, ChatMessage, MessageFeedback
from healthnavi.models.admin import SafetyEvent, Survey

# Get database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', 'postgres')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'healthnavi_db')}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def test_helpful_feedback():
    """Test helpful feedback calculation."""
    print("\n=== Testing Helpful Feedback ===")
    
    # Get all feedback
    all_feedback = db.query(MessageFeedback).all()
    print(f"Total feedback records: {len(all_feedback)}")
    
    for fb in all_feedback[:5]:  # Show first 5
        print(f"  ID: {fb.id}, Type: {fb.feedback_type}, Created: {fb.created_at}")
    
    # Count by type
    helpful_count = db.query(func.count(MessageFeedback.id)).filter(
        MessageFeedback.feedback_type == 'helpful'
    ).scalar()
    not_helpful_count = db.query(func.count(MessageFeedback.id)).filter(
        MessageFeedback.feedback_type == 'not_helpful'
    ).scalar()
    
    print(f"\nHelpful: {helpful_count}")
    print(f"Not Helpful: {not_helpful_count}")
    print(f"Total: {helpful_count + not_helpful_count}")
    
    # Test with date filter
    period_start = (datetime.utcnow() - timedelta(days=30)).isoformat()
    print(f"\nPeriod start (30 days ago): {period_start}")
    
    # Using direct comparison
    total_with_date = db.query(func.count(MessageFeedback.id)).filter(
        MessageFeedback.created_at >= period_start
    ).scalar()
    print(f"Total feedback (last 30 days, direct): {total_with_date}")
    
    # Using text()
    total_with_text = db.query(func.count(MessageFeedback.id)).filter(
        text("message_feedback.created_at >= :period_start").bindparams(period_start=period_start)
    ).scalar()
    print(f"Total feedback (last 30 days, text()): {total_with_text}")
    
    # Helpful with date
    helpful_with_date = db.query(func.count(MessageFeedback.id)).filter(
        and_(
            MessageFeedback.feedback_type == 'helpful',
            MessageFeedback.created_at >= period_start
        )
    ).scalar()
    print(f"Helpful feedback (last 30 days, direct): {helpful_with_date}")
    
    helpful_with_text = db.query(func.count(MessageFeedback.id)).filter(
        and_(
            MessageFeedback.feedback_type == 'helpful',
            text("message_feedback.created_at >= :period_start").bindparams(period_start=period_start)
        )
    ).scalar()
    print(f"Helpful feedback (last 30 days, text()): {helpful_with_text}")
    
    # Check actual created_at values
    print("\nSample created_at values:")
    sample_feedback = db.query(MessageFeedback).limit(5).all()
    for fb in sample_feedback:
        print(f"  ID {fb.id}: {fb.created_at} (type: {type(fb.created_at).__name__})")
        if fb.created_at:
            print(f"    Comparison with period_start: {fb.created_at >= period_start}")

def test_surveys():
    """Test survey calculations."""
    print("\n=== Testing Surveys ===")
    
    all_surveys = db.query(Survey).all()
    print(f"Total survey records: {len(all_surveys)}")
    
    for survey in all_surveys[:5]:
        print(f"  ID: {survey.id}, Type: {survey.survey_type}, Created: {survey.created_at}")
    
    # Count by relevance
    relevant = db.query(func.count(Survey.id)).filter(
        Survey.query_relevance == True
    ).scalar()
    total_with_relevance = db.query(func.count(Survey.id)).filter(
        Survey.query_relevance.isnot(None)
    ).scalar()
    
    print(f"\nRelevant queries: {relevant}")
    print(f"Total with relevance field: {total_with_relevance}")

def test_chat_messages():
    """Test chat message calculations."""
    print("\n=== Testing Chat Messages ===")
    
    total_messages = db.query(func.count(ChatMessage.id)).scalar()
    user_messages = db.query(func.count(ChatMessage.id)).filter(
        ChatMessage.message_type == 'user'
    ).scalar()
    assistant_messages = db.query(func.count(ChatMessage.id)).filter(
        ChatMessage.message_type == 'assistant'
    ).scalar()
    
    print(f"Total messages: {total_messages}")
    print(f"User messages: {user_messages}")
    print(f"Assistant messages: {assistant_messages}")

if __name__ == "__main__":
    try:
        test_helpful_feedback()
        test_surveys()
        test_chat_messages()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
