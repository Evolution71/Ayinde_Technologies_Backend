"""
Seed endpoints - API routes to populate database with sample data.

Endpoints:
- POST /api/seed/team - Populate team members
- POST /api/seed/quotes - Populate quotes
- POST /api/seed/all - Populate all data
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import TeamMember, Quote

router = APIRouter(prefix="/api/seed", tags=["seed"])


@router.post("/team/")
async def seed_team_members(db: Session = Depends(get_db)):
    """
    Populate team members table with sample data.
    """
    try:
        existing = db.query(TeamMember).count()
        if existing > 0:
            return {"status": "skipped", "message": f"Team already has {existing} members"}

        team_members = [
            TeamMember(
                name="Albert Cabrela",
                title="Founder & CEO",
                quote="Innovation and excellence drive everything we do.",
                achievement="Led the company to $10M+ annual revenue",
                image="👨‍💼",
                gender="male",
                category="leadership",
                order=1,
                is_active=True
            ),
            TeamMember(
                name="Sarah Johnson",
                title="Chief Technology Officer",
                quote="Great technology solves real problems.",
                achievement="20+ years in software architecture",
                image="👩‍💻",
                gender="female",
                category="leadership",
                order=2,
                is_active=True
            ),
            TeamMember(
                name="Mike Peterson",
                title="Product Manager",
                quote="User satisfaction is our north star.",
                achievement="Built 3 successful product lines",
                image="👨‍💼",
                gender="male",
                category="team",
                order=3,
                is_active=True
            ),
            TeamMember(
                name="Emily Rodriguez",
                title="Lead Engineer",
                quote="Code quality is not negotiable.",
                achievement="Architect of core platform system",
                image="👩‍🔬",
                gender="female",
                category="team",
                order=4,
                is_active=True
            ),
            TeamMember(
                name="James Chen",
                title="DevOps Lead",
                quote="Infrastructure is the backbone of reliability.",
                achievement="99.99% uptime track record",
                image="👨‍💻",
                gender="male",
                category="team",
                order=5,
                is_active=True
            ),
            TeamMember(
                name="Diana Watson",
                title="UX/UI Designer",
                quote="Design should be intuitive and beautiful.",
                achievement="Design lead for award-winning interface",
                image="👩‍🎨",
                gender="female",
                category="team",
                order=6,
                is_active=True
            ),
        ]

        for member in team_members:
            db.add(member)
        db.commit()

        return {
            "status": "success",
            "message": f"Added {len(team_members)} team members",
            "count": len(team_members)
        }

    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}


@router.post("/quotes/")
async def seed_quotes(db: Session = Depends(get_db)):
    """
    Populate quotes table with sample data.
    """
    try:
        existing = db.query(Quote).count()
        if existing > 0:
            return {"status": "skipped", "message": f"Database already has {existing} quotes"}

        quotes = [
            Quote(
                text="Success is not final, failure is not fatal: it is the courage to continue that counts.",
                author="Winston Churchill",
                category="success",
                order=1,
                is_active=True
            ),
            Quote(
                text="The only way to do great work is to love what you do.",
                author="Steve Jobs",
                category="business",
                order=2,
                is_active=True
            ),
            Quote(
                text="Innovation distinguishes between a leader and a follower.",
                author="Steve Jobs",
                category="leadership",
                order=3,
                is_active=True
            ),
            Quote(
                text="The future belongs to those who believe in the beauty of their dreams.",
                author="Eleanor Roosevelt",
                category="growth",
                order=4,
                is_active=True
            ),
            Quote(
                text="Don't watch the clock; do what it does. Keep going.",
                author="Sam Levenson",
                category="motivation",
                order=5,
                is_active=True
            ),
            Quote(
                text="Success is not about being the best. It's about being better than you were yesterday.",
                author="Unknown",
                category="growth",
                order=6,
                is_active=True
            ),
            Quote(
                text="The best time to plant a tree was 20 years ago. The second best time is now.",
                author="Chinese Proverb",
                category="business",
                order=7,
                is_active=True
            ),
            Quote(
                text="Excellence is not a destination; it is a continuous journey that never ends.",
                author="Brian Tracy",
                category="leadership",
                order=8,
                is_active=True
            ),
        ]

        for quote in quotes:
            db.add(quote)
        db.commit()

        return {
            "status": "success",
            "message": f"Added {len(quotes)} quotes",
            "count": len(quotes)
        }

    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}


@router.post("/all/")
async def seed_all(db: Session = Depends(get_db)):
    """
    Populate all seed data (team members and quotes).
    """
    team_result = await seed_team_members(db)
    quotes_result = await seed_quotes(db)

    return {
        "status": "success",
        "team": team_result,
        "quotes": quotes_result,
        "message": "All seed data populated"
    }


@router.post("/clear-all/")
async def clear_all(db: Session = Depends(get_db)):
    """
    Clear all seed data from database (for testing/reset).
    WARNING: This deletes all quotes and team members!
    """
    try:
        db.query(Quote).delete()
        db.query(TeamMember).delete()
        db.commit()
        return {
            "status": "success",
            "message": "All seed data cleared"
        }
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}