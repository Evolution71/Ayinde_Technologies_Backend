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

@router.post("/create-intent")
async def create_payment_intent(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Square payment intent for a course.
    
    Returns:
    - client_token: For Square Web Payments SDK
    - payment_id: For verification
    - amount: In cents (e.g., 10000 = $100)
    - currency: USD
    """
    try:
        # Get course
        course = db.query(Course).filter(Course.id == course_id).first()
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
            CourseEnrollment.course_id == course.id,
            CourseEnrollment.status.in_(["trial", "active"])
        ).first()
        
        if existing:
            if existing.status == "trial":
                return {
                    "status": "trial_active",
                    "message": f"You already have free trial access until {existing.trial_ends_at}",
                    "client_token": None,
                    "payment_id": None
                }
            return {
                "status": "already_enrolled",
                "message": "You already have active access to this course",
                "client_token": None,
                "payment_id": None
            }
        
        # Create payment record
        payment = Payment(
            user_id=current_user.id,
            amount=course.price or 100.0,
            currency=course.currency or "USD",
            status="pending",
            payment_method="card",
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
        
        # Get Square client (lazy load)
        try:
            client = get_square_client()
        except HTTPException:
            # If Square not configured, still return payment_id for frontend
            return {
                "status": "unavailable",
                "message": "Payments temporarily unavailable. Please try again later.",
                "client_token": None,
                "payment_id": payment.id
            }
        
        # Generate client token
        try:
            result = client.client.generate_client_token()
            
            if result.is_success():
                client_token = result.result.get("client_token")
                
                # Store metadata
                payment.payment_data["client_token_created"] = datetime.utcnow().isoformat()
                payment.expires_at = datetime.utcnow() + timedelta(hours=24)
                db.commit()
                
                return {
                    "status": "success",
                    "client_token": client_token,
                    "payment_id": payment.id,
                    "amount": int((course.price or 100.0) * 100),  # Convert to cents
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
        
        except HTTPException:
            raise
        except Exception as e:
            payment.status = "failed"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Square service temporarily unavailable"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment intent"
        )


# ========== VERIFY PAYMENT ==========

@router.post("/verify")
async def verify_payment(
    payment_id: int,
    square_payment_id: str,
    square_receipt_url: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verify Square payment and grant course access.
    
    Args:
    - payment_id: Payment ID from create-intent
    - square_payment_id: Payment ID from Square SDK
    - square_receipt_url: Receipt URL (optional)
    """
    try:
        # Get payment
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
        
        if payment.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment already processed"
            )
        
        # Get Square client
        try:
            client = get_square_client()
        except HTTPException:
            raise
        
        # Get course
        course_id = payment.payment_data.get("course_id")
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )
        
        # Verify with Square
        try:
            result = client.payments.retrieve_payment(square_payment_id)
            
            if result.is_success():
                payment_data = result.result.get("payment", {})
                payment_status = payment_data.get("status")
                
                if payment_status == "COMPLETED":
                    # Mark as verified
                    payment.status = "success"
                    payment.square_payment_id = square_payment_id
                    if square_receipt_url:
                        payment.payment_data["receipt_url"] = square_receipt_url
                    payment.verified_at = datetime.utcnow()
                    
                    # Grant course access
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
                        detail=f"Payment status: {payment_status}. Expected: COMPLETED"
                    )
            else:
                payment.status = "failed"
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Could not retrieve payment from Square"
                )
        
        except HTTPException:
            raise
        except Exception as e:
            payment.status = "failed"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment verification failed. Please try again."
            )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification error"
        )


# ========== GET PAYMENT STATUS ==========

@router.get("/{payment_id}")
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

@router.post("/webhook")
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
                payment.status = "success" if payment_status == "COMPLETED" else "failed"
                if payment_status == "COMPLETED":
                    payment.verified_at = datetime.utcnow()
                db.commit()
        
        return {"status": "received"}
    
    except Exception as e:
        # Always return OK to Square
        return {"status": "received"}

# ========== SQUARE WEBHOOK ==========

@router.post("/webhook")
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
                payment.status = "success" if payment_status == "COMPLETED" else "failed"
                if payment_status == "COMPLETED":
                    payment.verified_at = datetime.utcnow()
                db.commit()
        
        return {"status": "received"}
    
    except Exception as e:
        # Always return OK to Square
        return {"status": "received"}