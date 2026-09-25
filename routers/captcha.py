"""
Captcha router for Ayinde Technologies API.
Database-backed text captchas with Supabase PostgreSQL.

Endpoints:
  GET  /api/captcha/        → Generate new captcha
  POST /api/captcha/verify/ → Verify answer
  DELETE /api/captcha/{id}/ → Delete captcha (cleanup)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, delete
from datetime import datetime, timedelta
import random
import string
import logging

from database import get_db, Base, engine
from schemas import CaptchaGenerateResponse, CaptchaVerifyRequest, CaptchaVerifyResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/captcha", tags=["captcha"])

# ========== CAPTCHA MODEL ==========

from sqlalchemy.orm import declarative_base

class Captcha(Base):
    """Database-backed captcha storage"""
    __tablename__ = "captchas"
    
    id = Column(Integer, primary_key=True, index=True)
    captcha_id = Column(String(16), unique=True, index=True, nullable=False)  # Unique token
    text = Column(String(20), nullable=False)  # The text to display (e.g., "ABC123")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)

# Auto-create table
Base.metadata.create_all(bind=engine)

# ========== HELPER FUNCTIONS ==========

def generate_captcha_id():
    """Generate unique 16-char alphanumeric ID"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=16))

def generate_captcha_text():
    """
    Generate random captcha text
    Format: 3 uppercase letters + 3 digits (e.g., ABC123)
    """
    letters = ''.join(random.choices(string.ascii_uppercase, k=3))
    digits = ''.join(random.choices(string.digits, k=3))
    # Shuffle the order
    combined = list(letters + digits)
    random.shuffle(combined)
    return ''.join(combined)

# ========== ENDPOINTS ==========

@router.get("/", response_model=CaptchaGenerateResponse)
async def generate_captcha(db: Session = Depends(get_db)):
    """
    Generate a new text-based captcha.
    
    Returns:
      {
        "captcha_id": "xJ7kL9mN2pQ4",      ← Send this back during verification
        "captcha_image": "ABC123",          ← Display this to user
        "expires_at": "2026-09-25T12:30:00"
      }
    
    Captcha expires in 5 minutes.
    """
    try:
        # Generate unique ID and text
        captcha_id = generate_captcha_id()
        captcha_text = generate_captcha_text()
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        
        # Create and save to database
        captcha = Captcha(
            captcha_id=captcha_id,
            text=captcha_text,
            expires_at=expires_at
        )
        db.add(captcha)
        db.commit()
        db.refresh(captcha)
        
        logger.info(f"[Captcha] Generated: {captcha_id} = {captcha_text}")
        
        return {
            "captcha_id": captcha_id,
            "captcha_image": captcha_text,
            "expires_at": expires_at.isoformat()
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"[Captcha] Generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate captcha: {str(e)}")


@router.post("/verify/", response_model=CaptchaVerifyResponse)
async def verify_captcha(request: CaptchaVerifyRequest, db: Session = Depends(get_db)):
    """
    Verify a captcha answer.
    
    Request body:
      {
        "captcha_id": "xJ7kL9mN2pQ4",
        "captcha_answer": "abc123"  ← Case-insensitive
      }
    
    Returns:
      {
        "success": true/false,
        "message": "...",
        "score": 1.0 if correct, 0.0 if not
      }
    
    Deletes captcha from DB after verification attempt (win or lose).
    """
    try:
        captcha_id = request.captcha_id.strip()
        user_answer = request.captcha_answer.strip().upper()  # Normalize
        
        # Fetch from database
        captcha = db.query(Captcha).filter(
            Captcha.captcha_id == captcha_id
        ).first()
        
        # Check if exists
        if not captcha:
            logger.warning(f"[Captcha] Verify: not found or expired: {captcha_id}")
            return {
                "success": False,
                "message": "Captcha expired or invalid",
                "score": 0.0
            }
        
        # Check if expired
        if datetime.utcnow() > captcha.expires_at:
            db.delete(captcha)
            db.commit()
            logger.warning(f"[Captcha] Verify: expired: {captcha_id}")
            return {
                "success": False,
                "message": "Captcha expired",
                "score": 0.0
            }
        
        # Check answer (case-insensitive)
        correct_answer = captcha.text.upper()
        
        if user_answer == correct_answer:
            # Success — delete from DB
            db.delete(captcha)
            db.commit()
            logger.info(f"[Captcha] Verified successfully: {captcha_id}")
            return {
                "success": True,
                "message": "Captcha verified successfully",
                "score": 1.0
            }
        else:
            # Failed — delete from DB (one attempt only)
            db.delete(captcha)
            db.commit()
            logger.info(f"[Captcha] Verification failed: {captcha_id} (user: {user_answer}, correct: {correct_answer})")
            return {
                "success": False,
                "message": "Incorrect answer. Try again.",
                "score": 0.0
            }
    
    except Exception as e:
        db.rollback()
        logger.error(f"[Captcha] Verify error: {str(e)}")
        return {
            "success": False,
            "message": f"Verification failed: {str(e)}",
            "score": 0.0
        }


@router.delete("/{captcha_id}/")
async def delete_captcha(captcha_id: str, db: Session = Depends(get_db)):
    """
    Delete a captcha (for cleanup, e.g., form cancelled).
    """
    try:
        captcha = db.query(Captcha).filter(Captcha.captcha_id == captcha_id).first()
        
        if captcha:
            db.delete(captcha)
            db.commit()
            logger.info(f"[Captcha] Deleted: {captcha_id}")
        
        return {"success": True, "message": "Captcha deleted"}
    
    except Exception as e:
        db.rollback()
        logger.error(f"[Captcha] Delete error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete: {str(e)}")


@router.get("/health/")
async def captcha_health(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Count active (non-expired) captchas
        active_count = db.query(Captcha).filter(
            Captcha.expires_at > datetime.utcnow()
        ).count()
        
        return {
            "status": "healthy",
            "active_captchas": active_count
        }
    except Exception as e:
        logger.error(f"[Captcha] Health check error: {str(e)}")
        return {
            "status": "error",
            "detail": str(e)
        }