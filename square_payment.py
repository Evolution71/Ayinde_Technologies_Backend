"""
Square Payment Processing
Handles payment charging via Square API
"""

import os
import logging
from typing import Dict, Tuple, Optional
import uuid as uuid_lib

logger = logging.getLogger(__name__)

# Try to import squareup SDK
try:
    from squareup.client import Client
    from squareup.exceptions.api_exception import APIException
    SQUARE_SDK_AVAILABLE = True
except ImportError:
    SQUARE_SDK_AVAILABLE = False
    logger.warning("⚠️ squareup SDK not installed. Install withs: pip install squareup")


class SquarePaymentProcessor:
    """Process payments via Square API"""

    def __init__(self):
        self.square_api_key = os.getenv("SQUARE_ACCESS_TOKEN", "")
        self.square_environment = os.getenv("SQUARE_ENVIRONMENT", "sandbox")
        self.enabled = bool(self.square_api_key and SQUARE_SDK_AVAILABLE)

        if self.enabled:
            self.client = Client(
                access_token=self.square_api_key,
                environment=self.square_environment
            )
            self.payments_api = self.client.payments
            logger.info(f"✅ Square payment processor initialized ({self.square_environment} mode)")
        elif SQUARE_SDK_AVAILABLE:
            logger.warning("⚠️ Square API key not configured. Set SQUARE_ACCESS_TOKEN environment variable.")
        else:
            logger.warning("⚠️ Square SDK not installed. Payment processing disabled.")

    def charge_card(
        self,
        source_id: str,
        amount_cents: int,
        currency: str = "USD",
        description: str = "",
        idempotency_key: Optional[str] = None
    ) -> Tuple[bool, Dict]:
        """
        Charge a card via Square API

        Returns: (success: bool, response: dict)
        """

        if not self.enabled:
            return False, {
                "success": False,
                "error_code": "PAYMENT_PROCESSOR_DISABLED",
                "message": "Payment processing is not configured"
            }

        try:
            if not idempotency_key:
                idempotency_key = str(uuid_lib.uuid4())

            # Build payment request
            body = {
                "source_id": source_id,
                "amount_money": {
                    "amount": int(amount_cents),  # Amount in cents
                    "currency": currency
                },
                "idempotency_key": idempotency_key,
                "autocomplete": True
            }

            if description:
                body["reference_id"] = description

            # Call Square API
            result = self.payments_api.create_payment(body)

            if result.is_success():
                payment = result.result
                logger.info(f"✅ Payment successful: {payment['id']}")

                return True, {
                    "success": True,
                    "payment_id": payment["id"],
                    "receipt_url": payment.get("receipt_url", ""),
                    "amount": payment["amount_money"]["amount"],
                    "currency": payment["amount_money"]["currency"],
                    "status": payment["status"]
                }

            elif result.is_api_error():
                error = result.errors[0] if result.errors else {}
                error_code = error.get("code", "UNKNOWN_ERROR")
                error_detail = error.get("detail", "")

                logger.error(f"Square API Error: {error_code} - {error_detail}")

                # Map Square errors to user-friendly messages
                error_message, error_type = self._map_square_error(error_code, error_detail)

                return False, {
                    "success": False,
                    "error_code": error_code,
                    "error_type": error_type,
                    "message": error_message
                }

            else:
                logger.error(f"Square API returned unexpected response: {result}")
                return False, {
                    "success": False,
                    "error_code": "UNKNOWN_ERROR",
                    "message": "Payment processing failed. Please try again."
                }

        except APIException as e:
            logger.error(f"Square API Exception: {str(e)}")
            return False, {
                "success": False,
                "error_code": "API_ERROR",
                "message": "Payment service error. Please try again."
            }

        except Exception as e:
            logger.error(f"Unexpected error during payment: {str(e)}")
            return False, {
                "success": False,
                "error_code": "SYSTEM_ERROR",
                "message": f"Payment processing failed: {str(e)}"
            }

    def _map_square_error(self, error_code: str, error_detail: str) -> Tuple[str, str]:
        """Map Square error codes to user-friendly messages"""

        error_code_lower = error_code.lower()
        detail_lower = error_detail.lower()

        # Insufficient funds
        if "insufficient" in error_code_lower or "insufficient" in detail_lower:
            return (
                "❌ Insufficient funds on your card. Please check your account balance or use a different card.",
                "INSUFFICIENT_FUNDS"
            )

        # Card declined
        if "declined" in error_code_lower or "declined" in detail_lower:
            return (
                "❌ Your card was declined. Please check your card details or try a different card.",
                "CARD_DECLINED"
            )

        # Invalid card
        if "invalid" in error_code_lower or "invalid" in detail_lower:
            return (
                "❌ Invalid card details. Please check your card number, expiry date, and CVV.",
                "INVALID_CARD"
            )

        # Expired card
        if "expired" in error_code_lower or "expired" in detail_lower:
            return (
                "❌ Your card has expired. Please use a valid card.",
                "EXPIRED_CARD"
            )

        # CVV mismatch
        if "cvv" in error_code_lower or "cvv" in detail_lower:
            return (
                "❌ CVV verification failed. Please check your CVV code.",
                "CVV_MISMATCH"
            )

        # Generic error
        return (
            "❌ Payment failed. Please try again or contact your bank for support.",
            "PAYMENT_FAILED"
        )


# Global payment processor instance
payment_processor = SquarePaymentProcessor()