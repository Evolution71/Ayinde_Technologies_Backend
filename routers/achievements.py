"""
Achievements and Team Members Router - Manage company achievements and team profiles

Endpoints:
- GET /api/achievements/ - Get all active achievements
- POST /api/achievements - Create achievement (admin only)
- PUT /api/achievements/{achievement_id} - Update achievement (admin only)
- DELETE /api/achievements/{achievement_id} - Delete achievement (admin only)

- GET /api/team-members/ - Get all active team members
- GET /api/team-members/by-gender/{gender}/ - Get team members filtered by gender
- POST /api/team-members - Create team member (admin only)
- PUT /api/team-members/{member_id} - Update team member (admin only)
- DELETE /api/team-members/{member_id} - Delete team member (admin only)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional
import logging

from database import get_db
from auth import get_current_user
from models import User, Achievement, TeamMember

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["achievements"])


# ════════════════════════════════════════════════════════════════════════════════
# ACHIEVEMENTS - Company achievements and milestones
# ════════════════════════════════════════════════════════════════════════════════

@router.get("/achievements/")  # ✓ FIXED: Added trailing slash
async def get_achievements(db: Session = Depends(get_db)):
    """
    Get all active achievements.

    Returns: List of achievements ordered by display order
    """
    try:
        achievements = db.query(Achievement).filter(
            Achievement.is_active == True
        ).order_by(Achievement.order.asc()).all()

        return {
            "achievements": [
                {
                    "id": a.id,
                    "title": a.title,
                    "description": a.description,
                    "category": a.category,
                    "icon": a.icon,
                    "order": a.order
                }
                for a in achievements
            ]
        }
    except Exception as e:
        logger.error(f"[achievements] Error fetching achievements: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/achievements")
async def create_achievement(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new achievement (admin only).

    Request Body:
    {
        "title": "Achievement title",
        "description": "Achievement description",
        "category": "general|award|metric",
        "icon": "🎯",
        "order": 1
    }
    """
    try:
        # Check if user is admin (assuming admin status in user model)
        if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")

        body = await request.json()

        title = body.get("title")
        description = body.get("description")
        category = body.get("category", "general")
        icon = body.get("icon", "🎯")
        order = body.get("order", 0)

        if not title or not description:
            raise HTTPException(status_code=400, detail="Title and description required")

        achievement = Achievement(
            title=title,
            description=description,
            category=category,
            icon=icon,
            order=order,
            is_active=True
        )

        db.add(achievement)
        db.commit()
        db.refresh(achievement)

        logger.info(f"[achievements] Created achievement: {achievement.id} - {title}")

        return {
            "success": True,
            "achievement_id": achievement.id,
            "message": "Achievement created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[achievements] Error creating achievement: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/achievements/{achievement_id}")
