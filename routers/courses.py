"""
Courses, lessons, and enrollment endpoints.

Features:
- Browse courses (public or logged in)
- Free 30-day trial for all courses
- Track progress through lessons
- Payment integration (optional)

Endpoints:
- GET /api/courses - List all courses
- GET /api/courses/{id} - Get course details (requires enrollment)
- POST /api/courses/{id}/enroll - Start free trial
- GET /api/courses/{id}/lessons/{lesson_id} - Get lesson
- POST /api/courses/{id}/lessons/{lesson_id}/complete - Mark complete
- GET /api/courses/{id}/progress - Get user's course progress
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional

from database import get_db
from auth import get_current_user, get_current_user_optional
from models import User, Course, CourseEnrollment, Lesson, LessonProgress
import schemas

router = APIRouter(prefix="/api/courses", tags=["courses"])


# ========== LIST COURSES ==========

@router.get("/", response_model=List[schemas.CourseOut])
async def list_courses(
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    List all active courses.
    
    Features:
    - Shows all active courses to everyone (logged in or not)
    - If logged in: shows enrollment status for each course
    - If not logged in: shows basic course info only
    
    Returns: List of courses with enrollment status
    """
    
    courses = db.query(Course).filter(Course.is_active == True).all()
    
    result = []
    for course in courses:
        # Check enrollment status (if logged in)
        enrollment = None
        access_status = "not_enrolled"
        trial_ends_at = None
        
        if current_user:
            enrollment = db.query(CourseEnrollment).filter(
                CourseEnrollment.user_id == current_user.id,
                CourseEnrollment.course_id == course.id
            ).first()
            
            if enrollment:
                access_status = enrollment.status  # trial / active / expired / cancelled
                trial_ends_at = enrollment.trial_ends_at
                
                # Auto-expire if trial ended
                if access_status == "trial" and trial_ends_at and datetime.utcnow() > trial_ends_at:
                    enrollment.status = "expired"
                    db.commit()
                    access_status = "expired"
        
        course_out = schemas.CourseOut(
            id=course.id,
            title=course.title,
            description=course.description,
            level=course.level,
            duration=course.duration,
            icon=course.icon,
            instructor=course.instructor,
            price=course.price or 100.0,
            currency=course.currency or "USD",
            trial_duration_days=course.trial_duration_days or 30,
            enrolled=bool(enrollment),
            access_status=access_status,
            trial_ends_at=trial_ends_at
        )
        result.append(course_out)
    
    return result


# ========== GET COURSE DETAIL ==========

