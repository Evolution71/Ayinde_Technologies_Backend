from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from database import get_db

router = APIRouter(prefix="/api/team", tags=["team"])


def _to_out(m: models.TeamMember) -> schemas.TeamMemberOut:
    return schemas.TeamMemberOut(
        id=m.id, name=m.name, role=m.role, bio=m.bio, image=m.image,
        expertise=[e for e in m.expertise.split(",") if e],
        email=m.email, phone=m.phone,
    )


@router.get("", response_model=List[schemas.TeamMemberOut])
def list_team(db: Session = Depends(get_db)):
    return [_to_out(m) for m in db.query(models.TeamMember).all()]


@router.get("/{member_id}", response_model=schemas.TeamMemberOut)
def get_team_member(member_id: int, db: Session = Depends(get_db)):
    m = db.query(models.TeamMember).filter(models.TeamMember.id == member_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Team member not found")
    return _to_out(m)
