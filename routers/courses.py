"""
Courses, lessons, and enrollment endpoints with subscription system.

Features:
- Browse courses (public or logged in)
- Free 30-day trial for all courses
- Track progress through lessons
- Payment integration (Stripe)
- Auto-charge after trial ends
- Cancel subscription

Endpoints:
- GET /api/courses - List all courses
- GET /api/courses/me/enrollments - Get user's enrolled courses
- GET /api/courses/{id} - Get course details (requires enrollment)
- GET /api/courses/{id}/enrollment-status - Get enrollment & trial status
- POST /api/courses/{id}/enroll - Start free trial (with card)
- POST /api/courses/{id}/cancel - Cancel subscription
- GET /api/courses/{id}/lessons/{lesson_id} - Get lesson
- POST /api/courses/{id}/lessons/{lesson_id}/complete - Mark complete
- GET /api/courses/{id}/progress - Get user's course progress
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from database import get_db
from stripe_payment import payment_processor
from auth import get_current_user, get_current_user_optional
from models import User, Course, CourseEnrollment, Lesson, LessonProgress, Payment
import schemas

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/courses", tags=["courses"])


# ========== GET USER'S ENROLLMENTS ==========

@router.get("/me/enrollments/")
async def get_my_enrollments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of courses the current user is enrolled in.
    Returns course IDs for frontend to mark as "✅ Enrolled"
    
    Returns: List of enrolled course IDs
    """
    enrollments = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id
    ).all()
    
    return {
        "success": True,
        "enrollments": [
            {
                "course_id": e.course_id,
                "status": e.status,
                "trial_ends_at": e.trial_ends_at,
                "enrolled_at": e.enrolled_at
            }
            for e in enrollments
        ]
    }


# ========== GET ENROLLMENT STATUS ==========

@router.get("/{course_id}/enrollment-status/")
async def get_enrollment_status(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get enrollment and trial status for a course.
    
    Returns: Trial end date, subscription status, payment method
    
    Errors:
    - 404: Course not found
    - 403: Not enrolled
    """
    
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id
    ).first()
    
    if not enrollment:
        # Not an error: the learner simply has not started this course yet
        return {
            "course_id": course_id,
            "status": "not_enrolled",
            "trial_ends_at": None,
            "days_remaining": 0,
            "has_payment_method": False,
            "enrolled_at": None,
        }
    
    now = datetime.utcnow()
    days_remaining = 0
    
    # FIX: Properly calculate days remaining
    if enrollment.status == "trial" and enrollment.trial_ends_at:
        time_diff = enrollment.trial_ends_at - now
        days_remaining = time_diff.days
        
        # If trial has expired, update status
        if days_remaining < 0:
            enrollment.status = "expired"
            db.commit()
            days_remaining = 0
    
    logger.info(f"[enrollment-status] course_id={course_id}, user_id={current_user.id}, status={enrollment.status}, days_remaining={days_remaining}")
    
    return {
        "course_id": course_id,
        "status": enrollment.status,
        "trial_ends_at": enrollment.trial_ends_at.isoformat() if enrollment.trial_ends_at else None,
        "days_remaining": days_remaining,
        "has_payment_method": bool(enrollment.payment_method_id),
        "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None
    }


# ========== ENROLL IN COURSE (with card) ==========

@router.post("/{course_id}/enroll/")
async def enroll_in_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start a free trial for a course.
    
    Features:
    - 30-day free access to all course content
    - After trial ends, user must pay to continue
    - Can re-enroll if access expires
    - Frontend will collect card info for auto-charge
    
    Returns: Enrollment confirmation with trial end date
    
    Errors:
    - 404: Course not found
    - 400: Already has active access
    """
    
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if already enrolled with active access
    existing = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id
    ).first()
    
    if existing and existing.status in ["trial", "active"]:
        return {
            "status": "already_enrolled",
            "message": f"You already have {existing.status} access to this course.",
            "enrollment_id": existing.id
        }
    
    # ===== FIX: Properly set trial duration to 30 days =====
    # Always use 30 days, never 0
    trial_days = 30
    
    # Only override if course has explicit trial_duration_days > 0
    if hasattr(course, 'trial_duration_days') and course.trial_duration_days and course.trial_duration_days > 0:
        trial_days = course.trial_duration_days
    
    now = datetime.utcnow()
    trial_ends_at = now + timedelta(days=trial_days)
    
    # Create new enrollment with trial
    enrollment = CourseEnrollment(
        user_id=current_user.id,
        course_id=course_id,
        status="trial",
        enrolled_at=now,
        trial_ends_at=trial_ends_at,
        progress_percentage=0.0,
        auto_charge_attempted=False
    )
    
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    
    logger.info(f"[enroll] Trial started: user_id={current_user.id}, course_id={course_id}, trial_days={trial_days}, trial_ends={trial_ends_at}")
    
    return {
        "success": True,
        "enrollment_id": enrollment.id,
        "status": "trial",
        "trial_ends_at": trial_ends_at.isoformat(),
        "days": trial_days,
        "message": f"Free {trial_days}-day trial started! Card will be charged after trial ends."
    }


