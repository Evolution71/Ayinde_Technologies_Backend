"""
Contact form endpoints - for visitors to submit inquiries.

Endpoints:
- GET /api/captcha - Get CAPTCHA for form protection
- POST /api/contact - Submit contact form message
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from database import get_db
from models import ContactMessage
import schemas
from security import verify_captcha, limiter

router = APIRouter(prefix="/api/contact", tags=["contact"])


@router.post("/", response_model=schemas.ContactResponse)
@limiter.limit("5/minute")
async def submit_contact_form(
    request: Request,
    form: schemas.ContactForm,
    db: Session = Depends(get_db)
):
    """
    Submit a contact form message.
    
    Features:
    - CAPTCHA protection against bots
    - Rate limited to 5 messages per minute per IP
    - All fields are required
    
    Required fields:
    - name: Contact's name (1-100 chars)
    - email: Valid email address
    - phone: Contact phone number
    - company: Company name (optional but recommended)
    - subject: Message subject (1-200 chars)
    - message: Message body (1-5000 chars)
    - captcha_token: From /api/captcha endpoint
    - captcha_answer: Solution to CAPTCHA
    
    Returns: Confirmation message
    
    Errors:
    - 400: Invalid form data or invalid CAPTCHA
    - 429: Rate limited (too many requests)
    - 500: Failed to save message
    """
    
    try:
        # Verify CAPTCHA
        if not verify_captcha(form.captcha_token, form.captcha_answer):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid CAPTCHA. Please try again."
            )
        
        # Create and save message
        message = ContactMessage(
            name=form.name,
            email=form.email,
            phone=form.phone,
            company=form.company,
            subject=form.subject,
            message=form.message,
            ip_address=request.client.host if request.client else None
        )
        
        db.add(message)
        db.commit()
        db.refresh(message)
        
        return {
            "status": "success",
            "message": "Thank you for reaching out! We received your message and will get back to you within 24 hours.",
            "message_id": message.id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit your message. Please try again later."
        )