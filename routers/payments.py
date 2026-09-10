from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

import models
import schemas
from database import get_db
from auth import get_current_user
import payments

router = APIRouter(prefix="/api/payments", tags=["payments"])

TRIAL_DAYS = 30


@router.post("/initiate", response_model=schemas.PaymentInitResponse)
def initiate_payment(
    payload: schemas.PaymentInitRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    course = db.query(models.Course).filter(models.Course.id == payload.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if not payments.payments_enabled():
        # This is the state the site is in until a real Flutterwave key is
        # added — a normal 200 response, not an error, so the frontend can
        # show a friendly message instead of breaking.
        return schemas.PaymentInitResponse(
            status="unavailable",
            message="Online payments aren't turned on yet — check back soon, or contact support@ayindetechnologies.com.",
        )

    tx_ref = payments.make_tx_ref(current_user.id, course.id)
    redirect_url = payload.redirect_url or "https://ayindetechnologies.com/payment-complete"

    ok, result = payments.create_payment_link(
        tx_ref=tx_ref,
        amount=course.price,
        currency=course.currency,
        customer_email=current_user.email,
        customer_name=current_user.name,
        redirect_url=redirect_url,
        title=f"Ayinde Technologies — {course.title}",
    )

    if not ok:
        return schemas.PaymentInitResponse(status="error", message=result)

    db.add(models.Payment(
        user_id=current_user.id, course_id=course.id, tx_ref=tx_ref,
        amount=course.price, currency=course.currency, status="pending",
    ))
    db.commit()

    return schemas.PaymentInitResponse(status="success", message="Redirecting to payment...", payment_link=result)


@router.post("/verify", response_model=schemas.PaymentVerifyResponse)
def verify_payment(
    payload: schemas.PaymentVerifyRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not payments.payments_enabled():
        return schemas.PaymentVerifyResponse(status="unavailable", message="Payments aren't configured yet.")

    ok, data = payments.verify_transaction(payload.transaction_id)
    if not ok:
        return schemas.PaymentVerifyResponse(status="error", message=str(data))

    tx_ref = data.get("tx_ref")
    payment = db.query(models.Payment).filter(models.Payment.tx_ref == tx_ref).first()
    if not payment:
        return schemas.PaymentVerifyResponse(status="error", message="No matching payment record found.")

    if data.get("status") != "successful":
        payment.status = "failed"
        db.commit()
        return schemas.PaymentVerifyResponse(status="error", message="Payment was not successful.")

    _mark_paid(db, payment, data)
    return schemas.PaymentVerifyResponse(status="success", message="Payment confirmed — course access unlocked.")


@router.post("/webhook")
async def flutterwave_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Flutterwave calls this directly (no user auth — it's not the user's
    browser). Authenticity is checked via the verif-hash header instead.
    Always returns 200 on a recognized-but-unmatched event, so Flutterwave
    doesn't keep retrying — only a bad signature gets rejected.
    """
    signature = request.headers.get("verif-hash", "")
    if not payments.verify_webhook_signature(signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    body = await request.json()
    data = body.get("data", {})
    tx_ref = data.get("tx_ref")
    status_value = data.get("status")

    payment = db.query(models.Payment).filter(models.Payment.tx_ref == tx_ref).first()
    if not payment:
        return {"status": "ignored", "reason": "unknown tx_ref"}

    if status_value == "successful":
        _mark_paid(db, payment, data)
    else:
        payment.status = "failed"
        db.commit()

    return {"status": "ok"}


def _mark_paid(db: Session, payment: models.Payment, flw_data: dict):
    payment.status = "successful"
    payment.flw_transaction_id = str(flw_data.get("id", ""))
    db.commit()

    enrollment = db.query(models.Enrollment).filter(
        models.Enrollment.user_id == payment.user_id,
        models.Enrollment.course_id == payment.course_id,
    ).first()
    if not enrollment:
        enrollment = models.Enrollment(
            user_id=payment.user_id, course_id=payment.course_id,
        )
        db.add(enrollment)

    enrollment.is_paid = True
    enrollment.last_tx_ref = payment.tx_ref
    enrollment.paid_at = datetime.utcnow()
    db.commit()
