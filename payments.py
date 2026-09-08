"""
Flutterwave integration for course subscriptions.

Flow: 30-day free trial starts on enrollment (see routers/courses.py). When
the trial ends, the frontend calls /api/payments/initiate to get a
Flutterwave checkout link. Flutterwave confirms payment two ways — a
webhook (routers/payments.py) and/or the browser redirect back with a
transaction_id, which the frontend should send to /api/payments/verify.

CRITICAL: everything in this module is written to fail soft. If
FLUTTERWAVE_SECRET_KEY isn't set — e.g. you're live before you've set up a
merchant account — payments_enabled() returns False and every payment
endpoint returns a clean "not available yet" response instead of a 500.
Nothing else on the site (courses, login, contact) depends on this module
at all, so a missing key here can't break anything else.
"""

import os
import uuid
import requests

FLW_BASE_URL = "https://api.flutterwave.com/v3"


def payments_enabled() -> bool:
    return bool(os.getenv("FLUTTERWAVE_SECRET_KEY"))


def _secret_key() -> str:
    return os.getenv("FLUTTERWAVE_SECRET_KEY", "")


def make_tx_ref(user_id: int, course_id: int) -> str:
    return f"ayinde-u{user_id}-c{course_id}-{uuid.uuid4().hex[:10]}"


def create_payment_link(*, tx_ref: str, amount: float, currency: str,
                         customer_email: str, customer_name: str,
                         redirect_url: str, title: str):
    """
    Calls Flutterwave's Standard payment endpoint. Returns (True, link) on
    success, or (False, error_message) on failure — never raises, so a
    Flutterwave outage or bad key can't take down the endpoint calling this.
    """
    if not payments_enabled():
        return False, "Payments aren't configured yet."

    try:
        response = requests.post(
            f"{FLW_BASE_URL}/payments",
            json={
                "tx_ref": tx_ref,
                "amount": str(amount),
                "currency": currency,
                "redirect_url": redirect_url,
                "customer": {"email": customer_email, "name": customer_name},
                "customizations": {"title": title},
            },
            headers={
                "Authorization": f"Bearer {_secret_key()}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        data = response.json()
        if response.status_code == 200 and data.get("status") == "success":
            return True, data["data"]["link"]
        return False, data.get("message", "Could not start payment.")
    except requests.RequestException as e:
        return False, f"Could not reach the payment provider: {e}"
    except (KeyError, ValueError):
        return False, "Unexpected response from the payment provider."


def verify_transaction(transaction_id: str):
    """
    Confirms a transaction's real status directly with Flutterwave — never
    trust the redirect query params alone, they're client-controlled.
    Returns (True, data) on a confirmed successful payment, else (False, reason).
    """
    if not payments_enabled():
        return False, "Payments aren't configured yet."

    try:
        response = requests.get(
            f"{FLW_BASE_URL}/transactions/{transaction_id}/verify",
            headers={"Authorization": f"Bearer {_secret_key()}"},
            timeout=15,
        )
        data = response.json()
        if response.status_code == 200 and data.get("status") == "success":
            return True, data["data"]
        return False, data.get("message", "Could not verify transaction.")
    except requests.RequestException as e:
        return False, f"Could not reach the payment provider: {e}"
    except (KeyError, ValueError):
        return False, "Unexpected response from the payment provider."


def verify_webhook_signature(received_signature: str) -> bool:
    """
    Flutterwave sends back the secret hash you configured on their
    dashboard, verbatim, in the 'verif-hash' header. If you haven't set
    FLUTTERWAVE_SECRET_HASH yet, this always returns False — so an
    unconfigured webhook endpoint can't be spoofed by anyone who finds the URL.
    """
    configured_hash = os.getenv("FLUTTERWAVE_SECRET_HASH")
    if not configured_hash or not received_signature:
        return False
    return received_signature == configured_hash
