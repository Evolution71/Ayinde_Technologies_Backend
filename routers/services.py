"""
Services endpoints - display company services.

Endpoints:
- GET /api/services - List all services
- GET /api/services/{id} - Get service details
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import Service
import schemas

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("/", response_model=List[schemas.ServiceOut])
async def get_services(db: Session = Depends(get_db)):
    """
    Get all available services.
    
    Returns: List of all services with descriptions and pricing
    """
    services = db.query(Service).all()
    return services


@router.get("/{service_id}/", response_model=schemas.ServiceOut)
async def get_service(
    service_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific service by ID.
    
    Returns: Service details
    
    Errors:
    - 404: Service not found
    """
    service = db.query(Service).filter(Service.id == service_id).first()
    
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    return service