# ========== SAVE PAYMENT METHOD (FIXED) ==========

@router.post("/{course_id}/setup-intent/")
async def create_card_setup_intent(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start saving a card for a trial course (Stripe SetupIntent).

    The frontend confirms the returned client_secret with Stripe.js, then calls
    save-payment-method with the setup_intent_id.
    """
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    if not payment_processor.enabled:
        raise HTTPException(status_code=503, detail="Card saving is not available right now")

    try:
        if not current_user.stripe_customer_id:
            name = " ".join(p for p in [current_user.first_name, current_user.last_name] if p)
            current_user.stripe_customer_id = payment_processor.ensure_customer(
                email=current_user.email,
                name=name,
                user_id=current_user.id,
            )
            db.commit()

        intent = payment_processor.create_setup_intent(current_user.stripe_customer_id)
    except Exception as e:
        db.rollback()
        logger.error(f"[setup-intent] Stripe error for user {current_user.id}: {e}")
        raise HTTPException(status_code=502, detail="Could not start card setup. Please try again.")

    return {
        "success": True,
        "client_secret": intent["client_secret"],
        "setup_intent_id": intent["id"],
    }


@router.post("/{course_id}/save-payment-method/")
async def save_payment_method(
    course_id: int,
    request: schemas.SavePaymentMethodRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Save the card confirmed through a Stripe SetupIntent as the payment method for a course.

    The SetupIntent must have succeeded and belong to this user's Stripe customer.
    """
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    if not current_user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="Start card setup first")

    try:
        intent = payment_processor.retrieve_setup_intent(request.setup_intent_id)
    except Exception as e:
        logger.error(f"[payment-method] Could not retrieve SetupIntent: {e}")
        raise HTTPException(status_code=400, detail="Card setup could not be verified")

    if intent.status != "succeeded" or intent.customer != current_user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="Card setup was not completed")

    payment_method_id = intent.payment_method if isinstance(intent.payment_method, str) else getattr(intent.payment_method, "id", None)
    if not payment_method_id or not payment_method_id.startswith("pm_"):
        raise HTTPException(status_code=400, detail="No card was saved")

    try:
        enrollment.payment_method_id = payment_method_id
        enrollment.updated_at = datetime.utcnow()
        db.commit()
        logger.info(f"[payment-method] Saved card for user_id={current_user.id}, course_id={course_id}")
        return {
            "success": True,
            "message": "Payment method saved successfully",
            "enrollment_id": enrollment.id
        }
    except Exception as e:
        db.rollback()
        logger.error(f"[payment-method] Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to save payment method")


# ========== CANCEL SUBSCRIPTION ==========

@router.post("/{course_id}/cancel/")
async def cancel_subscription(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel subscription for a course.
    User loses access immediately.
    """
    
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found"
        )
    
    enrollment.status = "cancelled"
    db.commit()
    
    logger.info(f"[cancel] user_id={current_user.id}, course_id={course_id}")
    
    return {
        "success": True,
        "message": "Subscription cancelled"
    }


# ========== GET COURSE PROGRESS ==========

@router.get("/{course_id}/progress/")
async def get_course_progress(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's progress through a course.
    """
    
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enrolled"
        )
    
    # Get lesson progress
    lesson_progress = db.query(LessonProgress).filter(
        LessonProgress.user_id == current_user.id
    ).join(Lesson).filter(
        Lesson.course_id == course_id
    ).all()
    
    return {
        "course_id": course_id,
        "progress_percentage": enrollment.progress_percentage,
        "lessons_completed": len([lp for lp in lesson_progress if lp.is_completed]),
        "total_lessons": db.query(Lesson).filter(Lesson.course_id == course_id).count(),
        "last_accessed": enrollment.last_accessed_at
    }


# ========== LIST ALL COURSES ==========

# ========== LIST ALL COURSES ==========
# ⚠️ IMPORTANT: This route MUST come LAST because it matches any path
# If placed before specific routes like /{course_id}/, it will intercept them

