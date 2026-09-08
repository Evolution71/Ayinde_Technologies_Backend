from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from database import get_db
from auth import get_current_user

router = APIRouter(prefix="/api/courses", tags=["courses"])

TRIAL_DAYS = 30


def _access_status(enrollment: models.Enrollment) -> str:
    if not enrollment:
        return "not_enrolled"
    if enrollment.is_paid:
        return "active"
    if enrollment.trial_ends_at and enrollment.trial_ends_at > datetime.utcnow():
        return "trial"
    return "expired"


@router.get("", response_model=List[schemas.CourseOut])
def list_courses(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    enrollments = {
        e.course_id: e for e in
        db.query(models.Enrollment).filter(models.Enrollment.user_id == current_user.id).all()
    }
    courses = db.query(models.Course).all()
    out = []
    for c in courses:
        enrollment = enrollments.get(c.id)
        out.append(schemas.CourseOut(
            id=c.id, title=c.title, description=c.description, level=c.level,
            duration=c.duration, icon=c.icon, price=c.price, currency=c.currency,
            enrolled=enrollment is not None,
            access_status=_access_status(enrollment),
            trial_ends_at=enrollment.trial_ends_at if enrollment else None,
        ))
    return out


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
        return schemas.EnrollResponse(
            status="already_enrolled", course_id=course_id, trial_ends_at=existing.trial_ends_at,
        )

    trial_ends_at = datetime.utcnow() + timedelta(days=TRIAL_DAYS)
    enrollment = models.Enrollment(
        user_id=current_user.id, course_id=course_id, trial_ends_at=trial_ends_at,
    )
    db.add(enrollment)
    db.commit()
    return schemas.EnrollResponse(status="enrolled", course_id=course_id, trial_ends_at=trial_ends_at)
