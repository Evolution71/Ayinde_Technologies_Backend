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


@router.get("/", response_model=dict)
async def get_team(db: Session = Depends(get_db)):
    """
    Get all active team members ordered by display order.
    
    Returns: List of all team members with their roles, expertise, and bios
    """
    try:
        team_members = db.query(TeamMember).filter(
            TeamMember.is_active == True
        ).order_by(TeamMember.order.asc()).all()
        
        return {
            "success": True,
            "team_members": [
                {
                    "id": m.id,
                    "name": m.name,
                    "title": m.title,
                    "expertise": m.expertise if hasattr(m, 'expertise') else None,
                    "image": m.image,
                    "quote": m.quote,
                    "achievement": m.achievement if hasattr(m, 'achievement') else None,
                    "gender": m.gender if hasattr(m, 'gender') else None,
                    "category": m.category if hasattr(m, 'category') else None,
                    "created_at": m.created_at.isoformat() if hasattr(m, 'created_at') and m.created_at else None
                }
                for m in team_members
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{member_id}/", response_model=dict)
async def get_team_member(
    member_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific team member by ID.
    
    Returns: Team member details including bio and expertise
    """
    try:
        member = db.query(TeamMember).filter(TeamMember.id == member_id).first()
        
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team member not found"
            )
        
        return {
            "id": member.id,
            "name": member.name,
            "title": member.title,
            "expertise": member.expertise if hasattr(member, 'expertise') else None,
            "image": member.image,
            "quote": member.quote,
            "achievement": member.achievement if hasattr(member, 'achievement') else None,
            "gender": member.gender if hasattr(member, 'gender') else None,
            "category": member.category if hasattr(member, 'category') else None,
            "created_at": member.created_at.isoformat() if hasattr(member, 'created_at') and member.created_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))