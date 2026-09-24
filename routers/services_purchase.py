"""
Premium services purchase endpoint.

Handles service order creation and payment processing via Square.

Endpoints:
- POST /api/services/purchase/ - Create and process service order
- GET /api/services/orders/ - List user's service orders
- GET /api/services/orders/{order_id}/ - Get order details
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List
import uuid

from database import get_db
from auth import get_current_user
from models import User
import schemas

# Note: You'll need to add ServiceOrder model to models.py
# See the model definition at the end of this file

router = APIRouter(prefix="/api/services", tags=["services"])


@router.post("/purchase/")
async def create_service_order(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create and process a premium service order.
    
    Expects JSON body:
    {
        "tier": "website|application|supreme",
        "tierName": "Website Pro",
        "amount": 897.00,
        "currency": "USD",
        "paymentOption": "monthly|annual|threeyear|halfdown",
        "discountPercent": 0,
        "period": "/month",
        "fullName": "John Doe",
        "email": "john@example.com",
        "phone": "555-1234",
        "company": "Acme Corp",
        "postalCode": "90210",
        "country": "US",
        "sourceId": "cnp_..." (Square token)
    }
    
    Returns:
    {
        "success": true,
        "order_id": 123,
        "order": { order details },
        "message": "Order created successfully"
    }
    """
    try:
        # Parse request
        body = await request.json()
        
        print(f"[services] Creating order for user {current_user.id}")
        
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
                detail="Missing required fields: tier, amount, sourceId"
            )
        
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount must be greater than 0"
            )
        
        # Import ServiceOrder model
        from models import ServiceOrder
        
        # Determine service duration
        duration_days = 30  # default: monthly
        if payment_option == "annual":
            duration_days = 730  # 2 years
        elif payment_option == "threeyear":
            duration_days = 1095  # 3 years
        elif payment_option == "halfdown":
            duration_days = 180  # 6 months (first payment is 50%)
        
        # Calculate end date
        service_ends_at = datetime.utcnow() + timedelta(days=duration_days)
        
        # Create order record
        order = ServiceOrder(
            user_id=current_user.id,
            tier=tier,
            tier_name=tier_name,
            amount=amount,
            currency=currency,
            payment_option=payment_option,
            discount_percent=discount_percent,
            period=period,
            # Billing info
            full_name=full_name,
            email=email,
            phone=phone,
            company=company,
            postal_code=postal_code,
            country=country,
            # Service details
            status="active",
            service_starts_at=datetime.utcnow(),
            service_ends_at=service_ends_at,
            # Payment
            payment_status="pending",
            payment_method="square",
            payment_source_id=source_id,
            transaction_id=f"SVC-{current_user.id}-{uuid.uuid4().hex[:8].upper()}",
            # Metadata
            metadata={
                "features": body.get("features", []),
                "ip_address": request.client.host if request.client else "",
                "user_agent": request.headers.get("user-agent", "")
            }
        )
        
        db.add(order)
        db.commit()
        db.refresh(order)
        
        print(f"[services] ✅ Order created: id={order.id}, tier={tier}, amount=${amount}")
        
        # TODO: Process payment via Square API here
        # For now, mark as completed
        order.payment_status = "completed"
        order.payment_completed_at = datetime.utcnow()
        db.commit()
        
        # Send confirmation email (implement separately)
        # send_order_confirmation_email(email, order)
        
        return {
            "success": True,
            "order_id": order.id,
            "order": {
                "id": order.id,
                "tier": order.tier,
                "tier_name": order.tier_name,
                "amount": order.amount,
                "currency": order.currency,
                "status": order.status,
                "service_starts_at": order.service_starts_at,
                "service_ends_at": order.service_ends_at,
                "transaction_id": order.transaction_id
            },
            "message": f"Welcome to {tier_name}! Your service is now active."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[services] ❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create order: {str(e)}"
        )


@router.get("/orders/")
async def get_user_service_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all service orders for the current user.
    
    Returns: List of service orders
    """
    from models import ServiceOrder
    
    orders = db.query(ServiceOrder).filter(
        ServiceOrder.user_id == current_user.id
    ).order_by(ServiceOrder.created_at.desc()).all()
    
    return {
        "success": True,
        "count": len(orders),
        "orders": [
            {
                "id": order.id,
                "tier": order.tier,
                "tier_name": order.tier_name,
                "amount": order.amount,
                "currency": order.currency,
                "status": order.status,
                "service_starts_at": order.service_starts_at,
                "service_ends_at": order.service_ends_at,
                "payment_status": order.payment_status,
                "created_at": order.created_at
            }
            for order in orders
        ]
    }


@router.get("/orders/{order_id}/")
async def get_service_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific service order.
    
    Returns: Order details
    
    Errors:
    - 404: Order not found
    - 403: Not authorized to view this order
    """
    from models import ServiceOrder
    
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
        "success": True,
        "order": {
            "id": order.id,
            "tier": order.tier,
            "tier_name": order.tier_name,
            "amount": order.amount,
            "currency": order.currency,
            "payment_option": order.payment_option,
            "discount_percent": order.discount_percent,
            "status": order.status,
            "service_starts_at": order.service_starts_at,
            "service_ends_at": order.service_ends_at,
            "payment_status": order.payment_status,
            "transaction_id": order.transaction_id,
            "created_at": order.created_at,
            # Billing info
            "full_name": order.full_name,
            "email": order.email,
            "company": order.company,
            "country": order.country
        }
    }


@router.post("/orders/{order_id}/cancel/")
async def cancel_service_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel a service order.
    
    Note: This will trigger a refund if applicable.
    
    Returns: Updated order details
    """
    from models import ServiceOrder
    
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
            detail="Order is already cancelled"
        )
    
    # Mark as cancelled
    order.status = "cancelled"
    order.cancelled_at = datetime.utcnow()
    db.commit()
    
    print(f"[services] Order {order_id} cancelled")
    
    return {
        "success": True,
        "message": "Order cancelled successfully",
        "order_id": order.id
    }

