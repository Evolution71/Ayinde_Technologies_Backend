"""
Team members endpoints - display company team.

Endpoints:
- GET /api/team - List all team members
- GET /api/team/{id} - Get team member details
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import TeamMember
import schemas

router = APIRouter(prefix="/api/team", tags=["team"])


@router.get("/", response_model=List[schemas.TeamMemberOut])
async def get_team(db: Session = Depends(get_db)):
    """
    Get all team members.
    
    Returns: List of all team members with their roles and bios
    """
    team_members = db.query(TeamMember).all()
    return team_members


@router.get("/{member_id}/", response_model=schemas.TeamMemberOut)
async def get_team_member(
    member_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific team member by ID.
    
    Returns: Team member details including bio and social links
    
    Errors:
    - 404: Team member not found
    """
    member = db.query(TeamMember).filter(TeamMember.id == member_id).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found"
        )
    
    return member