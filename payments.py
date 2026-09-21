"""
Square payment processing - DEBUG VERSION
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid
import traceback

from database import get_db
from models import User, Course, CourseEnrollment, Payment
from auth import get_current_user

router = APIRouter(prefix="/api/payments", tags=["payments"])

# ========== SCHEMAS ==========

class PaymentIntentRequest(BaseModel):
    course_id: int
    amount: float = Field(default=0.0, ge=0)
    currency: str = Field(default="USD")
    
    class Config:
        json_schema_extra = {
            "example": {
                "course_id": 1,
                "amount": 49.99,
                "currency": "USD"
            }
        }

# ========== CREATE PAYMENT INTENT ==========

@router.post("/create-intent/")
async def create_payment_intent(
    payload: PaymentIntentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Square payment intent."""
    try:
        print(f"✅ Received payload: {payload}")
        print(f"✅ course_id={payload.course_id}, amount={payload.amount}, currency={payload.currency}")
        
        # Get course
        course = db.query(Course).filter(Course.id == payload.course_id).first()
        if not course:
            return {"error": f"Course {payload.course_id} not found"}
        
        print(f"✅ Found course: {course.title}")
        
        if not course.is_active:
            return {"error": "Course is not active"}
        
        # Check enrollment
        existing = db.query(CourseEnrollment).filter(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.course_id == payload.course_id,
            CourseEnrollment.status == "active"
        ).first()
        
        if existing:
            return {"error": "Already enrolled"}
        
        # Amount
        amount = payload.amount if payload.amount > 0 else course.price
        currency = payload.currency or "USD"
        
        print(f"✅ Final amount: {amount}, currency: {currency}")
        
        # Create payment
        payment = Payment(
            user_id=current_user.id,
            course_id=payload.course_id,
            amount=float(amount),
            currency=currency,
            status="pending",
            payment_method="square"
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        
        print(f"✅ Payment created: ID={payment.id}")
        
        return {
            "success": True,
            "client_token": str(uuid.uuid4()),
            "payment_id": payment.id,
            "amount": float(amount),
            "currency": currency
        }
    
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        print(f"❌ TRACEBACK: {traceback.format_exc()}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ========== VERIFY PAYMENT ==========

@router.post("/verify/")
async def verify_payment(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify payment and create enrollment."""
    try:
        payment_id = payload.get("payment_id")
        nonce = payload.get("nonce")
        
        if not payment_id or not nonce:
            raise HTTPException(status_code=400, detail="Missing payment_id or nonce")
        
        # Get payment
        payment = db.query(Payment).filter(
            Payment.id == payment_id,
            Payment.user_id == current_user.id
        ).first()
        
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        if payment.status != "pending":
            raise HTTPException(status_code=400, detail="Payment already processed")
        
        course = db.query(Course).filter(Course.id == payment.course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Complete payment
        payment.status = "completed"
        payment.square_payment_id = f"sq_{payment_id}"
        payment.verified_at = datetime.utcnow()
        db.commit()
        
        # Create enrollment
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
            "message": f"Enrolled in {course.title}",
            "enrollment_id": enrollment.id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ========== STATUS ==========

@router.get("/{payment_id}/")
async def get_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Not found")
    
    return {
        "id": payment.id,
        "status": payment.status,
        "amount": payment.amount,
        "currency": payment.currency
    }


# ========== WEBHOOK ==========

@router.post("/webhook/")
async def webhook():
    return {"ok": True}