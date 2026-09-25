"""
Auto-charge background job - Runs daily to charge users after trial ends.

Features:
- Checks for expired trials
- Charges saved cards via Square
- Transitions status from 'trial' to 'active'
- Sets subscription end date (e.g., 30 days from charge)
- Handles failed charges

Run with: python -m schedule (add to Railway cron job)
Or: Run manually with `python auto_charge_job.py`
"""

import os
import schedule
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from database import SessionLocal, engine
from models import CourseEnrollment, Course, Payment, User
import squareClient  # Your Square SDK integration

Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def auto_charge_expired_trials():
    """
    Daily job to auto-charge expired trials.
    
    Process:
    1. Find all enrollments with status='trial' and trial_ends_at < now
    2. Check if they have a payment_method_id (saved card)
    3. Charge the card via Square
    4. If successful: update status to 'active' and set access_expires_at
    5. If failed: send email to user + keep status as 'trial' (retry tomorrow)
    """
    
    db = SessionLocal()
    now = datetime.utcnow()
    
    print(f"[auto_charge_job] Starting at {now}")
    
    try:
        # Find expired trials with payment method
        expired_trials = db.query(CourseEnrollment).filter(
            CourseEnrollment.status == "trial",
            CourseEnrollment.trial_ends_at < now,
            CourseEnrollment.payment_method_id.isnot(None)
        ).all()
        
        print(f"[auto_charge_job] Found {len(expired_trials)} expired trials with saved cards")
        
        for enrollment in expired_trials:
            try:
                # Get course price
                course = db.query(Course).filter(
                    Course.id == enrollment.course_id
                ).first()
                
                if not course:
                    print(f"[auto_charge_job] Course {enrollment.course_id} not found, skipping")
                    continue
                
                # Get user email
                user = db.query(User).filter(
                    User.id == enrollment.user_id
                ).first()
                
                # Charge the card via Square
                amount_cents = int(course.price * 100) if course.price else 10000  # Default $100
                
                charge_result = squareClient.charge_card(
                    nonce=enrollment.payment_method_id,
                    amount_cents=amount_cents,
                    currency='USD',
                    reference_id=f"auto_charge_{enrollment.id}_{now.timestamp()}",
                    idempotency_key=f"auto_charge_{enrollment.id}"
                )
                
                if charge_result.get('success'):
                    # ✅ Charge successful
                    transaction_id = charge_result.get('transaction_id')
                    
                    # Create payment record
                    payment = Payment(
                        enrollment_id=enrollment.id,
                        user_id=enrollment.user_id,
                        course_id=enrollment.course_id,
                        amount=course.price or 100.0,
                        currency='USD',
                        status='completed',
                        payment_method='square',
                        transaction_id=transaction_id
                    )
                    db.add(payment)
                    
                    # Update enrollment
                    enrollment.status = 'active'
                    enrollment.access_expires_at = now + timedelta(days=30)  # 30-day subscription
                    enrollment.last_accessed_at = now
                    
                    print(f"✅ [auto_charge_job] Charged user {enrollment.user_id} for course {enrollment.course_id}")
                    print(f"   Amount: ${course.price}, Transaction: {transaction_id}")
                    
                    # TODO: Send email to user
                    # send_email(user.email, "Subscription Renewed", f"Your {course.title} subscription has been renewed for 30 days.")
                    
                else:
                    # ❌ Charge failed
                    error_msg = charge_result.get('error', 'Unknown error')
                    
                    print(f"❌ [auto_charge_job] Failed to charge user {enrollment.user_id}: {error_msg}")
                    
                    # Create failed payment record
                    payment = Payment(
                        enrollment_id=enrollment.id,
                        user_id=enrollment.user_id,
                        course_id=enrollment.course_id,
                        amount=course.price or 100.0,
                        currency='USD',
                        status='failed',
                        payment_method='square'
                    )
                    db.add(payment)
                    
                    # TODO: Send email to user about payment failure
                    # send_email(user.email, "Payment Failed", f"Your card was declined. Please update your payment method.")
                
                db.commit()
                
            except Exception as e:
                db.rollback()
                print(f"❌ [auto_charge_job] Error processing enrollment {enrollment.id}: {str(e)}")
                continue
        
        print(f"[auto_charge_job] Completed successfully")
        
    except Exception as e:
        print(f"❌ [auto_charge_job] Fatal error: {str(e)}")
    finally:
        db.close()


def schedule_jobs():
    """Schedule the auto-charge job to run daily at 2 AM UTC"""
    schedule.every().day.at("02:00").do(auto_charge_expired_trials)
    
    print("[scheduler] Auto-charge job scheduled daily at 02:00 UTC")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute if a job is due


if __name__ == "__main__":
    # Run once on startup
    auto_charge_expired_trials()
    
    # Then schedule for daily runs
    schedule_jobs()