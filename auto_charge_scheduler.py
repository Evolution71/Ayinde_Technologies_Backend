"""
Auto-charge scheduler for trial subscriptions
Updated to use environment variables instead of hardcoded tokens
Run with: python -m uvicorn main:app (starts automatically)
"""
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from database import SessionLocal
from models import CourseEnrollment, SubscriptionCharge, Payment, Course
import square
from sqlalchemy import func
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get from environment (set in Railway)
SQUARE_ACCESS_TOKEN = os.getenv("SQUARE_ACCESS_TOKEN")
SQUARE_LOCATION_ID = os.getenv("SQUARE_LOCATION_ID")

# Validate on startup
if not SQUARE_ACCESS_TOKEN or not SQUARE_LOCATION_ID:
    logger.warning("⚠️ Square credentials not configured. Auto-charge disabled.")
    SQUARE_ACCESS_TOKEN = None
    SQUARE_LOCATION_ID = None

def auto_charge_expiring_trials():
    """
    Run daily at midnight UTC (00:00)
    Charge cards for enrollments where trial_ends_at == today
    """
    if not SQUARE_ACCESS_TOKEN or not SQUARE_LOCATION_ID:
        logger.warning("[Auto-Charge] Square credentials not configured. Skipping.")
        return
    
    db = SessionLocal()
    
    try:
        # Find all trial enrollments where trial ends TODAY and card is saved
        today = datetime.utcnow().date()
        
        expiring = db.query(CourseEnrollment).filter(
            func.date(CourseEnrollment.trial_ends_at) == today,
            CourseEnrollment.payment_method_id.isnot(None),
            CourseEnrollment.status == 'trial',
            CourseEnrollment.auto_charge_attempted == False
        ).all()
        
        logger.info(f"[Auto-Charge] Found {len(expiring)} enrollments to charge")
        
        client = square.Client(access_token=SQUARE_ACCESS_TOKEN)
        
        for enrollment in expiring:
            try:
                course = enrollment.course
                amount_cents = int(float(course.price) * 100)  # Convert to cents
                
                logger.info(f"[Auto-Charge] Charging enrollment {enrollment.id} for course {course.title} - ${course.price}")
                
                # Create payment with saved card token
                result = client.payments.create_payment(
                    body={
                        'source_id': enrollment.payment_method_id,  # ← Saved card token
                        'amount_money': {
                            'amount': amount_cents,
                            'currency': 'USD'
                        },
                        'location_id': SQUARE_LOCATION_ID,
                        'idempotency_key': f"auto-charge-{enrollment.id}-{today.isoformat()}",
                        'note': f'Auto-charge for {course.title}'
                    }
                )
                
                # Mark as attempted (don't retry today)
                enrollment.auto_charge_attempted = True
                
                if result.is_success():
                    payment_id = result.result.get('payment', {}).get('id')
                    
                    # ✅ Charge succeeded
                    enrollment.status = 'active'
                    enrollment.access_expires_at = datetime.utcnow() + timedelta(days=365)
                    
                    # Log charge
                    charge = SubscriptionCharge(
                        enrollment_id=enrollment.id,
                        amount=course.price,
                        status='success',
                        square_payment_id=payment_id,
                        attempted_at=datetime.utcnow()
                    )
                    
                    payment_record = Payment(
                        user_id=enrollment.user_id,
                        course_id=enrollment.course_id,
                        amount=course.price,
                        status='success',
                        payment_method='square_auto_charge',
                        transaction_id=payment_id,
                        created_at=datetime.utcnow()
                    )
                    
                    db.add(charge)
                    db.add(payment_record)
                    db.commit()
                    
                    logger.info(f"✅ [Auto-Charge] SUCCESS - Enrollment {enrollment.id} charged ${course.price}")
                    
                elif result.is_error():
                    # ❌ Charge failed
                    error_msg = ', '.join([str(e.get('detail', e)) for e in result.errors])
                    
                    enrollment.status = 'payment_failed'
                    
                    charge = SubscriptionCharge(
                        enrollment_id=enrollment.id,
                        amount=course.price,
                        status='failed',
                        error_message=error_msg,
                        attempted_at=datetime.utcnow(),
                        next_retry_at=datetime.utcnow() + timedelta(days=1)  # Retry tomorrow
                    )
                    
                    db.add(charge)
                    db.commit()
                    
                    logger.error(f"❌ [Auto-Charge] FAILED - Enrollment {enrollment.id}: {error_msg}")
                    
            except Exception as err:
                logger.error(f"❌ [Auto-Charge] ERROR for enrollment {enrollment.id}: {str(err)}")
                enrollment.status = 'payment_failed'
                enrollment.auto_charge_attempted = True
                
                charge = SubscriptionCharge(
                    enrollment_id=enrollment.id,
                    amount=enrollment.course.price,
                    status='failed',
                    error_message=str(err),
                    attempted_at=datetime.utcnow(),
                    next_retry_at=datetime.utcnow() + timedelta(days=1)
                )
                db.add(charge)
                db.commit()
        
    except Exception as err:
        logger.error(f"❌ [Auto-Charge] Scheduler error: {str(err)}")
    finally:
        db.close()


