"""
Stripe payment processing for Ayinde Technologies.

Drop-in replacement for square_payment.py. Exposes the same
payment_processor.charge_card(...) interface that routers/payments.py
and routers/services.py already call.

Backend env var: STRIPE_SECRET_KEY (sk_test_... or sk_live_...)
The publishable key (pk_...) goes in the frontend, not Railway.
"""

import os
import logging
from typing import Dict, Tuple, Optional
import uuid as uuid_lib

import stripe

logger = logging.getLogger(__name__)

# Map Stripe error codes to the error_type values the Square version returned
STRIPE_ERROR_TYPES = {
    "card_declined": "CARD_DECLINED",
    "insufficient_funds": "INSUFFICIENT_FUNDS",
    "expired_card": "EXPIRED_CARD",
    "incorrect_cvc": "CVV_MISMATCH",
    "invalid_number": "INVALID_CARD",
    "incorrect_number": "INVALID_CARD",
}


class StripePaymentProcessor:
    """Charge cards via Stripe PaymentIntents"""

    def __init__(self):
        self.secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
        self.enabled = bool(self.secret_key)

        if self.enabled:
            stripe.api_key = self.secret_key
            mode = "live" if self.secret_key.startswith("sk_live_") else "test"
            logger.info(f"✅ Stripe payment processor initialized ({mode} mode)")
        else:
            logger.error("❌ STRIPE_SECRET_KEY not set. Payment processing disabled.")

    def charge_card(
        self,
        source_id: str,               # Stripe PaymentMethod id (pm_...) sent from the frontend
        amount_cents: int,
        currency: str = "USD",
        description: str = "",
        idempotency_key: Optional[str] = None,
    ) -> Tuple[bool, Dict]:
        """
        Charge a card. Returns (success, result_dict) with the same keys
        the Square version returned, so callers don't change.
        """
        if not self.enabled:
            return False, {
                "success": False,
                "error_code": "PAYMENT_PROCESSOR_DISABLED",
                "message": "Payment processing is not configured",
            }

        if not idempotency_key:
            idempotency_key = str(uuid_lib.uuid4())

        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount_cents),
                currency=currency.lower(),
                payment_method=source_id,
                confirm=True,
                payment_method_types=["card"],
                description=description or None,
                idempotency_key=idempotency_key,
            )
        except Exception as e:
            return self._handle_error(e)

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

        # Anything else (requires_action for 3D Secure, requires_payment_method, etc.) is not a success
        logger.warning(f"Payment not completed. Status: {intent.status}")
        return False, {
            "success": False,
            "error_code": "PAYMENT_INCOMPLETE",
            "error_type": "PAYMENT_FAILED",
            "message": "Payment was not completed. Please try another card or contact your bank.",
        }

    def _handle_error(self, e: Exception) -> Tuple[bool, Dict]:
        # Check attributes rather than exception class names, so this works across stripe-python versions
        code = (getattr(e, "code", None) or "unknown_error").lower()
        user_message = getattr(e, "user_message", None)
        logger.error(f"Stripe error: {type(e).__name__} code={code} detail={str(e)}")

        if user_message:
            # Card errors carry a message that is safe to show the customer
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