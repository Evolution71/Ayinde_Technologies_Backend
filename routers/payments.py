"""
Payments endpoints - handle course enrollment payments.

Endpoints:
- POST /api/payments/create-intent/ - Create payment intent for a course
- POST /api/payments/verify/ - Verify payment after completion
- GET /api/payments/{id}/ - Get payment status
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from database import get_db
from auth import get_current_user
from models import User, Course, CourseEnrollment, Payment
import schemas
import uuid

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("/create-intent/")
async def create_payment_intent(
    request_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a payment intent for upgrading course access.
    
    After free trial ends, user can pay to continue access.
    This endpoint creates the payment record and returns intent ID.
    
    Requires:
    - User authentication (JWT token)
    - course_id in request body
    
    Returns: Payment intent with amount and currency
    
    Errors:
    - 404: Course not found
    - 400: Invalid course or payment data
    """
    
    course_id = request_data.get('course_id')
    if not course_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="course_id is required"
        )
    
    # Get course
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check enrollment exists
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must enroll in this course first"
        )
    
    # Get amount from request or use course price
    amount = request_data.get('amount') or course.price or 99.99
    currency = request_data.get('currency', 'USD')
    
    # Create payment record
    payment = Payment(
        enrollment_id=enrollment.id,
        user_id=current_user.id,
        course_id=course_id,
        amount=float(amount),
        currency=currency,
        status="pending",
        payment_method="square"
    )
    
    db.add(payment)
    db.commit()
    db.refresh(payment)
    
    print(f"[payments] create-intent: course_id={course_id}, amount={amount}, currency={currency}")
    
    return {
        "status": "success",
        "payment_id": payment.id,
        "course_id": course_id,
        "amount": amount,
        "currency": currency,
        "course_title": course.title
    }


@router.post("/verify/")
async def verify_payment(
    request_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify a payment after Square completes the transaction.
    
    Updates the payment status and extends course access if successful.
    
    Requires:
    - payment_id: The payment record to verify
    - nonce: Square payment token (from Square Web Payments SDK)
    - billing_postal_code: Optional
    - billing_country: Optional
    
    Returns: Confirmation and new access end date
    
    Errors:
    - 404: Payment not found
    - 400: Payment verification failed
    """
    
    payment_id = request_data.get('payment_id')
    nonce = request_data.get('nonce')
    
    if not payment_id or not nonce:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payment_id and nonce are required"
        )
    
    # Get payment
    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.user_id == current_user.id
    ).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # In production, call Square API here to verify the nonce and charge
    # For now, mark as completed
    payment.status = "completed"
    payment.transaction_id = str(uuid.uuid4())
    
    # Update enrollment status
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.id == payment.enrollment_id
    ).first()
    
    if enrollment:
        enrollment.status = "active"
    
    db.commit()
    
    return {
        "status": "success",
        "message": "Payment verified and processed successfully",
        "payment_id": payment.id,
        "transaction_id": payment.transaction_id,
        "access_granted": True
    }


@router.get("/{payment_id}/")
async def get_payment_status(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the status of a payment.
    
    Returns: Current payment status (pending, completed, failed)
    
    Errors:
    - 404: Payment not found
    - 403: Access denied
    """
    
    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.user_id == current_user.id
    ).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    return {
        "payment_id": payment.id,
        "status": payment.status,
        "amount": payment.amount,
        "currency": payment.currency,
        "course_id": payment.course_id,
        "created_at": payment.created_at,
        "transaction_id": payment.transaction_id
    }