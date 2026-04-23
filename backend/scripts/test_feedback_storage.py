"""
Test script to verify feedback is being stored in the database.
Run this after submitting feedback to check if it's saved.
"""

import sys
import os

# Add the backend src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy.orm import Session
from healthnavi.core.database import get_db
from healthnavi.models.diagnosis_session import MessageFeedback, ChatMessage
from sqlalchemy import desc

def check_recent_feedback():
    """Check the most recent feedback entries in the database."""
    db: Session = next(get_db())
    
    try:
        # Get the 10 most recent feedback entries
        recent_feedback = db.query(MessageFeedback).order_by(
            desc(MessageFeedback.created_at)
        ).limit(10).all()
        
        print(f"\n=== Recent Feedback Entries (Last 10) ===\n")
        
        if not recent_feedback:
            print("No feedback entries found in the database.")
            return
        
        for feedback in recent_feedback:
            # Get the associated message
            message = db.query(ChatMessage).filter(
                ChatMessage.id == feedback.message_id
            ).first()
            
            print(f"Feedback ID: {feedback.id}")
            print(f"  Message ID: {feedback.message_id}")
            print(f"  User ID: {feedback.user_id}")
            print(f"  Type: {feedback.feedback_type}")
            print(f"  Rating: {feedback.rating}")
            print(f"  Feedback Text: {feedback.feedback_text[:50] if feedback.feedback_text else 'None'}...")
            print(f"  Created At: {feedback.created_at}")
            print(f"  Updated At: {feedback.updated_at}")
            if message:
                print(f"  Message Type: {message.message_type}")
                print(f"  Message Preview: {message.content[:50]}...")
            print()
        
        # Get statistics
        total_feedback = db.query(MessageFeedback).count()
        helpful_count = db.query(MessageFeedback).filter(
            MessageFeedback.feedback_type == 'helpful'
        ).count()
        not_helpful_count = db.query(MessageFeedback).filter(
            MessageFeedback.feedback_type == 'not_helpful'
        ).count()
        
        print(f"\n=== Statistics ===")
        print(f"Total Feedback: {total_feedback}")
        print(f"Helpful: {helpful_count}")
        print(f"Not Helpful: {not_helpful_count}")
        print(f"Helpful %: {(helpful_count / total_feedback * 100) if total_feedback > 0 else 0:.2f}%")
        
    except Exception as e:
        print(f"Error checking feedback: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    check_recent_feedback()
