"""
Square payment processing for Ayinde Technologies courses.
FIXED: Uses Request object to parse JSON body (not query params).
"""

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
    """
    Create a Square payment intent for a course.
    
    Expects JSON body:
    {
        "course_id": 1,
        "amount": 49.99,
        "currency": "USD"
    }
    
    Returns:
    {
        "success": true,
        "client_token": "...",
        "payment_id": 123,
        "amount": 49.99,
        "currency": "USD"
    }
    """
    try:
        # Parse JSON body
        body = await request.json()
        course_id = body.get("course_id")
        amount = body.get("amount", 0)
        currency = body.get("currency", "USD")
        
        print(f"[payments] create-intent: course_id={course_id}, amount={amount}, currency={currency}")
        
        # Validate course_id
        if not course_id:
            raise HTTPException(status_code=400, detail="course_id required")
        
        # Get course from DB
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        if not course.is_active:
            raise HTTPException(status_code=400, detail="Course not active")
        
        # Check for existing active enrollment
        existing = db.query(CourseEnrollment).filter(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.status == "active"
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Already enrolled in this course")
        
        # Use provided amount or fall back to course price
        final_amount = float(amount) if amount > 0 else float(course.price or 0)
        
        # Generate transaction reference
        tx_ref = f"PAY-{current_user.id}-{course_id}-{uuid.uuid4().hex[:8].upper()}"
        
        # Create payment record with course_id set explicitly
        payment = Payment(
            user_id=current_user.id,
            course_id=course_id,
            tx_ref=tx_ref,  # ← ADD THIS
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
        
        print(f"[payments] ✅ Payment created: id={payment.id}, amount={final_amount}")
        
        # Return success response
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
        print(f"[payments] ❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify/")
async def verify_payment(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verify payment and grant course access.
    
    Expects JSON body:
    {
        "payment_id": 123,
        "nonce": "cnp_..."
    }
    
    Returns:
    {
        "success": true,
        "enrollment_id": 456
    }
    """
    try:
        # Parse JSON body
        body = await request.json()
        payment_id = body.get("payment_id")
        nonce = body.get("nonce")
        
        print(f"[payments] verify: payment_id={payment_id}")
        
        # Validate
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
        
        # Get course from payment data
        course_id = payment.payment_data.get("course_id")
        course = db.query(Course).filter(Course.id == course_id).first()
        
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Mark payment as completed
        payment.status = "completed"
        payment.verified_at = datetime.utcnow()
        
        # Get or create enrollment
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
        else:
            enrollment.status = "active"
            enrollment.access_expires_at = datetime.utcnow() + timedelta(days=365)
        
        payment.enrollment_id = enrollment.id
        db.commit()
        
        print(f"[payments] ✅ Payment verified: enrollment_id={enrollment.id}")
        
        return {"success": True, "enrollment_id": enrollment.id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[payments] ❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{payment_id}/")
async def get_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get payment status."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    
    if not payment or payment.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    return {
        "id": payment.id,
        "status": payment.status,
        "amount": payment.amount,
        "currency": payment.currency,
        "created_at": payment.created_at,
        "verified_at": payment.verified_at,
    }


@router.post("/webhook/")
async def webhook():
    """Webhook endpoint for Square events."""
    return {"status": "received"}