"""
Endpoint to save payment method for subscription auto-charge
Add to backend/routers/courses.py
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from database import SessionLocal, get_db
from models import CourseEnrollment, Course
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post('/api/courses/{course_id}/save-card/')
async def save_payment_method(
    course_id: int,
    request: Request,
    db: SessionLocal = Depends(get_db)
):
    """
    Save Square card token for auto-charge after trial
    
    Request body:
    {
        "nonce": "cnon:CA4SE..."  // Square card token
    }
    
    Response:
    {
        "success": true,
        "message": "Card saved. Trial will auto-charge on 2026-10-23",
        "charge_date": "2026-10-23T00:00:00",
        "trial_days_remaining": 30
    }
    """
    try:
        # Get user from auth token
        user_id = request.state.user_id
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Parse request body
        body = await request.json()
        nonce = body.get('nonce')
        
        if not nonce:
            raise HTTPException(status_code=400, detail="Card token (nonce) required")
        
        # Find active trial enrollment
        enrollment = db.query(CourseEnrollment).filter(
            CourseEnrollment.user_id == user_id,
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.status == 'trial'
        ).first()
        
        if not enrollment:
            raise HTTPException(status_code=404, detail='No active trial enrollment found')
        
        # Save card token
        enrollment.payment_method_id = nonce
        
        # Calculate days remaining
        now = datetime.utcnow()
        days_remaining = (enrollment.trial_ends_at - now).days
        
        db.commit()
        
        logger.info(f"[Save-Card] User {user_id} saved card for enrollment {enrollment.id}")
        
        return {
            'success': True,
            'message': f'✅ Card saved! Your trial will auto-charge on {enrollment.trial_ends_at.strftime("%B %d, %Y")}',
            'charge_date': enrollment.trial_ends_at.isoformat(),
            'trial_days_remaining': max(0, days_remaining),
            'amount': float(enrollment.course.price),
            'currency': 'USD'
        }
        
    except Exception as err:
        logger.error(f"[Save-Card] Error: {str(err)}")
        raise HTTPException(status_code=500, detail=str(err))


@router.get('/api/courses/{course_id}/enrollment-status/')
async def get_enrollment_status(
    course_id: int,
    request: Request,
    db: SessionLocal = Depends(get_db)
):
    """
    Get current enrollment status
    
    Response:
    {
        "enrolled": true,
        "status": "trial",
        "trial_ends_at": "2026-10-23T00:00:00",
        "days_remaining": 30,
        "card_saved": false,
        "auto_charge_date": "2026-10-23"
    }
    """
    try:
        user_id = request.state.user_id
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        enrollment = db.query(CourseEnrollment).filter(
            CourseEnrollment.user_id == user_id,
            CourseEnrollment.course_id == course_id
        ).first()
        
        if not enrollment:
            return {
                'enrolled': False,
                'status': None,
                'message': 'Not enrolled in this course'
            }
        
        now = datetime.utcnow()
        
        if enrollment.status == 'trial':
            days_remaining = (enrollment.trial_ends_at - now).days
            return {
                'enrolled': True,
                'status': 'trial',
                'trial_ends_at': enrollment.trial_ends_at.isoformat(),
                'days_remaining': max(0, days_remaining),
                'card_saved': bool(enrollment.payment_method_id),
                'auto_charge_date': enrollment.trial_ends_at.strftime("%B %d, %Y"),
                'message': f'Trial ends in {max(0, days_remaining)} days'
            }
        elif enrollment.status == 'active':
            days_remaining = (enrollment.access_expires_at - now).days if enrollment.access_expires_at else None
            return {
                'enrolled': True,
                'status': 'active',
                'access_expires_at': enrollment.access_expires_at.isoformat() if enrollment.access_expires_at else None,
                'days_remaining': max(0, days_remaining) if days_remaining else None,
                'message': f'Active subscription'
            }
        elif enrollment.status == 'payment_failed':
            return {
                'enrolled': True,
                'status': 'payment_failed',
                'message': '❌ Payment failed - please update your card'
            }
        else:
            return {
                'enrolled': True,
                'status': enrollment.status,
                'message': f'Status: {enrollment.status}'
            }
        
    except Exception as err:
        logger.error(f"[Enrollment-Status] Error: {str(err)}")
        raise HTTPException(status_code=500, detail=str(err))