@router.get("/{course_id}/", response_model=schemas.CourseDetailOut)
async def get_course_detail(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed course view with all lessons.
    
    Requires:
    - Valid login (JWT token)
    - Active enrollment (trial or paid)
    
    Returns: Course details with lessons list and progress
    
    Errors:
    - 404: Course not found
    - 403: Not enrolled or access expired
    """
    
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check enrollment
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must enroll in this course first."
        )
    
    # Check if access is still valid
    now = datetime.utcnow()
    
    # Check trial expiration
    if enrollment.status == "trial":
        if enrollment.trial_ends_at and now > enrollment.trial_ends_at:
            enrollment.status = "expired"
            db.commit()
    
    # Check paid subscription expiration
    if enrollment.status == "active":
        if enrollment.access_expires_at and now > enrollment.access_expires_at:
            enrollment.status = "expired"
            db.commit()
    
    if enrollment.status not in ["trial", "active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your access to this course has expired. Please renew your subscription."
        )
    
    # Get published lessons
    lessons = db.query(Lesson).filter(
        Lesson.course_id == course_id,
        Lesson.is_published == True
    ).order_by(Lesson.order).all()
    
    lesson_outs = [schemas.LessonOut.from_attributes(l) for l in lessons]
    
    # Calculate progress
    if lessons:
        progress_records = db.query(LessonProgress).filter(
            LessonProgress.user_id == current_user.id,
            LessonProgress.lesson_id.in_([l.id for l in lessons]),
            LessonProgress.is_completed == True
        ).all()
        
        completed = len(progress_records)
        progress_percentage = (completed / len(lessons)) * 100
    else:
        progress_percentage = 0.0
    
    return schemas.CourseDetailOut(
        id=course.id,
        title=course.title,
        description=course.description,
        level=course.level,
        duration=course.duration,
        icon=course.icon,
        instructor=course.instructor,
        price=course.price or 100.0,
        currency=course.currency or "USD",
        trial_duration_days=course.trial_duration_days or 30,
        enrolled=True,
        access_status=enrollment.status,
        trial_ends_at=enrollment.trial_ends_at,
        lessons=lesson_outs,
        progress_percentage=progress_percentage,
        last_accessed_at=enrollment.last_accessed_at
    )


# ========== ENROLL IN COURSE ==========

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
            "enrollment": schemas.CourseEnrollmentOut.from_attributes(existing)
        }
    
    # Create new enrollment with 30-day trial
    trial_days = course.trial_duration_days or 30
    enrollment = CourseEnrollment(
        user_id=current_user.id,
        course_id=course_id,
        status="trial",
        enrolled_at=datetime.utcnow(),
        trial_ends_at=datetime.utcnow() + timedelta(days=trial_days),
        progress_percentage=0.0
    )
    
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    
    return {
        "status": "success",
        "message": f"Welcome to {course.title}! Your {trial_days}-day free trial has started.",
        "enrollment": schemas.CourseEnrollmentOut.from_attributes(enrollment)
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
    Get a single lesson's content.
    
    Requires: Active enrollment in the course
    
    Returns: Lesson details including video URL and resources
    
    Errors:
    - 404: Lesson not found
    - 403: No active enrollment in course
    """
    
    # Verify enrollment
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.status.in_(["trial", "active"])
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this course."
        )
    
    # Get lesson
    lesson = db.query(Lesson).filter(
        Lesson.id == lesson_id,
        Lesson.course_id == course_id,
        Lesson.is_published == True
    ).first()
    
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found"
        )
    
    # Update last accessed time
    enrollment.last_accessed_at = datetime.utcnow()
    db.commit()
    
    return schemas.LessonOut.from_attributes(lesson)


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
    
    Updates:
    - User's progress record
    - Overall course progress percentage
    
    Returns: Updated progress information
    
    Errors:
    - 403: Not enrolled in course
    - 404: Lesson not found
    """
    
    # Verify enrollment
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enrolled in this course"
        )
    
    # Get or create progress record
    progress = db.query(LessonProgress).filter(
        LessonProgress.user_id == current_user.id,
        LessonProgress.lesson_id == lesson_id
    ).first()
    
    if not progress:
        progress = LessonProgress(
            user_id=current_user.id,
            lesson_id=lesson_id
        )
        db.add(progress)
    
    progress.is_completed = True
    progress.completed_at = datetime.utcnow()
    
    # Recalculate course progress
    all_lessons = db.query(Lesson).filter(Lesson.course_id == course_id).count()
    completed_lessons = db.query(LessonProgress).filter(
        LessonProgress.user_id == current_user.id,
        LessonProgress.is_completed == True,
        LessonProgress.lesson_id.in_(
            db.query(Lesson.id).filter(Lesson.course_id == course_id)
        )
    ).count()
    
    enrollment.progress_percentage = (completed_lessons / all_lessons * 100) if all_lessons > 0 else 0
    enrollment.last_accessed_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "status": "success",
        "message": "Lesson marked as complete!",
        "progress_percentage": enrollment.progress_percentage
    }


# ========== GET COURSE PROGRESS ==========

@router.get("/{course_id}/progress/")
async def get_course_progress(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's overall progress in a course.
    
    Returns: Course status and progress for each lesson
    
    Errors:
    - 403: Not enrolled in course
    - 404: Course not found
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enrolled in this course"
        )
    
    # Get all lessons with progress
    lessons = db.query(Lesson).filter(Lesson.course_id == course_id).all()
    
    progress_details = []
    for lesson in lessons:
        p = db.query(LessonProgress).filter(
            LessonProgress.user_id == current_user.id,
            LessonProgress.lesson_id == lesson.id
        ).first()
        
        progress_details.append({
            "lesson_id": lesson.id,
            "title": lesson.title,
            "order": lesson.order,
            "completed": p.is_completed if p else False,
            "time_spent_seconds": p.time_spent_seconds if p else 0,
            "quiz_score": p.quiz_score if p else None
        })
    
    return {
        "course_id": course_id,
        "course_title": course.title,
        "enrollment_status": enrollment.status,
        "overall_progress": enrollment.progress_percentage,
        "total_lessons": len(lessons),
        "lessons": progress_details
    }