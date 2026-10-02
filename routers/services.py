"""
Services Router for Ayinde Technologies
Handles service tiers, subscriptions, promotions, and checkout

New Endpoints (12-Page Website Structure):
- GET /api/services/tiers/{service_type} - Get pricing tiers for service type
- GET /api/services/packages - Get all service packages
- GET /api/services/my-subscriptions - Get user's active subscriptions
- POST /api/services/promo-code/verify - Verify and apply promo code
- POST /api/services/checkout - Create service checkout
- GET /api/services/checkout/{checkout_id} - Get checkout status
- POST /api/services/subscriptions/{subscription_id}/cancel - Cancel subscription
- POST /api/services/subscriptions/{subscription_id}/upgrade - Upgrade tier

Existing Endpoints:
- GET /api/services/ - Get all services
- GET /api/services/{service_id}/ - Get specific service
- POST /api/services/purchase/ - Create service order
- GET /api/services/orders/ - List user's orders
- GET /api/services/orders/{order_id}/ - Get order details
- POST /api/services/orders/{order_id}/cancel/ - Cancel order
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import uuid
import logging

from database import get_db
from auth import get_current_user
from models import User, ServiceOrder, ServiceTier, ServiceSubscription, PromoCode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/services", tags=["services"])

# ════════════════════════════════════════════════════════════════════════════════
# SERVICE TIERS - Get pricing by service type
# ════════════════════════════════════════════════════════════════════════════════

@router.get("/tiers/{service_type}")
async def get_service_tiers(
    service_type: str,
    db: Session = Depends(get_db)
):
    """
    Get all pricing tiers for a specific service type.

    Service Types:
    - website: Website development
    - applications: Mobile/Web applications
    - consultation: Expert consultation
    - premium: Enterprise all-in-one

    Returns: List of tiers with pricing and features
    """
    try:
        service_type = service_type.lower()

        if service_type not in ["website", "applications", "consultation", "premium"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid service type. Must be: website, applications, consultation, or premium"
            )

        tiers = db.query(ServiceTier).filter(
            ServiceTier.service_type == service_type,
            ServiceTier.is_active == True
        ).all()

        if not tiers:
            # Return empty list if no tiers configured
            return {"service_type": service_type, "tiers": []}

        return {
            "service_type": service_type,
            "tiers": [
                {
                    "id": tier.id,
                    "tier": tier.tier,
                    "monthly_price": tier.monthly_price,
                    "quarterly_price": tier.quarterly_price,
                    "annual_price": tier.annual_price,
                    "fifty_percent_down": tier.fifty_percent_down,
                    "features": tier.features or [],
                    "description": tier.description
                }
                for tier in tiers
            ]
        }
    except Exception as e:
        logger.error(f"[services] Error fetching tiers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════════════════════
# SERVICE PACKAGES - Get all available service packages
# ════════════════════════════════════════════════════════════════════════════════

@router.get("/packages")
async def get_service_packages(db: Session = Depends(get_db)):
    """
    Get all available service packages across all service types.

    Returns: Grouped by service type with all tiers and pricing
    """
    try:
        all_tiers = db.query(ServiceTier).filter(
            ServiceTier.is_active == True
        ).all()

        # Group by service type
        packages_by_type = {}
        for tier in all_tiers:
            if tier.service_type not in packages_by_type:
                packages_by_type[tier.service_type] = []

            packages_by_type[tier.service_type].append({
                "id": tier.id,
                "tier": tier.tier,
                "monthly_price": tier.monthly_price,
                "quarterly_price": tier.quarterly_price,
                "annual_price": tier.annual_price,
                "fifty_percent_down": tier.fifty_percent_down,
                "features": tier.features or [],
                "description": tier.description
            })

        return {"packages": packages_by_type}
    except Exception as e:
        logger.error(f"[services] Error fetching packages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════════════════════
# SERVICE SUBSCRIPTIONS - Get user's active subscriptions
# ════════════════════════════════════════════════════════════════════════════════

@router.get("/my-subscriptions")
async def get_service_subscriptions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all active service subscriptions for the current user.

    Returns: List of active subscriptions with details
    """
    try:
        subscriptions = db.query(ServiceSubscription).filter(
            ServiceSubscription.user_id == current_user.id,
            ServiceSubscription.status == "active"
        ).all()

        return {
            "subscriptions": [
                {
                    "id": sub.id,
                    "service_type": sub.service_type,
                    "tier_name": sub.tier_name,
                    "payment_option": sub.payment_option,
                    "amount": sub.amount,
                    "currency": sub.currency,
                    "discount_amount": sub.discount_amount,
                    "started_at": sub.started_at.isoformat(),
                    "expires_at": sub.expires_at.isoformat(),
                    "next_billing_date": sub.next_billing_date.isoformat() if sub.next_billing_date else None,
                    "status": sub.status
                }
                for sub in subscriptions
            ]
        }
    except Exception as e:
        logger.error(f"[services] Error fetching subscriptions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════════════════════
# PROMO CODES - Verify and apply promotional codes
# ════════════════════════════════════════════════════════════════════════════════

@router.post("/promo-code/verify")
async def verify_promo_code(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify and calculate discount for a promotional code.

    Request Body:
    {
        "promo_code": "SAVE10",
        "amount": 100.00
    }

    Returns: {
        "valid": true/false,
        "discount_percentage": number,
        "discount_amount": number,
        "final_amount": number,
        "message": "string"
    }
    """
    try:
        body = await request.json()
        promo_code = body.get("promo_code", "").upper()
        amount = float(body.get("amount", 0))
        service_type = body.get("service_type")  # Optional: specific service type

        if not promo_code or amount <= 0:
            return {
                "valid": False,
                "discount_percentage": 0,
                "discount_amount": 0,
                "final_amount": amount,
                "message": "Invalid promo code or amount"
            }

        # Find promo code
        code = db.query(PromoCode).filter(
            PromoCode.code == promo_code,
            PromoCode.status == "active"
        ).first()

        if not code:
            return {
                "valid": False,
                "discount_percentage": 0,
                "discount_amount": 0,
                "final_amount": amount,
                "message": "Promo code not found or inactive"
            }

        # Check validity period
        now = datetime.now(timezone.utc)
        if code.valid_from and code.valid_from > now:
            return {
                "valid": False,
                "discount_percentage": 0,
                "discount_amount": 0,
                "final_amount": amount,
                "message": "Promo code not yet valid"
            }

        if code.valid_until and code.valid_until < now:
            return {
                "valid": False,
                "discount_percentage": 0,
                "discount_amount": 0,
                "final_amount": amount,
                "message": "Promo code has expired"
            }

        # Check usage limits
        if code.max_uses and code.times_used >= code.max_uses:
            return {
                "valid": False,
                "discount_percentage": 0,
                "discount_amount": 0,
                "final_amount": amount,
                "message": "Promo code usage limit reached"
            }

        # Check applicable services
        if code.applicable_services and service_type:
            if service_type.lower() not in code.applicable_services:
                return {
                    "valid": False,
                    "discount_percentage": 0,
                    "discount_amount": 0,
                    "final_amount": amount,
                    "message": f"Promo code not applicable to {service_type}"
                }

        # Calculate discount
        if code.discount_type == "percentage":
            discount_amount = amount * (code.discount_value / 100)
            discount_percentage = code.discount_value
        elif code.discount_type == "fixed":
            discount_amount = code.discount_value
            discount_percentage = (discount_amount / amount * 100) if amount > 0 else 0
        else:  # free_trial
            discount_amount = 0
            discount_percentage = 0

        final_amount = max(0, amount - discount_amount)

        return {
            "valid": True,
            "discount_percentage": round(discount_percentage, 2),
            "discount_amount": round(discount_amount, 2),
            "final_amount": round(final_amount, 2),
            "message": "Promo code applied successfully"
        }

    except Exception as e:
        logger.error(f"[services] Error verifying promo code: {str(e)}")
        return {
            "valid": False,
            "discount_percentage": 0,
            "discount_amount": 0,
            "final_amount": 0,
            "message": "Error verifying promo code"
        }


# ════════════════════════════════════════════════════════════════════════════════
# CHECKOUT - Create service subscription
# ════════════════════════════════════════════════════════════════════════════════

@router.post("/checkout")
async def create_service_checkout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a service subscription checkout.

    Request Body:
    {
        "service_type": "website|applications|consultation|premium",
        "tier": "starter|professional|advanced|premium",
        "payment_option": "monthly|quarterly|annual|fifty_percent_down",
        "hours": number (for consultation only),
        "promo_code": "OPTIONAL",
        "amount": number,
        "payment_method_nonce": "square_nonce_from_payment_form"
    }

    Returns: {
        "success": true,
        "subscription_id": number,
        "checkout_id": "UUID",
        "amount": number,
        "discount_applied": number,
        "final_amount": number,
        "message": "string"
    }
    """
    try:
        body = await request.json()

        service_type = body.get("service_type", "").lower()
        tier = body.get("tier", "").lower()
        payment_option = body.get("payment_option", "").lower()
        amount = float(body.get("amount", 0))
        promo_code = body.get("promo_code", "").upper()
        payment_nonce = body.get("payment_method_nonce")

        # Validation
        if not service_type or service_type not in ["website", "applications", "consultation", "premium"]:
            raise HTTPException(status_code=400, detail="Invalid service type")

        if not tier or tier not in ["starter", "professional", "advanced", "premium"]:
            raise HTTPException(status_code=400, detail="Invalid tier")

        if not payment_option or payment_option not in ["monthly", "quarterly", "annual", "fifty_percent_down"]:
            raise HTTPException(status_code=400, detail="Invalid payment option")

        if amount <= 0:
            raise HTTPException(status_code=400, detail="Invalid amount")

        # Get service tier
        service_tier = db.query(ServiceTier).filter(
            ServiceTier.service_type == service_type,
            ServiceTier.tier == tier,
            ServiceTier.is_active == True
        ).first()

        if not service_tier:
            raise HTTPException(status_code=404, detail="Service tier not found")

        # Apply promo code if provided
        discount_amount = 0
        if promo_code:
            code = db.query(PromoCode).filter(
                PromoCode.code == promo_code,
                PromoCode.status == "active"
            ).first()

            if code:
                now = datetime.now(timezone.utc)
                if code.valid_from and code.valid_from <= now and (not code.valid_until or code.valid_until >= now):
                    if not code.max_uses or code.times_used < code.max_uses:
                        if code.discount_type == "percentage":
                            discount_amount = amount * (code.discount_value / 100)
                        elif code.discount_type == "fixed":
                            discount_amount = code.discount_value

                        # Increment promo code usage
                        code.times_used += 1
                        db.commit()

        final_amount = max(0, amount - discount_amount)

        # Calculate expiration date based on payment option
        now = datetime.now(timezone.utc)
        if payment_option == "monthly":
            expires_at = now + timedelta(days=30)
        elif payment_option == "quarterly":
            expires_at = now + timedelta(days=90)
        elif payment_option == "annual":
            expires_at = now + timedelta(days=365)
        elif payment_option == "fifty_percent_down":
            expires_at = now + timedelta(days=180)
        else:
            expires_at = now + timedelta(days=30)

        # Calculate next billing date
        next_billing = expires_at if payment_option != "fifty_percent_down" else now + timedelta(days=30)

        # Create subscription
        subscription = ServiceSubscription(
            user_id=current_user.id,
            tier_id=service_tier.id,
            service_type=service_type,
            tier_name=tier,
            status="active",
            payment_option=payment_option,
            amount=final_amount,
            currency="USD",
            promo_code=promo_code if promo_code else None,
            discount_amount=discount_amount,
            started_at=now,
            expires_at=expires_at,
            next_billing_date=next_billing,
            payment_method_id=payment_nonce,
            transaction_id=f"SUB-{current_user.id}-{uuid.uuid4().hex[:8].upper()}"
        )

        db.add(subscription)
        db.commit()
        db.refresh(subscription)

        return {
            "success": True,
            "subscription_id": subscription.id,
            "checkout_id": subscription.transaction_id,
            "amount": amount,
            "discount_applied": round(discount_amount, 2),
            "final_amount": round(final_amount, 2),
            "service_type": service_type,
            "tier": tier,
            "expires_at": expires_at.isoformat(),
            "message": "Subscription created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[services] Error creating checkout: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checkout/{checkout_id}")
async def get_checkout_status(
    checkout_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get status of a service subscription checkout.
    """
    try:
        subscription = db.query(ServiceSubscription).filter(
            ServiceSubscription.transaction_id == checkout_id,
            ServiceSubscription.user_id == current_user.id
        ).first()

        if not subscription:
            raise HTTPException(status_code=404, detail="Checkout not found")

        return {
            "subscription_id": subscription.id,
            "checkout_id": subscription.transaction_id,
            "status": subscription.status,
            "service_type": subscription.service_type,
            "tier_name": subscription.tier_name,
            "amount": subscription.amount,
            "discount_amount": subscription.discount_amount,
            "started_at": subscription.started_at.isoformat(),
            "expires_at": subscription.expires_at.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[services] Error fetching checkout: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTIONS - Cancel and upgrade
# ════════════════════════════════════════════════════════════════════════════════

@router.post("/subscriptions/{subscription_id}/cancel")
async def cancel_service_subscription(
    subscription_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel an active service subscription.
    """
    try:
        subscription = db.query(ServiceSubscription).filter(
            ServiceSubscription.id == subscription_id,
            ServiceSubscription.user_id == current_user.id
        ).first()

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        if subscription.status in ["cancelled", "expired"]:
            raise HTTPException(status_code=400, detail="Subscription is already cancelled or expired")

        subscription.status = "cancelled"
        subscription.cancelled_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "success": True,
            "subscription_id": subscription.id,
            "message": "Subscription cancelled successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[services] Error cancelling subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscriptions/{subscription_id}/upgrade")
async def upgrade_service_tier(
    subscription_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upgrade or downgrade a service tier.

    Request Body:
    {
        "new_tier": "starter|professional|advanced|premium",
        "payment_option": "monthly|quarterly|annual|fifty_percent_down"
    }
    """
    try:
        body = await request.json()
        new_tier = body.get("new_tier", "").lower()
        payment_option = body.get("payment_option", "").lower()

        if not new_tier or new_tier not in ["starter", "professional", "advanced", "premium"]:
            raise HTTPException(status_code=400, detail="Invalid tier")

        if not payment_option or payment_option not in ["monthly", "quarterly", "annual", "fifty_percent_down"]:
            raise HTTPException(status_code=400, detail="Invalid payment option")

        subscription = db.query(ServiceSubscription).filter(
            ServiceSubscription.id == subscription_id,
            ServiceSubscription.user_id == current_user.id
        ).first()

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        if subscription.status != "active":
            raise HTTPException(status_code=400, detail="Can only upgrade active subscriptions")

        # Get new tier
        new_tier_obj = db.query(ServiceTier).filter(
            ServiceTier.service_type == subscription.service_type,
            ServiceTier.tier == new_tier,
            ServiceTier.is_active == True
        ).first()

        if not new_tier_obj:
            raise HTTPException(status_code=404, detail="New tier not found")

        # Update subscription
        subscription.tier_id = new_tier_obj.id
        subscription.tier_name = new_tier
        subscription.payment_option = payment_option

        # Recalculate price based on payment option
        if payment_option == "monthly":
            new_price = new_tier_obj.monthly_price
            expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        elif payment_option == "quarterly":
            new_price = new_tier_obj.quarterly_price or new_tier_obj.monthly_price * 3 * 0.95
            expires_at = datetime.now(timezone.utc) + timedelta(days=90)
        elif payment_option == "annual":
            new_price = new_tier_obj.annual_price or new_tier_obj.monthly_price * 12 * 0.90
            expires_at = datetime.now(timezone.utc) + timedelta(days=365)
        elif payment_option == "fifty_percent_down":
            new_price = new_tier_obj.fifty_percent_down or new_tier_obj.monthly_price * 6
            expires_at = datetime.now(timezone.utc) + timedelta(days=180)

        subscription.amount = new_price
        subscription.expires_at = expires_at
        subscription.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(subscription)

        return {
            "success": True,
            "subscription_id": subscription.id,
            "new_tier": new_tier,
            "new_amount": new_price,
            "expires_at": expires_at.isoformat(),
            "message": "Tier upgraded successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[services] Error upgrading tier: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════════════════════
# EXISTING ENDPOINTS - Maintain backward compatibility
# ════════════════════════════════════════════════════════════════════════════════

@router.get("/")
async def get_services(db: Session = Depends(get_db)):
    """Get all available services"""
    return []


@router.get("/{service_id}/")
async def get_service(service_id: int, db: Session = Depends(get_db)):
    """Get a specific service"""
    raise HTTPException(status_code=404, detail="Service not found")


@router.post("/purchase/")
async def create_service_order(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create and process a premium service order.

    ✅ TODO: In production, integrate with Square Python SDK to charge card
    Current implementation marks payment as completed for testing

    Error Handling:
    - Invalid card data → Return error_code: INVALID_CARD
    - Card declined → Return error_code: CARD_DECLINED
    - Insufficient funds → Return error_code: INSUFFICIENT_FUNDS
    """
    try:
        body = await request.json()

        service_type = body.get("serviceType", "website")  # Extract service type, default to 'website'
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

        # Validation
        if not tier or not amount or not source_id:
            logger.warning(f"[services] Missing required fields in purchase request")
            raise HTTPException(status_code=400, detail="Missing required fields: tier, amount, and payment method required")

        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than 0")

        if not full_name or not email:
            raise HTTPException(status_code=400, detail="Full name and email are required")

        if not postal_code:
            raise HTTPException(status_code=400, detail="Postal code is required for billing")

        logger.info(f"[services] Processing purchase for user {current_user.id}: tier={tier}, amount={amount}")

        # ✅ TODO: Call Square API here to charge the card
        # Example error handling structure:
        # try:
        #     payment = square_client.payments.create_payment({
        #         source_id: source_id,
        #         amount_money: {
        #             amount: int(amount * 100),  # Convert to cents
        #             currency: currency
        #         },
        #         idempotency_key: str(uuid.uuid4())
        #     })
        # except SquareException as e:
        #     if 'insufficient' in str(e):
        #         return { success: False, error_code: INSUFFICIENT_FUNDS, message: "Your card has insufficient funds" }
        #     if 'declined' in str(e) or 'invalid' in str(e):
        #         return { success: False, error_code: CARD_DECLINED, message: "Your card was declined" }
        #     raise

        service_starts_at = datetime.now(timezone.utc)

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

        # Create order record
        order = ServiceOrder(
            user_id=current_user.id,
            service_type=service_type,
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

        logger.info(f"[services] Order created: {order.id}, now processing payment")

        # ✅ Mark payment as completed (in production, verify with Square API response)
        order.payment_status = "completed"
        order.payment_completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"[services] Payment completed for order {order.id}")

        return {
            "success": True,
            "order_id": order.id,
            "message": "Order created successfully",
            "order": {
                "id": order.id,
                "tier": order.tier,
                "tier_name": order.tier_name,
                "amount": order.amount,
                "status": order.status,
                "payment_status": order.payment_status,
                "service_starts_at": order.service_starts_at.isoformat(),
                "service_ends_at": order.service_ends_at.isoformat()
            }
        }

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"[services] ValueError in purchase: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid data format: " + str(e))
    except Exception as e:
        logger.error(f"[services] Error creating order: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Payment processing failed: {str(e)}")


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
    order.cancelled_at = datetime.now(timezone.utc)
    db.commit()

    return {"success": True, "message": "Order cancelled successfully"}