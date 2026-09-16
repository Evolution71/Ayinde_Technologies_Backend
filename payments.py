"""
Payment processing endpoints - Square integration.

Features:
- Initialize payments for course subscriptions
- Create payment intents for Square
- Verify payment completion
- Get payment status
- Webhook handling for payment notifications

Endpoints:
- POST /api/payments/create-intent - Create Square payment intent
- POST /api/payments/verify - Verify payment completion
- GET /api/payments/{id} - Get payment status
- POST /api/payments/webhook - Receive Square webhooks
"""

import os
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import hmac
import hashlib
import json
from typing import Optional
import uuid

from squareup.client import Client
from squareup.api_client import ApiClient
from squareup.exceptions import ApiException

from database import SessionLocal, get_db
from auth import get_current_user  # ✅ CORRECT IMPORT
from models import User, Course, CourseEnrollment, Payment
import schemas

router = APIRouter(prefix="/api/payments", tags=["payments"])

# Square configuration
SQUARE_ACCESS_TOKEN = os.getenv("SQUARE_ACCESS_TOKEN", "")
SQUARE_APPLICATION_ID = os.getenv("SQUARE_APPLICATION_ID", "")
SQUARE_LOCATION_ID = os.getenv("SQUARE_LOCATION_ID", "")
SQUARE_ENVIRONMENT = os.getenv("SQUARE_ENVIRONMENT", "sandbox")  # sandbox or production
WEBHOOK_SIGNATURE_KEY = os.getenv("SQUARE_WEBHOOK_SIGNATURE_KEY", "")

# Initialize Square client
square_client = None
if SQUARE_ACCESS_TOKEN:
    square_client = Client(
        access_token=SQUARE_ACCESS_TOKEN,
        environment=SQUARE_ENVIRONMENT
    )


# ========== PAYMENT INTENT CREATION ==========

@router.post("/create-intent")
async def create_payment_intent(
    request: schemas.PaymentInitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Square payment intent for a course.
    
    Features:
    - Prevents duplicate payments
    - Creates payment record for tracking
    - Returns client token for frontend to use with Square Web Payments SDK
    
    Request body:
    - course_id: The course to purchase
    
    Returns:
    - client_token: Use this in frontend with Square Web Payments SDK
    - payment_id: For verification later
    - amount: Amount in cents (e.g., 10000 = $100.00)
    - currency: USD
    
    Errors:
    - 404: Course not found
    - 400: Already has active access
    - 503: Square service unavailable
    """
    
    try:
        # Get course
        course = db.query(Course).filter(Course.id == request.course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )
        
        # Check for existing active enrollment
        existing = db.query(CourseEnrollment).filter(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.course_id == course.id,
            CourseEnrollment.status.in_(["trial", "active"])
        ).first()
        
        if existing:
            if existing.status == "trial":
                return {
                    "status": "trial_active",
                    "message": f"You already have free trial access until {existing.trial_ends_at}",
                    "client_token": None
                }
            return {
                "status": "already_enrolled",
                "message": "You already have active access to this course",
                "client_token": None
            }
        
        # Create payment record
        payment = Payment(
            user_id=current_user.id,
            amount=course.price or 100.0,
            currency=course.currency or "USD",
            status="pending",
            payment_data={
                "course_id": course.id,
                "course_title": course.title,
                "user_email": current_user.email,
                "user_name": current_user.name,
                "idempotency_key": str(uuid.uuid4())
            }
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        
        # Check if Square is configured
        if not SQUARE_ACCESS_TOKEN or not square_client:
            return {
                "status": "unavailable",
                "message": "Payments are temporarily unavailable. Please contact support.",
                "client_token": None,
                "payment_id": payment.id
            }
        
        try:
            # Generate client token for Web Payments SDK
            result = square_client.client.generate_client_token()
            
            if result.is_success():
                client_token = result.result.get("client_token")
                
                # Store metadata for verification
                payment.payment_data["client_token_created"] = datetime.utcnow().isoformat()
                payment.expires_at = datetime.utcnow() + timedelta(hours=24)
                db.commit()
                
                return {
                    "status": "success",
                    "message": "Payment intent created. Use the client token with Square Web Payments SDK.",
                    "client_token": client_token,
                    "payment_id": payment.id,
                    "amount": int(course.price * 100) if course.price else 10000,  # Convert to cents
                    "currency": course.currency or "USD",
                    "course_title": course.title
                }
            else:
                payment.status = "failed"
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to create payment intent"
                )
        
        except ApiException as e:
            payment.status = "failed"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Square service unavailable. Please try again later."
            )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate payment"
        )


# ========== PAYMENT VERIFICATION ==========

@router.post("/verify")
async def verify_payment(
    request: schemas.PaymentVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verify Square payment and activate course access.
    
    After user completes payment in Square Web Payments SDK, verify here.
    
    Request body:
    - payment_id: Payment ID from create-intent endpoint
    - square_payment_id: Payment ID returned from Square
    - square_receipt_url: Receipt URL from Square (optional)
    
    Returns:
    - Success confirmation
    - Course access granted
    - Enrollment details
    
    Errors:
    - 404: Payment not found
    - 403: Payment belongs to different user
    - 400: Payment verification failed
    """
    
    if not SQUARE_ACCESS_TOKEN or not square_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payments are unavailable"
        )
    
    try:
        # Get payment record
        payment = db.query(Payment).filter(Payment.id == request.payment_id).first()
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        if payment.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized"
            )
        
        # Verify with Square
        try:
            result = square_client.payments.retrieve_payment(request.square_payment_id)
            
            if result.is_success():
                payment_data = result.result.get("payment", {})
                payment_status = payment_data.get("status")
                
                if payment_status == "COMPLETED":
                    # Payment verified - grant access
                    payment.status = "success"
                    payment.flutterwave_transaction_id = request.square_payment_id  # Reusing field for Square ID
                    payment.payment_method = "square"
                    payment.verified_at = datetime.utcnow()
                    
                    # Store Square receipt URL if provided
                    if request.square_receipt_url:
                        payment.payment_data["receipt_url"] = request.square_receipt_url
                    
                    # Get course
                    course_id = payment.payment_data.get("course_id")
                    course = db.query(Course).filter(Course.id == course_id).first()
                    
                    if not course:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="Course not found"
                        )
                    
                    # Create/update enrollment
                    enrollment = db.query(CourseEnrollment).filter(
                        CourseEnrollment.user_id == current_user.id,
                        CourseEnrollment.course_id == course_id
                    ).first()
                    
                    if not enrollment:
                        enrollment = CourseEnrollment(
                            user_id=current_user.id,
                            course_id=course_id,
                            status="trial",
                            trial_ends_at=datetime.utcnow() + timedelta(days=course.trial_duration_days or 30)
                        )
                        db.add(enrollment)
                    
                    # Activate access
                    enrollment.status = "active"
                    enrollment.access_expires_at = datetime.utcnow() + timedelta(days=365)  # 1 year
                    enrollment.last_accessed_at = datetime.utcnow()
                    payment.enrollment_id = enrollment.id
                    
                    db.commit()
                    
                    return {
                        "status": "success",
                        "message": f"Payment verified! Access to {course.title} is now active.",
                        "course_id": course_id,
                        "enrollment_id": enrollment.id
                    }
                else:
                    payment.status = "failed"
                    db.commit()
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Payment status is {payment_status}. Expected COMPLETED."
                    )
            else:
                payment.status = "failed"
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to retrieve payment from Square"
                )
        
        except ApiException as e:
            payment.status = "failed"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Square verification failed. Please try again."
            )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification error"
        )


