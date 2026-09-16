"""
CAPTCHA endpoints for login and form protection.

Endpoints:
- GET /api/captcha - Generate new CAPTCHA challenge
"""

from fastapi import APIRouter
from security import generate_captcha
import schemas

router = APIRouter(prefix="/api/captcha", tags=["captcha"])


@router.get("/", response_model=schemas.CaptchaOut)
async def get_captcha():
    """
    Generate a new CAPTCHA challenge image.
    
    This endpoint generates a random CAPTCHA image with letters/numbers
    that the user must solve before accessing protected forms.
    
    Returns:
    - token: Unique ID for this CAPTCHA (use when submitting forms)
    - image: Base64-encoded PNG image, ready to display in browser
    
    Usage flow:
    1. Frontend calls this endpoint to get a new CAPTCHA
    2. Display the image to the user
    3. User enters the text they see (e.g., "3X2M5")
    4. When submitting login/register/contact form, include:
       - captcha_token: The token from step 1
       - captcha_answer: The user's answer from step 3
    5. Backend verifies automatically in auth/contact endpoints
    
    Note: CAPTCHA tokens expire after 5 minutes of inactivity
    """
    
    # Generate random CAPTCHA and get token + image
    token, image_base64 = generate_captcha()
    
    # Return as data URI (browser-ready format)
    return {
        "token": token,
        "image": f"data:image/png;base64,{image_base64}"
    }