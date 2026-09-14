"""
Courses router — list courses, manage enrollments, handle trials.
Compatible with CourseEnrollment model (not Enrollment).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List

from database import SessionLocal
from auth import get_current_user
from models import User, Course, CourseEnrollment, Lesson
import schemas

router = APIRouter(prefix="/api/courses", tags=["courses"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _access_status(enrollment: CourseEnrollment) -> str:
    """Determine user's access status for a course."""
    if not enrollment:
        return "not_enrolled"
    
    if enrollment.status == "trial":
        if enrollment.trial_ends_at and datetime.utcnow() > enrollment.trial_ends_at:
            return "expired"
        return "trial"
    
    if enrollment.status == "active":
        if enrollment.access_expires_at and datetime.utcnow() > enrollment.access_expires_at:
            return "expired"
        return "active"
    
    return enrollment.status


# ========== List All Courses ==========

@router.get("/", response_model=List[schemas.CourseOut])
def list_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all active courses with user's enrollment status.
    """
    
    courses = db.query(Course).filter(Course.is_active == True).all()
    
    result = []
    for course in courses:
        # Check if user is enrolled
        enrollment = db.query(CourseEnrollment).filter(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.course_id == course.id,
        ).first()
        
        access_status = _access_status(enrollment)
        
        result.append({
            "id": course.id,
            "title": course.title,
            "description": course.description,
            "level": course.level,
            "duration": course.duration,
            "icon": course.icon,
            "instructor": course.instructor,
            "price": course.price,
            "currency": course.currency,
            "trial_duration_days": course.trial_duration_days,
            "enrolled": enrollment is not None,
            "access_status": access_status,
            "trial_ends_at": enrollment.trial_ends_at if enrollment else None,
        })
    
    return result


# ========== Start Free Trial ==========

@router.post("/{course_id}/enroll")
def start_trial(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Start a free trial for a course (30 days).
    """
    
    # Get course
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Check if already enrolled
    existing = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id,
    ).first()
    
    if existing:
        status = _access_status(existing)
        if status in ["trial", "active"]:
            return {
                "status": "already_enrolled",
                "message": f"You're already enrolled (status: {status})",
                "course_id": course_id,
                "enrollment_id": existing.id,
                "trial_ends_at": existing.trial_ends_at,
            }
    
    # Create enrollment with trial
    trial_ends_at = datetime.utcnow() + timedelta(days=course.trial_duration_days)
    
    enrollment = CourseEnrollment(
        user_id=current_user.id,
        course_id=course_id,
        status="trial",
        trial_ends_at=trial_ends_at,
    )
    
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    
    return {
        "status": "success",
        "message": f"Trial started! Access until {trial_ends_at.strftime('%Y-%m-%d')}",
        "course_id": course_id,
        "enrollment_id": enrollment.id,
        "trial_ends_at": enrollment.trial_ends_at,
    }


# ========== Get User's Enrollments ==========

@router.get("/user/enrollments", response_model=List[schemas.CourseEnrollmentOut])
def get_my_enrollments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all courses user is enrolled in (trial or active).
    """
    
    enrollments = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
    ).all()
    
    return enrollments