def retry_failed_charges():
    """
    Run daily at 01:00 UTC
    Retry failed charges that are ready for retry
    """
    if not SQUARE_ACCESS_TOKEN or not SQUARE_LOCATION_ID:
        logger.warning("[Retry-Charge] Square credentials not configured. Skipping.")
        return
    
    db = SessionLocal()
    
    try:
        now = datetime.utcnow()
        failed_charges = db.query(SubscriptionCharge).filter(
            SubscriptionCharge.status == 'failed',
            SubscriptionCharge.next_retry_at <= now
        ).all()
        
        logger.info(f"[Retry-Charge] Found {len(failed_charges)} failed charges to retry")
        
        client = square.Client(access_token=SQUARE_ACCESS_TOKEN)
        
        for charge in failed_charges:
            enrollment = charge.enrollment
            
            if not enrollment.payment_method_id:
                logger.warning(f"[Retry-Charge] No payment method for enrollment {enrollment.id}")
                continue
            
            try:
                course = enrollment.course
                amount_cents = int(float(course.price) * 100)
                
                result = client.payments.create_payment(
                    body={
                        'source_id': enrollment.payment_method_id,
                        'amount_money': {
                            'amount': amount_cents,
                            'currency': 'USD'
                        },
                        'location_id': SQUARE_LOCATION_ID,
                        'idempotency_key': f"retry-charge-{charge.id}-{now.isoformat()}",
                        'note': f'Retry: {course.title}'
                    }
                )
                
                if result.is_success():
                    charge.status = 'success'
                    charge.square_payment_id = result.result.get('payment', {}).get('id')
                    
                    enrollment.status = 'active'
                    enrollment.access_expires_at = now + timedelta(days=365)
                    
                    db.commit()
                    logger.info(f"✅ [Retry-Charge] SUCCESS - Charge {charge.id} completed")
                else:
                    charge.next_retry_at = now + timedelta(days=1)
                    charge.error_message = ', '.join([str(e.get('detail', e)) for e in result.errors])
                    db.commit()
                    logger.error(f"❌ [Retry-Charge] FAILED - Charge {charge.id} will retry tomorrow")
                    
            except Exception as err:
                logger.error(f"❌ [Retry-Charge] ERROR for charge {charge.id}: {str(err)}")
                charge.next_retry_at = now + timedelta(days=1)
                db.commit()
        
    except Exception as err:
        logger.error(f"❌ [Retry-Charge] Scheduler error: {str(err)}")
    finally:
        db.close()


# Global scheduler instance
scheduler = BackgroundScheduler()

def start_scheduler():
    """Called from main.py on startup"""
    if scheduler.running:
        return
    
    # Run auto-charge every day at 00:00 UTC
    scheduler.add_job(auto_charge_expiring_trials, 'cron', hour=0, minute=0, id='auto_charge_job', replace_existing=True)
    
    # Run retry at 01:00 UTC
    scheduler.add_job(retry_failed_charges, 'cron', hour=1, minute=0, id='retry_charge_job', replace_existing=True)
    
    logger.info("✅ Subscription auto-charge scheduler started")
    logger.info("   → Auto-charge runs daily at 00:00 UTC")
    logger.info("   → Retry runs daily at 01:00 UTC")
    scheduler.start()


if __name__ == '__main__':
    start_scheduler()
    try:
        # Keep scheduler running
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()
        logger.info("Scheduler stopped")