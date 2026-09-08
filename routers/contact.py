from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from security import limiter, verify_captcha

router = APIRouter(prefix="/api/contact", tags=["contact"])


@router.post("", response_model=schemas.ContactResponse)
@limiter.limit("5/minute")
def submit_contact(request: Request, payload: schemas.ContactForm, db: Session = Depends(get_db)):
    if not verify_captcha(payload.captcha_token, payload.captcha_answer):
        raise HTTPException(status_code=400, detail="Captcha incorrect or expired — please try again.")

    record = models.ContactMessage(
        name=payload.name.strip(),
        email=payload.email,
        phone=payload.phone,
        company=payload.company,
        subject=payload.subject,
        message=payload.message.strip(),
    )
    db.add(record)
    db.commit()

    return schemas.ContactResponse(
        status="success",
        message=f"Thank you {payload.name}! We've received your message and will contact you within 24 hours.",
    )
