from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from database import get_db
from auth import get_current_user

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("", response_model=List[schemas.CourseOut])
def list_courses(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    enrolled_ids = {
        e.course_id for e in
        db.query(models.Enrollment).filter(models.Enrollment.user_id == current_user.id).all()
    }
    courses = db.query(models.Course).all()
    return [
        schemas.CourseOut(
            id=c.id, title=c.title, description=c.description, level=c.level,
            duration=c.duration, icon=c.icon, enrolled=c.id in enrolled_ids,
        )
        for c in courses
    ]


@router.post("/{course_id}/enroll", response_model=schemas.EnrollResponse)
def enroll(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    existing = db.query(models.Enrollment).filter(
        models.Enrollment.user_id == current_user.id,
        models.Enrollment.course_id == course_id,
    ).first()
    if existing:
        return schemas.EnrollResponse(status="already_enrolled", course_id=course_id)

    db.add(models.Enrollment(user_id=current_user.id, course_id=course_id))
    db.commit()
    return schemas.EnrollResponse(status="enrolled", course_id=course_id)
