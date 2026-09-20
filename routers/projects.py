"""
Projects endpoints - display portfolio and case studies.

Requires: User authentication

Endpoints:
- GET /api/projects - List all projects
- GET /api/projects/{id} - Get project details
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from auth import get_current_user
from models import User, Project
import schemas

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("/", response_model=List[schemas.ProjectOut])
async def get_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all portfolio projects.
    
    Requires: User must be logged in
    
    Returns: List of all projects with descriptions and images
    """
    projects = db.query(Project).all()
    return projects


@router.get("/{project_id}/", response_model=schemas.ProjectOut)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific project by ID.
    
    Requires: User must be logged in
    
    Returns: Project details with case study information
    
    Errors:
    - 404: Project not found
    - 401: User not authenticated
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project