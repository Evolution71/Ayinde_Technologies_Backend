"""
Square payment processing - SIMPLE VERSION (no schema validation)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

from database import get_db
from models import User, Course, CourseEnrollment, Payment
from auth import get_current_user

router = APIRouter(prefix="/api/payments", tags=["payments"])

# ========== CREATE PAYMENT INTENT ==========

@router.post("/create-intent/")
async def create_payment_intent(
    body: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Square payment intent.
    Body: { "course_id": int, "amount": float, "currency": str }
    """
    try:
        # Extract fields
        course_id = body.get("course_id")
        amount = body.get("amount", 0)
        currency = body.get("currency", "USD")
        
        if not course_id:
            raise HTTPException(status_code=400, detail="course_id is required")
        
        # Get course
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail=f"Course not found")
        
        if not course.is_active:
            raise HTTPException(status_code=400, detail="Course is not active")
        
        # Check if already enrolled
        existing = db.query(CourseEnrollment).filter(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.status == "active"
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Already enrolled")
        
        # Use provided amount or course price
        final_amount = float(amount) if amount > 0 else float(course.price or 0)
        
        # Create payment record
        payment = Payment(
            user_id=current_user.id,
            course_id=course_id,
            amount=final_amount,
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
            "amount": final_amount,
            "currency": currency
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ========== VERIFY PAYMENT ==========

@router.post("/verify/")
async def verify_payment(
    body: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verify payment and create enrollment.
    Body: { "payment_id": int, "nonce": str }
    """
    try:
        payment_id = body.get("payment_id")
        nonce = body.get("nonce")
        
        if not payment_id or not nonce:
            raise HTTPException(status_code=400, detail="payment_id and nonce required")
        
        # Get payment
        payment = db.query(Payment).filter(
            Payment.id == payment_id,
            Payment.user_id == current_user.id
        ).first()
        
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        if payment.status != "pending":
            raise HTTPException(status_code=400, detail="Payment already processed")
        
        # Get course
        course = db.query(Course).filter(Course.id == payment.course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Mark payment as completed
        payment.status = "completed"
        payment.square_payment_id = f"sq_{payment_id}"
        payment.verified_at = datetime.utcnow()
        db.add(payment)
        db.commit()
        
        # Create or update enrollment
        enrollment = db.query(CourseEnrollment).filter(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.course_id == payment.course_id
        ).first()
        
        if not enrollment:
            enrollment = CourseEnrollment(
                user_id=current_user.id,
                course_id=payment.course_id,
                status="active",
                access_expires_at=datetime.utcnow() + timedelta(days=365)
            )
            db.add(enrollment)
        else:
            enrollment.status = "active"
            enrollment.access_expires_at = datetime.utcnow() + timedelta(days=365)
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Payment verified! Access to {course.title} is now active.",
            "payment_id": payment.id,
            "course_id": payment.course_id,
            "enrollment_id": enrollment.id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


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
async def handle_square_webhook():
    """Handle Square webhook events."""
    return {"status": "received"}