@router.get("/")
async def get_courses(db: Session = Depends(get_db)):
    """
    Get list of all available courses.
    """
    courses = db.query(Course).filter(Course.is_published == True).all()
    
    return {
        "success": True,
        "courses": [
            {
                "id": c.id,
                "title": c.title,
                "description": c.description,
                "price": c.price,
                "icon": c.icon,
                "instructor": c.instructor,
                "level": c.level,
                "duration": c.duration,
                "trial_duration_days": c.trial_duration_days or 30
            }
            for c in courses
        ]
    }

def _youtube_course_out(c: Course) -> dict:
    """Public shape of a course on the YouTube section. Price is the exact checkout price."""
    return {
        "id": c.id,
        "title": c.title,
        "description": c.description,
        "instructor": c.instructor,
        "level": c.level,
        "duration": c.duration,
        "price": c.price,
        "currency": c.currency or "USD",
        "youtube_url": c.youtube_url,
        "youtube_live_url": c.youtube_live_url,
        "practical_code_url": c.practical_code_url,
        "notes": [line.strip() for line in (c.course_notes or "").splitlines() if line.strip()],
        "checkout_url": f"/checkout/{c.id}",
    }


@router.get("/youtube/")
async def get_youtube_courses(db: Session = Depends(get_db)):
    """
    Courses that are published on our YouTube channel.
    Only courses with show_on_youtube = true, is_published = true and is_active = true are returned.
    """
    rows = (
        db.query(Course)
        .filter(
            Course.is_published == True,
            Course.is_active == True,
            Course.show_on_youtube == True,
        )
        .order_by(Course.id)
        .all()
    )
    return {"success": True, "courses": [_youtube_course_out(c) for c in rows]}


# ========== GET COURSE DETAILS ==========

@router.get("/{course_id}/")
async def get_course_detail(
    course_id: int,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a course.
    Requires enrollment to view lessons.
    """
    
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if user is enrolled
    enrollment = None
    if current_user:
        enrollment = db.query(CourseEnrollment).filter(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.course_id == course_id
        ).first()
    
    # Only return lessons if enrolled
    lessons = []
    if enrollment and enrollment.status in ["trial", "active"]:
        lessons = db.query(Lesson).filter(
            Lesson.course_id == course_id,
            Lesson.is_published == True
        ).all()
    
    return {
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "price": course.price,
        "icon": course.icon,
        "instructor": course.instructor,
        "level": course.level,
        "duration": course.duration,
        "is_enrolled": bool(enrollment),
        "enrollment_status": enrollment.status if enrollment else None,
        "lessons": [
            {
                "id": l.id,
                "title": l.title,
                "description": l.description,
                "order": l.order
            }
            for l in lessons
        ] if lessons else []
    }


# ========== GET LESSON ==========

@router.get("/{course_id}/lessons/{lesson_id}/")
async def get_lesson(
    course_id: int,
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get lesson content (requires enrollment).
    """
    
    # Check enrollment
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id
    ).first()
    
    if not enrollment or enrollment.status not in ["trial", "active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Not enrolled or subscription expired"
        )
    
    # Get lesson
    lesson = db.query(Lesson).filter(
        Lesson.id == lesson_id,
        Lesson.course_id == course_id
    ).first()
    
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found"
        )
    
    return {
        "id": lesson.id,
        "title": lesson.title,
        "description": lesson.description,
        "content_html": lesson.content_html,
        "video_url": lesson.video_url,
        "duration_minutes": lesson.duration_minutes,
        "resources": lesson.resources,
        "has_quiz": lesson.has_quiz,
        "quiz_data": lesson.quiz_data
    }


# ========== MARK LESSON COMPLETE ==========

@router.post("/{course_id}/lessons/{lesson_id}/complete/")
async def complete_lesson(
    course_id: int,
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a lesson as completed.
    """
    
    # Check enrollment
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enrolled"
        )
    
    # Get or create lesson progress
    progress = db.query(LessonProgress).filter(
        LessonProgress.user_id == current_user.id,
        LessonProgress.lesson_id == lesson_id
    ).first()
    
    if not progress:
        progress = LessonProgress(
            user_id=current_user.id,
            lesson_id=lesson_id,
            is_completed=True,
            completed_at=datetime.utcnow()
        )
        db.add(progress)
    else:
        progress.is_completed = True
        progress.completed_at = datetime.utcnow()
    
    db.commit()
    
    logger.info(f"[lesson-complete] user_id={current_user.id}, lesson_id={lesson_id}")
    
    return {
        "success": True,
        "message": "Lesson marked as complete"
    }