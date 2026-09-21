"""
Square payment processing for Ayinde Technologies courses.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import os
import uuid

from database import get_db
from models import User, Course, CourseEnrollment, Payment
from auth import get_current_user

router = APIRouter(prefix="/api/payments", tags=["payments"])

# ========== SCHEMAS (inline to avoid import issues) ==========

class PaymentIntentRequest(BaseModel):
    course_id: int
    amount: float = 0.0
    currency: str = "USD"

class PaymentVerificationRequest(BaseModel):
    payment_id: int
    nonce: str

# ========== CREATE PAYMENT INTENT ==========

@router.post("/create-intent/")
async def create_payment_intent(
    request_body: PaymentIntentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Square payment intent for a course.
    
    Request body:
    {
        "course_id": 1,
        "amount": 49.99,
        "currency": "USD"
    }
    """
    try:
        # Extract from request body
        course_id = request_body.course_id
        amount = request_body.amount
        currency = request_body.currency or "USD"
        
        # Get course
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        if not course.is_active:
            raise HTTPException(status_code=400, detail="This course is not available")
        
        # Check for existing enrollment
        existing = db.query(CourseEnrollment).filter(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.status == "active"
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="You are already enrolled in this course")
        
        # Use provided amount or course price
        final_amount = amount if amount > 0 else course.price
        
        # Create payment record
        payment = Payment(
            user_id=current_user.id,
            course_id=course_id,
            amount=float(final_amount),
            currency=currency,
            status="pending",
            payment_method="square"
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        
        return {
            "success": True,
            "client_token": str(uuid.uuid4()),
            "payment_id": payment.id,
            "amount": float(final_amount),
            "currency": currency
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Payment creation failed: {str(e)}")


# ========== VERIFY PAYMENT ==========

@router.post("/verify/")
async def verify_payment(
    request_body: PaymentVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verify a Square payment and complete enrollment.
    
    Request body:
    {
        "payment_id": 1,
        "nonce": "cnon:xxx..."
    }
    """
    try:
        # Extract from request body
        payment_id = request_body.payment_id
        nonce = request_body.nonce
        
        # Get payment record
        payment = db.query(Payment).filter(
            Payment.id == payment_id,
            Payment.user_id == current_user.id
        ).first()
        
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        if payment.status != "pending":
            raise HTTPException(status_code=400, detail="Payment already processed")
        
        # Get course
        course_id = payment.course_id
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Mark payment as completed
        payment.status = "completed"
        payment.square_payment_id = f"sq_{payment_id}_{int(datetime.utcnow().timestamp())}"
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
        raise HTTPException(status_code=500, detail=f"Payment verification failed: {str(e)}")


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
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return {
        "id": payment.id,
        "status": payment.status,
        "amount": payment.amount,
        "currency": payment.currency,
        "created_at": payment.created_at,
        "verified_at": payment.verified_at,
    }


# ========== SQUARE WEBHOOK ==========

@router.post("/webhook/")
async def handle_square_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle Square webhook events."""
    return {"status": "received"}