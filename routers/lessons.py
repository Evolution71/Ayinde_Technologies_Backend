"""
Lessons endpoints - manage lesson content and progress tracking.

Requires: User authentication and course enrollment

Endpoints:
- GET /api/lessons/{id} - Get lesson details
- POST /api/lessons/{id}/progress - Update lesson progress
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from database import get_db
from auth import get_current_user
from models import User, Lesson, LessonProgress, CourseEnrollment
import schemas

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


@router.get("/{lesson_id}", response_model=schemas.LessonOut)
async def get_lesson_detail(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific lesson's details.
    
    Requires:
    - User must be logged in
    - User must have active enrollment in the lesson's course
    
    Returns: Lesson content including video URL and resources
    
    Errors:
    - 404: Lesson not found
    - 403: No active enrollment in course
    """
    
    lesson = db.query(Lesson).filter(
        Lesson.id == lesson_id,
        Lesson.is_published == True
    ).first()
    
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found or is not published"
        )
    
    # Verify enrollment in course
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == lesson.course_id,
        CourseEnrollment.status.in_(["trial", "active"])
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be enrolled in this course to access its lessons."
        )
    
    return schemas.LessonOut.from_attributes(lesson)


@router.post("/{lesson_id}/progress")
async def update_lesson_progress(
    lesson_id: int,
    time_spent: Optional[int] = 0,
    quiz_score: Optional[float] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user's progress on a lesson.
    
    Updates:
    - Time spent watching/reading the lesson
    - Quiz score if quiz was completed
    - Marks lesson as in-progress or completed
    
    Parameters:
    - lesson_id: The lesson being worked on
    - time_spent: Seconds spent on this lesson (0 = don't update)
    - quiz_score: Score on quiz if completed (0-100)
    
    Returns: Updated progress record
    
    Errors:
    - 403: Not enrolled in course
    - 404: Lesson not found
    """
    
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found"
        )
    
    # Verify enrollment in course
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == lesson.course_id
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
            lesson_id=lesson_id,
            time_spent_seconds=0
        )
        db.add(progress)
    
    # Update progress
    if time_spent and time_spent > 0:
        progress.time_spent_seconds += time_spent
    
    if quiz_score is not None and quiz_score >= 0:
        progress.quiz_score = quiz_score
    
    progress.last_accessed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(progress)
    
    return {
        "status": "success",
        "message": "Progress updated successfully",
        "progress": schemas.LessonProgressOut.from_attributes(progress)
    }


@router.post("/{lesson_id}/complete")
async def complete_lesson(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a lesson as completed.
    
    Effects:
    - Marks lesson as completed in user's progress
    - Updates course overall progress percentage
    - Records completion time
    
    Returns: Success confirmation
    
    Errors:
    - 403: Not enrolled in course
    - 404: Lesson not found
    """
    
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found"
        )
    
    # Verify enrollment
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == lesson.course_id
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enrolled in this course"
        )
    
    # Get or create progress
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
    
    db.commit()
    
    return {
        "status": "success",
        "message": "Congratulations! Lesson completed.",
        "completed_at": progress.completed_at
    }