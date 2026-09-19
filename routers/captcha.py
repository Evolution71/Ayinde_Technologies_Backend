"""
Captcha router - generate and verify captcha challenges.
"""

import random
import string
from io import BytesIO
import base64
from PIL import Image, ImageDraw, ImageFont

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
import schemas

router = APIRouter(prefix="/api/captcha", tags=["captcha"])

# Store active captchas temporarily (in production, use Redis or DB)
active_captchas = {}


def generate_captcha_image(text: str) -> str:
    """Generate a captcha image and return as base64"""
    width, height = 200, 100
    
    # Create image with white background
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Add text
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except OSError:
        # Fallback to default font
        font = ImageFont.load_default()
    
    # Add some noise
    for _ in range(50):
        x = random.randint(0, width)
        y = random.randint(0, height)
        draw.point((x, y), fill='gray')
    
    # Draw text
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    draw.text((x, y), text, font=font, fill='black')
    
    # Convert to base64
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"


# ========== GET CAPTCHA ==========

@router.get("/", response_model=schemas.CaptchaGenerateResponse)
async def get_captcha():
    """
    Generate a new captcha challenge.
    
    Returns:
    - token: Unique identifier for this captcha
    - image: Base64 encoded PNG image of the captcha
    
    Client should:
    1. Display the image to the user
    2. Ask user to enter the text they see
    3. Send token + user_answer to /api/captcha/verify/
    """
    
    # Generate random 6-character alphanumeric string
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    # Generate unique token
    captcha_token = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32))
    
    # Generate image
    captcha_image = generate_captcha_image(captcha_text)
    
    # Store in memory (in production, use Redis/cache with TTL)
    active_captchas[captcha_token] = {
        'answer': captcha_text.lower(),
        'attempts': 0,
    }
    
    return {
        "token": captcha_token,
        "image": captcha_image,
    }


# ========== VERIFY CAPTCHA ==========

@router.post("/verify/", response_model=schemas.CaptchaVerifyResponse)
async def verify_captcha(request: schemas.CaptchaVerifyRequest):
    """
    Verify a captcha answer.
    
    Request:
    - token: Token from the captcha generation endpoint
    - user_answer: Text the user entered from the image
    
    Returns:
    - valid: True if answer is correct
    - message: Success or error message
    """
    
    token = request.token
    user_answer = (request.user_answer or '').lower().strip()
    
    # Check if token exists
    if token not in active_captchas:
        return {
            "valid": False,
            "message": "Invalid or expired captcha token"
        }
    
    captcha_data = active_captchas[token]
    correct_answer = captcha_data['answer']
    
    # Check if too many attempts
    if captcha_data['attempts'] >= 3:
        del active_captchas[token]
        return {
            "valid": False,
            "message": "Too many attempts. Please request a new captcha."
        }
    
    # Increment attempts
    captcha_data['attempts'] += 1
    
    # Verify answer
    if user_answer == correct_answer:
        # Remove used captcha
        del active_captchas[token]
        return {
            "valid": True,
            "message": "Captcha verified successfully"
        }
    else:
        remaining = 3 - captcha_data['attempts']
        return {
            "valid": False,
            "message": f"Incorrect answer. {remaining} attempts remaining."
        }