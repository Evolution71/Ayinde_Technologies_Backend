"""
Captcha router for Ayinde Technologies API.
Generates and verifies simple text-based captchas for form protection.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import random
import string
from database import get_db
from schemas import CaptchaGenerateResponse, CaptchaVerifyRequest, CaptchaVerifyResponse

router = APIRouter(prefix="/api/captcha", tags=["captcha"])

# Simple in-memory captcha storage (in production, use Redis or database)
captcha_store = {}

def generate_captcha_id():
    """Generate a unique captcha ID"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=16))

def generate_captcha_challenge():
    """Generate a simple math challenge"""
    num1 = random.randint(1, 20)
    num2 = random.randint(1, 20)
    operation = random.choice(['+', '-'])
    
    if operation == '+':
        answer = num1 + num2
    else:
        answer = num1 - num2
    
    challenge_text = f"What is {num1} {operation} {num2}?"
    return challenge_text, str(answer)

@router.get("/", response_model=CaptchaGenerateResponse)
async def generate_captcha():
    """
    Generate a new captcha challenge.
    Returns a captcha ID and challenge text.
    The client must solve the challenge and send back the answer.
    """
    try:
        captcha_id = generate_captcha_id()
        challenge_text, answer = generate_captcha_challenge()
        
        # Store captcha with 10 minute expiry
        captcha_store[captcha_id] = {
            'challenge': challenge_text,
            'answer': answer,
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(minutes=10),
            'attempts': 0
        }
        
        return {
            "captcha_id": captcha_id,
            "captcha_image": challenge_text  # In this simple version, return the text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate captcha: {str(e)}")


@router.post("/verify/", response_model=CaptchaVerifyResponse)
async def verify_captcha(request: CaptchaVerifyRequest):
    """
    Verify a captcha answer.
    Returns success: true if answer is correct.
    """
    try:
        captcha_id = request.captcha_id
        user_answer = request.captcha_answer.strip()
        
        # Check if captcha exists
        if captcha_id not in captcha_store:
            return {
                "success": False,
                "message": "Captcha expired or invalid",
                "score": 0.0
            }
        
        captcha_data = captcha_store[captcha_id]
        
        # Check if captcha has expired
        if datetime.utcnow() > captcha_data['expires_at']:
            del captcha_store[captcha_id]
            return {
                "success": False,
                "message": "Captcha expired",
                "score": 0.0
            }
        
        # Check if too many attempts
        captcha_data['attempts'] += 1
        if captcha_data['attempts'] > 5:
            del captcha_store[captcha_id]
            return {
                "success": False,
                "message": "Too many attempts",
                "score": 0.0
            }
        
        # Verify answer
        if user_answer == captcha_data['answer']:
            # Clean up used captcha
            del captcha_store[captcha_id]
            return {
                "success": True,
                "message": "Captcha verified successfully",
                "score": 1.0
            }
        else:
            return {
                "success": False,
                "message": f"Incorrect answer. Attempts: {captcha_data['attempts']}/5",
                "score": 0.0
            }
    
    except Exception as e:
        return {
            "success": False,
            "message": f"Verification failed: {str(e)}",
            "score": 0.0
        }


@router.get("/health/")
async def captcha_health():
    """Health check endpoint for captcha service"""
    return {
        "status": "healthy",
        "active_captchas": len(captcha_store)
    }