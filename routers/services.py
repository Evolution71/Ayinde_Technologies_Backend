from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

from database import get_db
from auth import get_current_user
from models import User, ServiceOrder

router = APIRouter(prefix="/api/services", tags=["services"])


@router.post("/purchase/")
async def create_service_order(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create and process a premium service orders"""
    try:
        body = await request.json()
        
        # Extract fields
        tier = body.get("tier")
        tier_name = body.get("tierName")
        amount = float(body.get("amount", 0))
        currency = body.get("currency", "USD")
        payment_option = body.get("paymentOption")
        discount_percent = int(body.get("discountPercent", 0))
        period = body.get("period")
        source_id = body.get("sourceId")
        
        # Billing info
        full_name = body.get("fullName")
        email = body.get("email")
        phone = body.get("phone", "")
        company = body.get("company", "")
        postal_code = body.get("postalCode")
        country = body.get("country", "US")
        
        # Validate
        if not tier or not amount or not source_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields"
            )
        
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount must be greater than 0"
            )
        
        # Calculate service end date based on payment option
        service_starts_at = datetime.utcnow()
        
        if payment_option == "monthly":
            service_ends_at = service_starts_at + timedelta(days=30)
        elif payment_option == "annual" or payment_option == "twoyear":
            service_ends_at = service_starts_at + timedelta(days=730)
        elif payment_option == "threeyear":
            service_ends_at = service_starts_at + timedelta(days=1095)
        elif payment_option == "halfdown":
            service_ends_at = service_starts_at + timedelta(days=180)
        else:
            service_ends_at = service_starts_at + timedelta(days=30)
        
        # Create order
        order = ServiceOrder(
            user_id=current_user.id,
            tier=tier,
            tier_name=tier_name,
            amount=amount,
            currency=currency,
            payment_option=payment_option,
            discount_percent=discount_percent,
            period=period,
            full_name=full_name,
            email=email,
            phone=phone,
            company=company,
            postal_code=postal_code,
            country=country,
            status="active",
            service_starts_at=service_starts_at,
            service_ends_at=service_ends_at,
            payment_status="pending",
            payment_method="square",
            payment_source_id=source_id,
            transaction_id=f"SVC-{current_user.id}-{uuid.uuid4().hex[:8].upper()}",
            order_metadata={
                "features": body.get("features", []),
                "ip_address": request.client.host if request.client else "",
                "user_agent": request.headers.get("user-agent", "")
            }
        )
        
        db.add(order)
        db.commit()
        db.refresh(order)
        
        # TODO: Process payment via Square API
        # For now, mark as completed
        order.payment_status = "completed"
        order.payment_completed_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "order_id": order.id,
            "message": "Order created successfully",
            "order": {
                "id": order.id,
                "tier": order.tier,
                "amount": order.amount,
                "status": order.status,
                "service_starts_at": order.service_starts_at.isoformat(),
                "service_ends_at": order.service_ends_at.isoformat()
            }
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/orders/")
async def list_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's service orders"""
    orders = db.query(ServiceOrder).filter(
        ServiceOrder.user_id == current_user.id
    ).order_by(ServiceOrder.created_at.desc()).all()
    
    return {
        "orders": [
            {
                "id": o.id,
                "tier": o.tier,
                "tier_name": o.tier_name,
                "amount": o.amount,
                "status": o.status,
                "service_starts_at": o.service_starts_at.isoformat(),
                "service_ends_at": o.service_ends_at.isoformat(),
                "payment_status": o.payment_status
            }
            for o in orders
        ]
    }


@router.get("/orders/{order_id}/")
async def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get order details"""
    order = db.query(ServiceOrder).filter(
        ServiceOrder.id == order_id,
        ServiceOrder.user_id == current_user.id
    ).first()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    return {
        "id": order.id,
        "tier": order.tier,
        "tier_name": order.tier_name,
        "amount": order.amount,
        "status": order.status,
        "service_starts_at": order.service_starts_at.isoformat(),
        "service_ends_at": order.service_ends_at.isoformat(),
        "payment_status": order.payment_status,
        "full_name": order.full_name,
        "email": order.email,
        "company": order.company
    }


@router.post("/orders/{order_id}/cancel/")
async def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a service order"""
    order = db.query(ServiceOrder).filter(
        ServiceOrder.id == order_id,
        ServiceOrder.user_id == current_user.id
    ).first()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    if order.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order already cancelled"
        )
    
    order.status = "cancelled"
    order.cancelled_at = datetime.utcnow()
    db.commit()
    
    return {
        "success": True,
        "message": "Order cancelled successfully"
    }