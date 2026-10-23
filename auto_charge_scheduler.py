"""
Trial auto-charge and failed-charge retries, using Stripe.

- auto_charge_expiring_trials(): runs daily at 00:00 UTC, charges saved cards whose trial ends today.
- retry_failed_charges(): runs daily at 01:00 UTC, retries failed charges that are due.

Charges use the saved Stripe payment method (stored on the enrollment) and the
customer id stored on the user, so the customer does not need to be present.
"""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func

from database import SessionLocal
from models import CourseEnrollment, SubscriptionCharge
from stripe_payment import payment_processor

logger = logging.getLogger(__name__)


def _amount_cents(price) -> int:
    return int(round(float(price) * 100))


def auto_charge_expiring_trials():
    """Charge cards for enrollments whose trial ends today."""
    if not payment_processor.enabled:
        logger.warning("[Auto-Charge] Stripe is not configured. Skipping.")
        return

    db = SessionLocal()
    try:
        today = datetime.utcnow().date()
        expiring = db.query(CourseEnrollment).filter(
            func.date(CourseEnrollment.trial_ends_at) == today,
            CourseEnrollment.payment_method_id.isnot(None),
            CourseEnrollment.status == "trial",
            CourseEnrollment.auto_charge_attempted == False,  # noqa: E712
        ).all()

        logger.info(f"[Auto-Charge] Found {len(expiring)} enrollments to charge")

        for enrollment in expiring:
            course = enrollment.course
            user = enrollment.user
            enrollment.auto_charge_attempted = True

            if not user or not user.stripe_customer_id:
                _record_failure(db, enrollment, course, "No Stripe customer on file")
                continue

            ok, result = payment_processor.charge_saved(
                customer_id=user.stripe_customer_id,
                payment_method_id=enrollment.payment_method_id,
                amount_cents=_amount_cents(course.price),
                currency=course.currency or "USD",
                description=f"Auto-charge: {course.title}",
                idempotency_key=f"auto-charge-{enrollment.id}-{today.isoformat()}",
            )

            if ok:
                enrollment.status = "active"
                enrollment.access_expires_at = datetime.utcnow() + timedelta(days=365)
                db.add(SubscriptionCharge(
                    enrollment_id=enrollment.id,
                    amount=course.price,
                    status="success",
                    stripe_payment_id=result.get("payment_id"),
                    attempted_at=datetime.utcnow(),
                ))
                logger.info(f"✅ [Auto-Charge] SUCCESS - Enrollment {enrollment.id} charged {course.price}")
            else:
                _record_failure(db, enrollment, course, result.get("message", "Payment failed"))

            db.commit()

    except Exception as err:
        db.rollback()
        logger.error(f"❌ [Auto-Charge] Scheduler error: {err}")
    finally:
        db.close()


def retry_failed_charges():
    """Retry failed charges that are due."""
    if not payment_processor.enabled:
        logger.warning("[Retry-Charge] Stripe is not configured. Skipping.")
        return

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        failed = db.query(SubscriptionCharge).filter(
            SubscriptionCharge.status == "failed",
            SubscriptionCharge.next_retry_at <= now,
        ).all()

        logger.info(f"[Retry-Charge] Found {len(failed)} failed charges to retry")

        for charge in failed:
            enrollment = charge.enrollment
            user = enrollment.user if enrollment else None

            if not enrollment or not enrollment.payment_method_id or not user or not user.stripe_customer_id:
                logger.warning(f"[Retry-Charge] No saved card or customer for charge {charge.id}")
                continue

            course = enrollment.course
            ok, result = payment_processor.charge_saved(
                customer_id=user.stripe_customer_id,
                payment_method_id=enrollment.payment_method_id,
                amount_cents=_amount_cents(course.price),
                currency=course.currency or "USD",
                description=f"Retry: {course.title}",
                idempotency_key=f"retry-charge-{charge.id}-{now.date().isoformat()}",
            )

            if ok:
                charge.status = "success"
                charge.stripe_payment_id = result.get("payment_id")
                enrollment.status = "active"
                enrollment.access_expires_at = now + timedelta(days=365)
                logger.info(f"✅ [Retry-Charge] SUCCESS - Charge {charge.id} completed")
            else:
                charge.next_retry_at = now + timedelta(days=1)
                charge.error_message = result.get("message", "Payment failed")
                logger.error(f"❌ [Retry-Charge] FAILED - Charge {charge.id} will retry tomorrow")
            db.commit()

    except Exception as err:
        db.rollback()
        logger.error(f"❌ [Retry-Charge] Scheduler error: {err}")
    finally:
        db.close()


def _record_failure(db, enrollment, course, message: str):
    enrollment.status = "payment_failed"
    db.add(SubscriptionCharge(
        enrollment_id=enrollment.id,
        amount=course.price,
        status="failed",
        error_message=message,
        attempted_at=datetime.utcnow(),
        next_retry_at=datetime.utcnow() + timedelta(days=1),  # retry tomorrow
    ))
    logger.error(f"❌ [Auto-Charge] FAILED - Enrollment {enrollment.id}: {message}")


# Global scheduler instance
scheduler = BackgroundScheduler()


def start_scheduler():
    """Called from main.py on startup."""
    if scheduler.running:
        return

    scheduler.add_job(auto_charge_expiring_trials, "cron", hour=0, minute=0,
                      id="auto_charge_job", replace_existing=True)
    scheduler.add_job(retry_failed_charges, "cron", hour=1, minute=0,
                      id="retry_charge_job", replace_existing=True)

    logger.info("✅ Subscription auto-charge scheduler started (Stripe)")
    logger.info("   → Auto-charge runs daily at 00:00 UTC")
    logger.info("   → Retry runs daily at 01:00 UTC")
    scheduler.start()


if __name__ == "__main__":
    import time
    start_scheduler()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
