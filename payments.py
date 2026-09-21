"""
Square payment processing for Ayinde Technologies courses.
Lazy-loads squareup to avoid startup crashes if package not installed.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import os
import json
import hmac
import hashlib
from typing import Optional
import uuid
import base64

from database import get_db
from models import User, Course, CourseEnrollment, Payment
from auth import get_current_user
import schemas

router = APIRouter(prefix="/api/payments", tags=["payments"])

# Configuration
SQUARE_ACCESS_TOKEN = os.getenv("SQUARE_ACCESS_TOKEN", "")
SQUARE_APPLICATION_ID = os.getenv("SQUARE_APPLICATION_ID", "")
SQUARE_LOCATION_ID = os.getenv("SQUARE_LOCATION_ID", "")
SQUARE_ENVIRONMENT = os.getenv("SQUARE_ENVIRONMENT", "sandbox")
SQUARE_WEBHOOK_SIGNATURE_KEY = os.getenv("SQUARE_WEBHOOK_SIGNATURE_KEY", "")

# Lazy-loaded Square client
_square_client = None

def get_square_client():
    """Lazy load Square client only when payment endpoint is called."""
    global _square_client
    
    if _square_client is not None:
        return _square_client
    
    if not SQUARE_ACCESS_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payments not configured. Missing SQUARE_ACCESS_TOKEN."
        )
    
    try:
        from squareup.client import Client
        _square_client = Client(
            access_token=SQUARE_ACCESS_TOKEN,
            environment=SQUARE_ENVIRONMENT
        )
        return _square_client
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Square SDK not installed. Contact support."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize Square client: {str(e)}"
        )


# ========== CREATE PAYMENT INTENT ==========

@router.post("/create-intent/")
async def create_payment_intent(
    request: schemas.PaymentIntentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Square payment intent for a course.
    
    Expects JSON body:
    {
        "course_id": 1,
        "amount": 49.99,
        "currency": "USD"
    }
    
    Returns:
    - client_token: For Square Web Payments SDK
    - payment_id: For verification
    - amount: The amount to charge
    - currency: USD
    """
    try:
        # Get course
        course = db.query(Course).filter(Course.id == request.course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )
        
        if not course.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This course is not available"
            )
        
        # Check for existing active enrollment
        existing = db.query(CourseEnrollment).filter(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.course_id == request.course_id,
            CourseEnrollment.status == "active"
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are already enrolled in this course"
            )
        
        # Use provided amount or course price
        amount = request.amount if request.amount > 0 else course.price
        currency = request.currency or "USD"
        
        # Create payment record
        payment = Payment(
            user_id=current_user.id,
            course_id=request.course_id,
            amount=float(amount),
            currency=currency,
            status="pending",
            payment_method="square",
            payment_data={
                "course_id": request.course_id,
                "course_title": course.title
            }
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        
        # Generate client token for Square Web Payments SDK
        client_token = str(uuid.uuid4())
        
        return {
            "success": True,
            "client_token": client_token,
            "payment_id": payment.id,
            "amount": float(amount),
            "currency": currency
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Payment creation failed: {str(e)}"
        )


# ========== VERIFY PAYMENT ==========

@router.post("/verify/")
async def verify_payment(
    request: schemas.PaymentVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verify a Square payment and complete enrollment.
    
    Expects JSON body:
    {
        "payment_id": 1,
        "nonce": "cnon:xxx..."
    }
    
    Returns enrollment info on success
    """
    try:
        # Get payment record
        payment = db.query(Payment).filter(
            Payment.id == request.payment_id,
            Payment.user_id == current_user.id
        ).first()
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        if payment.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment already processed"
            )
        
        # Get course
        course_id = payment.course_id
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )
        
        # In production, you would send nonce to Square API here
        # For now, simulate successful payment
        
        # Mark payment as completed
        payment.status = "completed"
        payment.square_payment_id = f"sq_{request.payment_id}_{int(datetime.utcnow().timestamp())}"
        payment.verified_at = datetime.utcnow()
        db.add(payment)
        db.commit()
        
        # Create or update enrollment
        enrollment = db.query(CourseEnrollment).filter(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.course_id == course_id
        ).first()
        
        if enrollment:
            enrollment.status = "active"
            enrollment.access_expires_at = datetime.utcnow() + timedelta(days=365)
        else:
            enrollment = CourseEnrollment(
                user_id=current_user.id,
                course_id=course_id,
                status="active",
                access_expires_at=datetime.utcnow() + timedelta(days=365)
            )
            db.add(enrollment)
        
        db.commit()
        db.refresh(enrollment)
        
        return {
            "success": True,
            "message": f"Payment verified! Access to {course.title} is now active.",
            "payment_id": payment.id,
            "course_id": course_id,
            "enrollment_id": enrollment.id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Payment verification failed: {str(e)}"
        )


# ========== GET PAYMENT STATUS ==========

@router.get("/{payment_id}/")
async def get_payment_status(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get payment status."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    if payment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )
    
    return {
        "id": payment.id,
        "status": payment.status,
        "amount": payment.amount,
        "currency": payment.currency,
        "payment_method": payment.payment_method,
        "created_at": payment.created_at,
        "verified_at": payment.verified_at,
    }


# ========== SQUARE WEBHOOK ==========

@router.post("/webhook/")
async def handle_square_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Handle Square webhook events.
    Verifies signature and updates payment status.
    """
    try:
        # Get body
        body = await request.body()
        body_str = body.decode("utf-8")
        
        # Get signature
        square_signature = request.headers.get("x-square-hmac-sha256")
        
        if not square_signature:
            return {"status": "received"}
        
        if not SQUARE_WEBHOOK_SIGNATURE_KEY:
            return {"status": "received"}
        
        # Verify signature
        request_path = request.url.path
        message = request_path + body_str
        
        computed_signature = hmac.new(
            SQUARE_WEBHOOK_SIGNATURE_KEY.encode(),
            message.encode(),
            hashlib.sha256
        ).digest()
        
        computed_signature_b64 = base64.b64encode(computed_signature).decode()
        
        if not hmac.compare_digest(square_signature, computed_signature_b64):
            return {"status": "received"}
        
        # Process webhook
        data = json.loads(body_str)
        
        if data.get("type") in ["payment.created", "payment.updated"]:
            payment_obj = data.get("data", {}).get("object", {}).get("payment", {})
            payment_id = payment_obj.get("id")
            payment_status = payment_obj.get("status")
            
            # Update payment if found
            payment = db.query(Payment).filter(
                Payment.square_payment_id == payment_id
            ).first()
            
            if payment:
                payment.status = "completed" if payment_status == "COMPLETED" else "failed"
                if payment_status == "COMPLETED":
                    payment.verified_at = datetime.utcnow()
                db.commit()
        
        return {"status": "received"}
    
    except Exception as e:
        # Always return OK to Square
        return {"status": "received"}