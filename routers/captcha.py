"""
Captcha router for Ayinde Technologies API.
Updated to use database storage instead of in-memory dict.
Generates and verifies text-based captchas for form protection.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import random
import string
from database import get_db
from models import Captcha
import schemas

router = APIRouter(prefix="/api/captcha", tags=["captcha"])


def generate_captcha_text(length=6):
    """Generate random captcha text (letters + digits)"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choices(characters, k=length))


@router.get("/")
async def generate_captcha(db: Session = Depends(get_db)):
    """
    Generate a new captcha challenge.
    
    Returns:
    - captcha_id: Unique ID for this challenge
    - captcha_image: Text to display to user (for text-based captcha)
    - expires_at: When this captcha expires (5 minutes)
    
    Frontend should:
    1. Display captcha_image text to user
    2. Get user's answer
    3. Call /api/captcha/verify/ with captcha_id and user's answer
    """
    try:
        # Generate text captcha
        captcha_text = generate_captcha_text(6)
        
        # Create captcha record in database
        captcha = Captcha(
            text=captcha_text,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=5)
        )
        
        db.add(captcha)
        db.commit()
        db.refresh(captcha)
        
        print(f"[captcha] Generated new captcha: id={captcha.id}, text={captcha_text}")
        
        return {
            "success": True,
            "captcha_id": captcha.id,
            "captcha_image": captcha_text,  # Display this text to user
            "expires_at": captcha.expires_at.isoformat(),
            "message": "Please enter the text shown above"
        }
    
    except Exception as e:
        print(f"[captcha] Error generating captcha: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate captcha: {str(e)}"
        )


@router.post("/verify/")
async def verify_captcha(
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Verify user's captcha answer.
    
    Expected request format:
    {
        "captcha_id": <id from generate_captcha>,
        "captcha_answer": "<user's answer>"
    }
    
    Returns:
    - success: true if verified, false otherwise
    - message: Explanation
    - score: 1.0 if valid, 0.0 if invalid
    """
    try:
        captcha_id = request.get('captcha_id')
        user_answer = request.get('captcha_answer', '').strip()
        
        if not captcha_id:
            return {
                "success": False,
                "message": "captcha_id is required",
                "score": 0.0
            }
        
        # Find captcha in database
        captcha = db.query(Captcha).filter(Captcha.id == captcha_id).first()
        
        if not captcha:
            print(f"[captcha] Captcha {captcha_id} not found")
            return {
                "success": False,
                "message": "Captcha not found or expired",
                "score": 0.0
            }
        
        # Check if expired
        if datetime.utcnow() > captcha.expires_at:
            print(f"[captcha] Captcha {captcha_id} expired")
            db.delete(captcha)
            db.commit()
            return {
                "success": False,
                "message": "Captcha expired. Please refresh and try again.",
                "score": 0.0
            }
        
        # Verify answer (case-insensitive)
        is_valid = captcha.text.upper() == user_answer.upper()
        
        if is_valid:
            print(f"[captcha] Captcha {captcha_id} verified successfully")
            # Delete after successful verification
            db.delete(captcha)
            db.commit()
            return {
                "success": True,
                "message": "Captcha verified!",
                "score": 1.0
            }
        else:
            print(f"[captcha] Captcha {captcha_id} verification failed - incorrect answer")
            return {
                "success": False,
                "message": "Incorrect answer. Please try again.",
                "score": 0.0
            }
    
    except Exception as e:
        print(f"[captcha] Error verifying captcha: {str(e)}")
        return {
            "success": False,
            "message": f"Verification failed: {str(e)}",
            "score": 0.0
        }


@router.delete("/{captcha_id}/")
async def delete_captcha(
    captcha_id: int,
    db: Session = Depends(get_db)
):
    """Delete a captcha (useful for form cancellations)"""
    try:
        captcha = db.query(Captcha).filter(Captcha.id == captcha_id).first()
        
        if not captcha:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Captcha not found"
            )
        
        db.delete(captcha)
        db.commit()
        
        return {"success": True, "message": "Captcha deleted"}
    
    except Exception as e:
        print(f"[captcha] Error deleting captcha: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete captcha: {str(e)}"
        )


@router.get("/health/")
async def captcha_health(db: Session = Depends(get_db)):
    """Health check endpoint for captcha service"""
    try:
        count = db.query(Captcha).count()
        return {
            "status": "healthy",
            "active_captchas": count
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }