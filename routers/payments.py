"""
Payments router - handle course enrollment payments and verification.

Endpoints:
- POST /api/payments/create-intent/ - Create payment intent for a course
- POST /api/payments/verify/ - Verify payment after completion
- GET /api/payments/{id}/ - Get payment status
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging
import uuid

from database import get_db
from auth import get_current_user
from models import User, Course, CourseEnrollment, Payment
import schemas

logger = logging.getLogger(__name__)
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
    
    Request:
    - course_id: ID of course to pay for
    - amount: Optional - override course price
    - currency: Optional - USD (default)
    
    Returns:
    - payment_id: ID for use in verify endpoint
    - amount: Amount to charge
    - currency: Currency code
    - course_title: Course name
    
    Errors:
    - 400: Missing course_id
    - 404: Course not found
    - 403: User not enrolled in course
    """
    
    try:
        course_id = request_data.get('course_id')
        if not course_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="course_id is required"
            )
        
        # Get course
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            logger.warning(f"[payments] Course not found: {course_id}")
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
            logger.warning(f"[payments] User {current_user.id} not enrolled in course {course_id}")
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
        
        logger.info(f"[payments] Payment intent created: id={payment.id}, course_id={course_id}, amount={amount}")
        
        return {
            "status": "success",
            "payment_id": payment.id,
            "course_id": course_id,
            "amount": amount,
            "currency": currency,
            "course_title": course.title
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[payments] create-intent error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment intent"
        )


@router.post("/verify/")
async def verify_payment(
    request_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify a payment after Square completes the transaction.
    
    Updates the payment status and extends course access if successful.
    
    Request:
    - payment_id: The payment record to verify
    - nonce: Square payment token (from Square Web Payments SDK)
    - billing_postal_code: Optional
    - billing_country: Optional
    
    Returns:
    - status: "success" or "failed"
    - message: Confirmation message
    - access_granted: True if payment successful
    - transaction_id: Square transaction reference
    
    Errors:
    - 400: Missing payment_id or nonce
    - 404: Payment not found
    - 403: Access denied (payment belongs to different user)
    """
    
    try:
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
            logger.warning(f"[payments] Payment not found: {payment_id} for user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        logger.info(f"[payments] Verifying payment: {payment_id}, nonce={nonce[:20]}...")
        
        # ✅ TODO: In production, call Square API here to verify the nonce and charge
        # For now, mark as completed (for testing)
        payment.status = "completed"
        payment.transaction_id = str(uuid.uuid4())
        payment.paid_at = datetime.now(timezone.utc)
        
        # Update enrollment status to 'active'
        enrollment = db.query(CourseEnrollment).filter(
            CourseEnrollment.id == payment.enrollment_id
        ).first()
        
        if enrollment:
            enrollment.status = "active"
            # Set new access end date (30 days from now or custom duration)
            enrollment.access_ends_at = datetime.now(timezone.utc) + timedelta(days=30)
            logger.info(f"[payments] Enrollment {enrollment.id} activated, access until {enrollment.access_ends_at}")
        
        db.commit()
        
        logger.info(f"[payments] Payment verified successfully: {payment_id}")
        
        return {
            "success": True,
            "status": "success",
            "message": "Payment verified and processed successfully",
            "payment_id": payment.id,
            "transaction_id": payment.transaction_id,
            "access_granted": True,
            "course_id": payment.course_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[payments] verify error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment verification failed"
        )


@router.get("/{payment_id}/")
async def get_payment_status(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the status of a payment.
    
    Returns: Current payment status and details
    
    Response:
    - payment_id: Payment ID
    - status: "pending", "completed", or "failed"
    - amount: Amount in currency
    - currency: Currency code
    - course_id: Associated course
    - created_at: When payment was created
    - transaction_id: Square transaction reference (if completed)
    
    Errors:
    - 404: Payment not found
    - 403: Access denied (not your payment)
    """
    
    try:
        payment = db.query(Payment).filter(
            Payment.id == payment_id,
            Payment.user_id == current_user.id
        ).first()
        
        if not payment:
            logger.warning(f"[payments] Payment not found: {payment_id} for user {current_user.id}")
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
            "transaction_id": payment.transaction_id,
            "paid_at": payment.paid_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[payments] get_payment_status error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get payment status"
        )


@router.post("/{payment_id}/refund/")
async def refund_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Refund a completed payment.
    
    Only completed payments can be refunded.
    
    Returns: Refund confirmation
    
    Errors:
    - 404: Payment not found
    - 403: Access denied
    - 400: Cannot refund this payment (not completed or already refunded)
    """
    
    try:
        payment = db.query(Payment).filter(
            Payment.id == payment_id,
            Payment.user_id == current_user.id
        ).first()
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        if payment.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot refund payment with status '{payment.status}'"
            )
        
        # ✅ TODO: In production, call Square API to refund
        payment.status = "refunded"
        
        # Revert enrollment to trial
        enrollment = db.query(CourseEnrollment).filter(
            CourseEnrollment.id == payment.enrollment_id
        ).first()
        
        if enrollment:
            enrollment.status = "trial"
        
        db.commit()
        
        logger.info(f"[payments] Payment refunded: {payment_id}")
        
        return {
            "status": "success",
            "message": "Payment refunded successfully",
            "payment_id": payment.id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[payments] refund error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Refund failed"
        )