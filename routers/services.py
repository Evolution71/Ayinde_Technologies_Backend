from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from database import get_db

router = APIRouter(prefix="/api/services", tags=["services"])


def _to_out(s: models.Service) -> schemas.ServiceOut:
    return schemas.ServiceOut(
        id=s.id, name=s.name, description=s.description, icon=s.icon,
        features=[f for f in s.features.split(",") if f],
    )


@router.get("", response_model=List[schemas.ServiceOut])
def list_services(db: Session = Depends(get_db)):
    return [_to_out(s) for s in db.query(models.Service).all()]


@router.get("/{service_id}", response_model=schemas.ServiceOut)
def get_service(service_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Service).filter(models.Service.id == service_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Service not found")
    return _to_out(s)
