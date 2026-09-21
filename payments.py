from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

from database import get_db
from models import User, Course, CourseEnrollment, Payment
from auth import get_current_user

router = APIRouter(prefix="/api/payments", tags=["payments"])

@router.post("/create-intent/")
async def create_payment_intent(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create payment intent - NO Pydantic validation"""
    try:
        # Get raw JSON
        body = await request.json()
        course_id = body.get("course_id")
        amount = body.get("amount", 0)
        currency = body.get("currency", "USD")
        
        # Validate
        if not course_id:
            raise HTTPException(status_code=400, detail="course_id required")
        
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Create payment
        final_amount = float(amount) if amount > 0 else float(course.price or 0)
        payment = Payment(
            user_id=current_user.id,
            amount=final_amount,
            currency=currency,
            status="pending",
            payment_method="square",
            payment_data={"course_id": course_id},
            expires_at=datetime.utcnow() + timedelta(hours=24)
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


@router.post("/verify/")
async def verify_payment(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify payment - NO Pydantic validation"""
    try:
        body = await request.json()
        payment_id = body.get("payment_id")
        nonce = body.get("nonce")
        
        if not payment_id or not nonce:
            raise HTTPException(status_code=400, detail="Missing fields")
        
        payment = db.query(Payment).filter(
            Payment.id == payment_id,
            Payment.user_id == current_user.id
        ).first()
        
        if not payment or payment.status != "pending":
            raise HTTPException(status_code=400, detail="Invalid payment")
        
        course_id = payment.payment_data.get("course_id")
        course = db.query(Course).filter(Course.id == course_id).first()
        
        # Mark completed
        payment.status = "completed"
        payment.verified_at = datetime.utcnow()
        
        # Create enrollment
        enrollment = db.query(CourseEnrollment).filter(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.course_id == course_id
        ).first()
        
        if not enrollment:
            enrollment = CourseEnrollment(
                user_id=current_user.id,
                course_id=course_id,
                status="active",
                access_expires_at=datetime.utcnow() + timedelta(days=365)
            )
            db.add(enrollment)
        
        payment.enrollment_id = enrollment.id
        db.commit()
        
        return {"success": True, "enrollment_id": enrollment.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{payment_id}/")
async def get_payment(payment_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment or payment.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    return {"id": payment.id, "status": payment.status, "amount": payment.amount}


@router.post("/webhook/")
async def webhook():
    return {"ok": True}