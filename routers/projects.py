from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from database import get_db
from auth import get_current_user

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _to_out(p: models.Project) -> schemas.ProjectOut:
    return schemas.ProjectOut(
        id=p.id, title=p.title, client=p.client, category=p.category,
        description=p.description, image=p.image,
        technologies=[t for t in p.technologies.split(",") if t],
        results=[r for r in p.results.split(",") if r],
        app_url=p.app_url,
    )


@router.get("", response_model=List[schemas.ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),  # 401s if not logged in
):
    return [_to_out(p) for p in db.query(models.Project).all()]


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return _to_out(p)
