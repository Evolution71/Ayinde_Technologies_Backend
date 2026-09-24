from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

from database import get_db
from auth import get_current_user
from models import User, Service, ServiceOrder

router = APIRouter(prefix="/api/services", tags=["services"])


# GET all services - NO AUTH REQUIRED
@router.get("/")
async def get_services(db: Session = Depends(get_db)):
    """Get all available services"""
    services = db.query(Service).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "icon": s.icon,
            "created_at": s.created_at.isoformat() if s.created_at else None
        }
        for s in services
    ]


# GET single service - NO AUTH REQUIRED
@router.get("/{service_id}/")
async def get_service(service_id: int, db: Session = Depends(get_db)):
    """Get a specific service"""
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return {
        "id": service.id,
        "name": service.name,
        "description": service.description,
        "icon": service.icon,
        "created_at": service.created_at.isoformat() if service.created_at else None
    }


# POST purchase - AUTH REQUIRED
@router.post("/purchase/")
async def create_service_order(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create and process a premium service order"""
    try:
        body = await request.json()
        
        tier = body.get("tier")
        tier_name = body.get("tierName")
        amount = float(body.get("amount", 0))
        currency = body.get("currency", "USD")
        payment_option = body.get("paymentOption")
        discount_percent = int(body.get("discountPercent", 0))
        period = body.get("period")
        source_id = body.get("sourceId")
        
        full_name = body.get("fullName")
        email = body.get("email")
        phone = body.get("phone", "")
        company = body.get("company", "")
        postal_code = body.get("postalCode")
        country = body.get("country", "US")
        
        if not tier or not amount or not source_id:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than 0")
        
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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=404, detail="Order not found")
    
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
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status == "cancelled":
        raise HTTPException(status_code=400, detail="Order already cancelled")
    
    order.status = "cancelled"
    order.cancelled_at = datetime.utcnow()
    db.commit()
    
    return {"success": True, "message": "Order cancelled successfully"}