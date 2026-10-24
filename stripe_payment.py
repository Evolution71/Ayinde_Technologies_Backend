"""
Stripe payment processing for Ayinde Technologies.

Backend env var: STRIPE_SECRET_KEY (sk_test_... or sk_live_...)
The publishable key (pk_...) goes in the frontend (REACT_APP_STRIPE_PUBLISHABLE_KEY).

Flows:
  - One-off purchase: the frontend creates a PaymentMethod (pm_...) and the backend
    charges it with charge_card().
  - Saved card for trial auto-charge: the backend creates a Stripe Customer and a
    SetupIntent; the frontend confirms the SetupIntent with Stripe.js and the backend
    stores the resulting payment method. charge_saved() charges it off-session later.
"""

import os
import logging
from typing import Dict, Tuple, Optional
import uuid as uuid_lib

import stripe

logger = logging.getLogger(__name__)

# Map Stripe error codes to the error_type values the rest of the app expects
STRIPE_ERROR_TYPES = {
    "card_declined": "CARD_DECLINED",
    "insufficient_funds": "INSUFFICIENT_FUNDS",
    "expired_card": "EXPIRED_CARD",
    "incorrect_cvc": "CVV_MISMATCH",
    "invalid_number": "INVALID_CARD",
    "incorrect_number": "INVALID_CARD",
}


class StripePaymentProcessor:
    """Charge cards and manage customers through Stripe."""

    def __init__(self):
        self.secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
        self.enabled = bool(self.secret_key)

        if self.enabled:
            stripe.api_key = self.secret_key
            mode = "live" if self.secret_key.startswith("sk_live_") else "test"
            logger.info(f"✅ Stripe payment processor initialized ({mode} mode)")
        else:
            logger.error("❌ STRIPE_SECRET_KEY not set. Payment processing disabled.")

    # ----- one-off purchases -------------------------------------------------

    def charge_card(
        self,
        source_id: str,               # Stripe PaymentMethod id (pm_...) sent from the frontend
        amount_cents: int,
        currency: str = "USD",
        description: str = "",
        idempotency_key: Optional[str] = None,
    ) -> Tuple[bool, Dict]:
        """Charge a PaymentMethod once. Returns (success, result_dict)."""
        if not self.enabled:
            return self._disabled()

        if not source_id or not source_id.startswith("pm_"):
            return False, {
                "success": False,
                "error_code": "INVALID_PAYMENT_METHOD",
                "error_type": "INVALID_CARD",
                "message": "Card details were not received. Please enter your card again.",
            }

        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount_cents),
                currency=currency.lower(),
                payment_method=source_id,
                confirm=True,
                payment_method_types=["card"],
                description=description or None,
                idempotency_key=idempotency_key or str(uuid_lib.uuid4()),
            )
        except Exception as e:
            return self._handle_error(e)

        return self._result(intent)

    def refund_payment(self, payment_intent_id: str, idempotency_key: Optional[str] = None) -> Tuple[bool, Dict]:
        """Refund a PaymentIntent in full. Returns (success, result_dict)."""
        if not self.enabled:
            return self._disabled()
        if not payment_intent_id or not payment_intent_id.startswith("pi_"):
            return False, {
                "success": False,
                "error_code": "NO_STRIPE_PAYMENT",
                "message": "This payment has no Stripe reference, so it cannot be refunded automatically.",
            }
        try:
            refund = stripe.Refund.create(
                payment_intent=payment_intent_id,
                idempotency_key=idempotency_key or str(uuid_lib.uuid4()),
            )
        except Exception as e:
            return self._handle_error(e)
        if refund.status in ("succeeded", "pending"):
            return True, {"success": True, "refund_id": refund.id, "status": refund.status}
        return False, {"success": False, "message": f"Stripe refund status: {refund.status}"}

    # ----- customers and saved cards ----------------------------------------

    def ensure_customer(self, email: str, name: str, user_id: int, existing_id: Optional[str] = None) -> str:
        """Return the Stripe customer id for this user, creating one if needed."""
        if existing_id:
            return existing_id
        customer = stripe.Customer.create(
            email=email,
            name=name or None,
            metadata={"user_id": str(user_id)},
            idempotency_key=f"customer-user-{user_id}",
        )
        return customer.id

    def create_setup_intent(self, customer_id: str) -> Dict:
        """Create a SetupIntent for saving a card for later off-session charges."""
        intent = stripe.SetupIntent.create(
            customer=customer_id,
            usage="off_session",
            payment_method_types=["card"],
        )
        return {"id": intent.id, "client_secret": intent.client_secret}

    def retrieve_setup_intent(self, setup_intent_id: str):
        return stripe.SetupIntent.retrieve(setup_intent_id)

    def charge_saved(
        self,
        customer_id: str,
        payment_method_id: str,
        amount_cents: int,
        currency: str = "USD",
        description: str = "",
        idempotency_key: Optional[str] = None,
    ) -> Tuple[bool, Dict]:
        """Charge a saved card without the customer present (trial auto-charge and retries)."""
        if not self.enabled:
            return self._disabled()
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount_cents),
                currency=currency.lower(),
                customer=customer_id,
                payment_method=payment_method_id,
                off_session=True,
                confirm=True,
                payment_method_types=["card"],
                description=description or None,
                idempotency_key=idempotency_key or str(uuid_lib.uuid4()),
            )
        except Exception as e:
            return self._handle_error(e)
        return self._result(intent)

    # ----- helpers -------------------------------------------------------------

    def _disabled(self) -> Tuple[bool, Dict]:
        return False, {
            "success": False,
            "error_code": "PAYMENT_PROCESSOR_DISABLED",
            "message": "Payment processing is not configured",
        }

    def _result(self, intent) -> Tuple[bool, Dict]:
        if intent.status == "succeeded":
            logger.info(f"✅ Payment successful: {intent.id}")
            return True, {
                "success": True,
                "payment_id": intent.id,
                "receipt_url": "",
                "amount": intent.amount,
                "currency": intent.currency,
                "status": intent.status,
            }

        # requires_action (3D Secure), requires_payment_method, etc. are not successes
        logger.warning(f"Payment not completed. Status: {intent.status}")
        return False, {
            "success": False,
            "error_code": "PAYMENT_INCOMPLETE",
            "error_type": "PAYMENT_FAILED",
            "message": "Payment was not completed. Please try another card or contact your bank.",
        }

    def _handle_error(self, e: Exception) -> Tuple[bool, Dict]:
        code = (getattr(e, "code", None) or "unknown_error").lower()
        user_message = getattr(e, "user_message", None)
        logger.error(f"Stripe error: {type(e).__name__} code={code} detail={str(e)}")

        if user_message:
            return False, {
                "success": False,
                "error_code": code.upper(),
                "error_type": STRIPE_ERROR_TYPES.get(code, "PAYMENT_FAILED"),
                "message": user_message,
            }

        return False, {
            "success": False,
            "error_code": "API_ERROR",
            "error_type": "API_ERROR",
            "message": "Payment service error. Please try again.",
        }


# Global payment processor instance
payment_processor = StripePaymentProcessor()
