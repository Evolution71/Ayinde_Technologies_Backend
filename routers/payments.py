"""
Flutterwave payment integration for Ayinde Technologies.
Handles payment initialization, verification, and webhook handling.
"""

import os
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import requests
from datetime import datetime, timedelta
import hmac
import hashlib
from typing import Optional

from database import SessionLocal
from security import get_current_user
from models import User, Course, CourseEnrollment, Payment
import schemas

router = APIRouter(prefix="/api/payments", tags=["payments"])

# Flutterwave config
FLW_PUBLIC_KEY = os.getenv("FLUTTERWAVE_PUBLIC_KEY")
FLW_SECRET_KEY = os.getenv("FLUTTERWAVE_SECRET_KEY")
FLW_BASE_URL = "https://api.flutterwave.com/v3"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ========== Payment Initialization ==========

@router.post("/initiate")
def initiate_payment(
    request: schemas.PaymentInitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Initiate a payment for a course using Flutterwave.
    Returns payment link for the user to proceed.
    """
    
    # Get course
    course = db.query(Course).filter(Course.id == request.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Check if user already has active enrollment
    existing = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course.id,
        CourseEnrollment.status.in_(["trial", "active"])
    ).first()
    
    if existing:
        if existing.status == "trial":
            return {
                "status": "trial_active",
                "message": "You're already in the free trial. Trial ends at: " + str(existing.trial_ends_at),
                "payment_link": None
            }
        else:
            return {
                "status": "already_enrolled",
                "message": "You already have active access to this course",
                "payment_link": None
            }
    
    # Create payment record (PENDING)
    payment = Payment(
        user_id=current_user.id,
        amount=course.price,
        currency=course.currency,
        status="pending",
        payment_data={
            "course_id": course.id,
            "course_title": course.title,
            "user_email": current_user.email,
            "user_name": current_user.name,
        }
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    
    # Prepare Flutterwave payload
    payload = {
        "tx_ref": f"ayinde-{payment.id}-{current_user.id}",  # Unique reference
        "amount": course.price,
        "currency": course.currency,
        "payment_options": "card, banktransfer, mobilemoney, ussd",  # All payment methods
        "customer": {
            "email": current_user.email,
            "name": current_user.name,
        },
        "customizations": {
            "title": f"Ayinde Technologies - {course.title}",
            "description": f"Unlock full access to {course.title} course",
            "logo": "https://ayindetechnologies.com/logo-mark.svg"
        },
        "meta": {
            "payment_id": payment.id,
            "course_id": course.id,
        },
        "redirect_url": request.redirect_url or f"https://ayindetechnologies.com/payment/verify?payment_id={payment.id}"
    }
    
    # Call Flutterwave API
    try:
        response = requests.post(
            f"{FLW_BASE_URL}/payments",
            json=payload,
            headers={"Authorization": f"Bearer {FLW_SECRET_KEY}"}
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "success":
            # Store Flutterwave reference
            payment.flutterwave_reference = data["data"]["link"]
            payment.payment_data["flutterwave_payment_id"] = data["data"]["id"]
            payment.expires_at = datetime.utcnow() + timedelta(hours=24)
            db.commit()
            
            return {
                "status": "success",
                "message": "Payment link generated",
                "payment_link": data["data"]["link"],
                "payment_id": payment.id
            }
        else:
            payment.status = "failed"
            db.commit()
            raise HTTPException(status_code=400, detail="Failed to generate payment link")
    
    except requests.RequestException as e:
        payment.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Payment service error: {str(e)}")


# ========== Payment Verification ==========

@router.post("/verify")
def verify_payment(
    request: schemas.PaymentVerifyRequest,
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """
    Verify Flutterwave payment status using transaction reference.
    On success, creates/activates course enrollment.
    """
    
    # Get payment record
    payment = db.query(Payment).filter(Payment.id == request.payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # Query Flutterwave
    try:
        response = requests.get(
            f"{FLW_BASE_URL}/transactions/{request.transaction_id}/verify",
            headers={"Authorization": f"Bearer {FLW_SECRET_KEY}"}
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "success" and data["data"]["status"] == "successful":
            # Payment verified!
            payment.status = "success"
            payment.flutterwave_transaction_id = data["data"]["id"]
            payment.payment_method = data["data"].get("payment_method", "card")
            payment.verified_at = datetime.utcnow()
            
            # Get course from enrollment or payment_data
            course_id = payment.payment_data.get("course_id")
            course = db.query(Course).filter(Course.id == course_id).first()
            
            if not course:
                raise HTTPException(status_code=404, detail="Course not found")
            
            # Create/update enrollment
            enrollment = db.query(CourseEnrollment).filter(
                CourseEnrollment.user_id == current_user.id,
                CourseEnrollment.course_id == course_id
            ).first()
            
            if not enrollment:
                # If no enrollment, create one with trial first
                enrollment = CourseEnrollment(
                    user_id=current_user.id,
                    course_id=course_id,
                    status="trial",
                    trial_ends_at=datetime.utcnow() + timedelta(days=course.trial_duration_days)
                )
                db.add(enrollment)
            
            # After trial, mark as active
            enrollment.status = "active"
            enrollment.access_expires_at = datetime.utcnow() + timedelta(days=365)  # 1 year subscription
            enrollment.last_accessed_at = datetime.utcnow()
            
            # Link payment to enrollment
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
            raise HTTPException(status_code=400, detail="Payment verification failed")
    
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Verification error: {str(e)}")


# ========== Webhook Handler (Flutterwave → Your Backend) ==========

@router.post("/webhook")
def handle_flutterwave_webhook(
    request: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Handle Flutterwave webhook notifications.
    Verify webhook signature and process payment status changes.
    """
    
    # Verify webhook signature
    flw_signature = request.headers.get("verif-hash")
    webhook_secret = os.getenv("FLUTTERWAVE_WEBHOOK_SECRET")
    
    if not flw_signature:
        raise HTTPException(status_code=401, detail="No signature provided")
    
    # Compute HMAC SHA256
    body = request.body
    computed_signature = hmac.new(
        webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(flw_signature, computed_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Process webhook
    data = request.json()
    
    if data.get("event") == "charge.completed":
        tx_id = data["data"]["id"]
        status = data["data"]["status"]
        
        # Update payment
        payment = db.query(Payment).filter(
            Payment.flutterwave_transaction_id == tx_id
        ).first()
        
        if payment:
            payment.status = "success" if status == "successful" else "failed"
            payment.verified_at = datetime.utcnow()
            db.commit()
    
    return {"status": "received"}


# ========== Get Payment Status ==========

@router.get("/{payment_id}")
def get_payment_status(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the status of a payment.
    """
    
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    return {
        "id": payment.id,
        "status": payment.status,
        "amount": payment.amount,
        "currency": payment.currency,
        "payment_method": payment.payment_method,
        "created_at": payment.created_at,
        "verified_at": payment.verified_at,
    }