# ========== WEBHOOK HANDLER ==========

@router.post("/webhook")
async def handle_square_webhook(
    http_request: Request,
    db: Session = Depends(get_db),
):
    """
    Handle webhooks from Square.
    
    Square will POST payment notifications here.
    Verifies webhook signature and updates payment status.
    
    Returns: Webhook received confirmation
    """
    
    if not WEBHOOK_SIGNATURE_KEY:
        return {"status": "received"}  # Silent accept if no signature key
    
    try:
        # Get request body
        body = await http_request.body()
        body_str = body.decode("utf-8")
        
        # Get signature from headers
        square_signature = http_request.headers.get("x-square-hmac-sha256")
        if not square_signature:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No signature provided"
            )
        
        # Get request path (needed for signature verification)
        request_path = http_request.url.path
        
        # Verify signature using Square's method
        message = request_path + body_str
        computed_signature = hmac.new(
            WEBHOOK_SIGNATURE_KEY.encode(),
            message.encode(),
            hashlib.sha256
        ).digest()
        
        import base64
        computed_signature_b64 = base64.b64encode(computed_signature).decode()
        
        if not hmac.compare_digest(square_signature, computed_signature_b64):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )
        
        # Process webhook
        data = json.loads(body_str)
        
        if data.get("type") == "payment.created" or data.get("type") == "payment.updated":
            payment_obj = data.get("data", {}).get("object", {}).get("payment", {})
            payment_id = payment_obj.get("id")
            payment_status = payment_obj.get("status")
            
            # Update payment record
            payment = db.query(Payment).filter(
                Payment.flutterwave_transaction_id == payment_id
            ).first()
            
            if payment:
                payment.status = "success" if payment_status == "COMPLETED" else "failed"
                payment.verified_at = datetime.utcnow()
                db.commit()
        
        return {"status": "received"}
    
    except Exception as e:
        return {"status": "received"}  # Always return OK to Square


# ========== GET PAYMENT STATUS ==========

@router.get("/{payment_id}")
async def get_payment_status(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the status of a payment.
    
    Returns: Payment details and current status
    
    Errors:
    - 404: Payment not found
    - 403: Payment belongs to different user
    """
    
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    if payment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized"
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