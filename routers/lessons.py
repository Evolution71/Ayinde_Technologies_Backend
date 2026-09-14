"""
Course lessons and progress tracking router.
Handles video streaming, quizzes, and user progress.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from database import SessionLocal
from auth import get_current_user
from models import User, Course, Lesson, CourseEnrollment, LessonProgress
import schemas

router = APIRouter(prefix="/api/courses", tags=["courses"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ========== Get Course with Lessons ==========

@router.get("/{course_id}", response_model=schemas.CourseDetailOut)
def get_course_detail(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get full course details including lessons.
    User must be enrolled (trial or active) to see lesson content.
    """
    
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Check enrollment
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.status.in_(["trial", "active"])
    ).first()
    
    if not enrollment:
        # Not enrolled - return basic info only
        return {
            **course.__dict__,
            "lessons": [],
            "enrolled": False,
            "access_status": "not_enrolled",
            "trial_ends_at": None,
            "progress_percentage": 0.0,
        }
    
    # Update last_accessed_at
    enrollment.last_accessed_at = datetime.utcnow()
    db.commit()
    
    # Get lessons (ordered)
    lessons = db.query(Lesson).filter(
        Lesson.course_id == course_id,
        Lesson.is_published == True
    ).order_by(Lesson.order).all()
    
    # Calculate progress
    total_lessons = len(lessons)
    if total_lessons > 0:
        completed = db.query(LessonProgress).filter(
            LessonProgress.user_id == current_user.id,
            LessonProgress.lesson_id.in_([l.id for l in lessons]),
            LessonProgress.is_completed == True
        ).count()
        progress_percentage = (completed / total_lessons) * 100
    else:
        progress_percentage = 0.0
    
    return {
        **course.__dict__,
        "lessons": lessons,
        "enrolled": True,
        "access_status": "trial" if enrollment.status == "trial" else "active",
        "trial_ends_at": enrollment.trial_ends_at,
        "progress_percentage": progress_percentage,
        "last_accessed_at": enrollment.last_accessed_at,
    }


# ========== Get Single Lesson ==========

@router.get("/{course_id}/lessons/{lesson_id}", response_model=schemas.LessonOut)
def get_lesson(
    course_id: int,
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a specific lesson content.
    User must be enrolled to access.
    """
    
    # Check enrollment
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.status.in_(["trial", "active"])
    ).first()
    
    if not enrollment:
        raise HTTPException(status_code=403, detail="You don't have access to this course")
    
    # Get lesson
    lesson = db.query(Lesson).filter(
        Lesson.id == lesson_id,
        Lesson.course_id == course_id
    ).first()
    
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    
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
        db.commit()
    
    return lesson


# ========== Mark Lesson as Complete ==========

@router.post("/{course_id}/lessons/{lesson_id}/complete")
def complete_lesson(
    course_id: int,
    lesson_id: int,
    quiz_score: float = None,  # Optional: 0-100
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark a lesson as completed.
    Optionally include quiz score.
    """
    
    # Check enrollment
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.status.in_(["trial", "active"])
    ).first()
    
    if not enrollment:
        raise HTTPException(status_code=403, detail="You don't have access to this course")
    
    # Get lesson
    lesson = db.query(Lesson).filter(
        Lesson.id == lesson_id,
        Lesson.course_id == course_id
    ).first()
    
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    
    # Update progress
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
    if quiz_score is not None:
        progress.quiz_score = min(100, max(0, quiz_score))  # Clamp 0-100
    
    db.commit()
    
    # Recalculate enrollment progress
    lessons = db.query(Lesson).filter(
        Lesson.course_id == course_id,
        Lesson.is_published == True
    ).all()
    
    total = len(lessons)
    if total > 0:
        completed = db.query(LessonProgress).filter(
            LessonProgress.user_id == current_user.id,
            LessonProgress.lesson_id.in_([l.id for l in lessons]),
            LessonProgress.is_completed == True
        ).count()
        enrollment.progress_percentage = (completed / total) * 100
        db.commit()
    
    return {
        "status": "success",
        "message": "Lesson marked as complete",
        "progress_percentage": enrollment.progress_percentage
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
        CourseEnrollment.status.in_(["trial", "active"])
    ).all()
    
    return enrollments


# ========== Get User's Progress ==========

@router.get("/{course_id}/progress")
def get_course_progress(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get detailed progress for a course.
    """
    
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id
    ).first()
    
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    
    # Get all lessons
    lessons = db.query(Lesson).filter(
        Lesson.course_id == course_id,
        Lesson.is_published == True
    ).order_by(Lesson.order).all()
    
    # Get progress for each lesson
    lesson_progress = []
    for lesson in lessons:
        progress = db.query(LessonProgress).filter(
            LessonProgress.user_id == current_user.id,
            LessonProgress.lesson_id == lesson.id
        ).first()
        
        lesson_progress.append({
            "lesson_id": lesson.id,
            "lesson_title": lesson.title,
            "order": lesson.order,
            "is_completed": progress.is_completed if progress else False,
            "quiz_score": progress.quiz_score if progress else None,
            "time_spent_seconds": progress.time_spent_seconds if progress else 0,
        })
    
    return {
        "course_id": course_id,
        "overall_progress": enrollment.progress_percentage,
        "status": enrollment.status,
        "lessons": lesson_progress,
        "enrolled_at": enrollment.enrolled_at,
        "trial_ends_at": enrollment.trial_ends_at,
    }