async def update_achievement(
    achievement_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update an achievement (admin only).
    """
    try:
        if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")

        achievement = db.query(Achievement).filter(
            Achievement.id == achievement_id
        ).first()

        if not achievement:
            raise HTTPException(status_code=404, detail="Achievement not found")

        body = await request.json()

        achievement.title = body.get("title", achievement.title)
        achievement.description = body.get("description", achievement.description)
        achievement.category = body.get("category", achievement.category)
        achievement.icon = body.get("icon", achievement.icon)
        achievement.order = body.get("order", achievement.order)
        achievement.is_active = body.get("is_active", achievement.is_active)
        achievement.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(achievement)

        logger.info(f"[achievements] Updated achievement: {achievement_id}")

        return {
            "success": True,
            "achievement_id": achievement.id,
            "message": "Achievement updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[achievements] Error updating achievement: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/achievements/{achievement_id}")
async def delete_achievement(
    achievement_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete an achievement (admin only).
    """
    try:
        if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")

        achievement = db.query(Achievement).filter(
            Achievement.id == achievement_id
        ).first()

        if not achievement:
            raise HTTPException(status_code=404, detail="Achievement not found")

        db.delete(achievement)
        db.commit()

        logger.info(f"[achievements] Deleted achievement: {achievement_id}")

        return {
            "success": True,
            "message": "Achievement deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[achievements] Error deleting achievement: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════════════════════
# TEAM MEMBERS - Leadership and team profiles
# ════════════════════════════════════════════════════════════════════════════════

@router.get("/team-members/")  # ✓ FIXED: Added trailing slash
async def get_team_members(db: Session = Depends(get_db)):
    """
    Get all active team members.

    Returns: List of team members grouped by gender, ordered by display order
    """
    try:
        team_members = db.query(TeamMember).filter(
            TeamMember.is_active == True
        ).order_by(TeamMember.gender.asc(), TeamMember.order.asc()).all()

        # Group by gender
        by_gender = {}
        for member in team_members:
            if member.gender not in by_gender:
                by_gender[member.gender] = []
            by_gender[member.gender].append({
                "id": member.id,
                "name": member.name,
                "title": member.title,
                "quote": member.quote,
                "achievement": member.achievement,
                "image": member.image,
                "gender": member.gender,
                "category": member.category
            })

        return {
            "team_members": by_gender,
            "all_members": [
                {
                    "id": m.id,
                    "name": m.name,
                    "title": m.title,
                    "quote": m.quote,
                    "achievement": m.achievement,
                    "image": m.image,
                    "gender": m.gender,
                    "category": m.category
                }
                for m in team_members
            ]
        }
    except Exception as e:
        logger.error(f"[team_members] Error fetching team members: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/team-members/by-gender/{gender}/")  # ✓ FIXED: Added trailing slash
async def get_team_members_by_gender(
    gender: str,
    db: Session = Depends(get_db)
):
    """
    Get team members filtered by gender (male or female).
    """
    try:
        gender = gender.lower()
        if gender not in ["male", "female", "other"]:
            raise HTTPException(status_code=400, detail="Invalid gender. Use: male, female, or other")

        team_members = db.query(TeamMember).filter(
            TeamMember.is_active == True,
            TeamMember.gender == gender
        ).order_by(TeamMember.order.asc()).all()

        return {
            "gender": gender,
            "team_members": [
                {
                    "id": m.id,
                    "name": m.name,
                    "title": m.title,
                    "quote": m.quote,
                    "achievement": m.achievement,
                    "image": m.image,
                    "category": m.category
                }
                for m in team_members
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[team_members] Error fetching team members: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/team-members")
async def create_team_member(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new team member (admin only).

    Request Body:
    {
        "name": "Albert Cabrela",
        "title": "Founder & CEO",
        "quote": "...",
        "achievement": "Led the company to $10M+ annual revenue",
        "image": "👨‍💼",
        "gender": "male|female|other",
        "category": "leadership|team|consultant",
        "order": 1
    }
    """
    try:
        if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")

        body = await request.json()

        name = body.get("name")
        title = body.get("title")
        quote = body.get("quote")
        achievement = body.get("achievement")
        image = body.get("image", "👤")
        gender = body.get("gender", "other")
        category = body.get("category", "team")
        order = body.get("order", 0)

        if not name or not title or not quote:
            raise HTTPException(status_code=400, detail="Name, title, and quote are required")

        member = TeamMember(
            name=name,
            title=title,
            quote=quote,
            achievement=achievement,
            image=image,
            gender=gender,
            category=category,
            order=order,
            is_active=True
        )

        db.add(member)
        db.commit()
        db.refresh(member)

        logger.info(f"[team_members] Created team member: {member.id} - {name}")

        return {
            "success": True,
            "member_id": member.id,
            "message": "Team member created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[team_members] Error creating team member: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/team-members/{member_id}")
async def update_team_member(
    member_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a team member (admin only).
    """
    try:
        if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")

        member = db.query(TeamMember).filter(
            TeamMember.id == member_id
        ).first()

        if not member:
            raise HTTPException(status_code=404, detail="Team member not found")

        body = await request.json()

        member.name = body.get("name", member.name)
        member.title = body.get("title", member.title)
        member.quote = body.get("quote", member.quote)
        member.achievement = body.get("achievement", member.achievement)
        member.image = body.get("image", member.image)
        member.gender = body.get("gender", member.gender)
        member.category = body.get("category", member.category)
        member.order = body.get("order", member.order)
        member.is_active = body.get("is_active", member.is_active)
        member.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(member)

        logger.info(f"[team_members] Updated team member: {member_id}")

        return {
            "success": True,
            "member_id": member.id,
            "message": "Team member updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[team_members] Error updating team member: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/team-members/{member_id}")
async def delete_team_member(
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a team member (admin only).
    """
    try:
        if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")

        member = db.query(TeamMember).filter(
            TeamMember.id == member_id
        ).first()

        if not member:
            raise HTTPException(status_code=404, detail="Team member not found")

        db.delete(member)
        db.commit()

        logger.info(f"[team_members] Deleted team member: {member_id}")

        return {
            "success": True,
            "message": "Team member deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[team_members] Error deleting team member: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))