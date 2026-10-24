"""
Server-side price list for Ayinde service packages.

These numbers come from the official service fliers and mirror
frontend/src/lib/servicePlans.js. The server always recalculates the amount
from this table, so the browser can never change what a customer is charged.

Payment options:
- monthly:   base price per month
- quarterly: 3 months with 5% off
- annual:    12 months with 10% off
- halfdown:  50% down (3 x monthly), then the rest over 6 months

Consultation is billed by the hour, with a minimum number of hours.
"""

import math
from typing import Optional, Tuple

# Monthly package prices in USD
MONTHLY_PRICES = {
    "website": {
        "starter": 297.00,
        "professional": 497.00,
        "advanced": 697.00,
        "premium": 897.00,
    },
    "applications": {
        "starter": 897.00,
        "professional": 1097.00,
        "advanced": 1297.00,
        "premium": 1497.00,
    },
    "premium": {
        "supreme": 2394.00,
    },
}

# Hourly consultation rates and minimum hours
CONSULTATION_RATES = {
    "starter": {"hourly": 50.00, "min_hours": 1},
    "standard": {"hourly": 100.00, "min_hours": 3},
    "enterprise": {"hourly": 300.00, "min_hours": 10},
}

SERVICE_TYPES = tuple(MONTHLY_PRICES.keys()) + ("consultation",)
PAYMENT_OPTIONS = ("monthly", "quarterly", "annual", "halfdown")


def _round(value: float) -> float:
    return round(value + 1e-9, 2)


def load_tier_base(db, service_type: str, tier: str) -> float:
    """
    Monthly base price (or hourly rate for consultation) from the service_tiers
    table, which is the source of truth. Raises ValueError if the package is not set up.
    """
    from models import ServiceTier  # local import avoids a circular import at startup

    row = db.query(ServiceTier).filter(
        ServiceTier.service_type == service_type,
        ServiceTier.tier == tier,
        ServiceTier.is_active == True,
    ).first()
    if not row or row.monthly_price is None:
        raise ValueError("This package is not available right now. Please refresh the page.")
    if float(row.monthly_price) <= 0:
        raise ValueError("This package is not priced yet. Please contact support.")
    return float(row.monthly_price)


def compute_service_amount(
    service_type: str,
    tier: str,
    payment_option: str,
    hours: Optional[float] = None,
    db=None,
) -> Tuple[float, str]:
    """
    Return (amount_in_dollars, period_label) for a package.

    Prices come from service_tiers when a database session is given. The
    built-in table is only used when db is None (tests and scripts).
    Raises ValueError for an unknown service, tier, option or hour count.
    """
    service_type = (service_type or "").lower()
    tier = (tier or "").lower()
    payment_option = (payment_option or "").lower()

    if service_type == "consultation":
        rate_info = CONSULTATION_RATES.get(tier)
        if not rate_info:
            raise ValueError("Unknown consultation package")
        hourly = load_tier_base(db, "consultation", tier) if db is not None else rate_info["hourly"]
        try:
            requested = float(hours or 0)
        except (TypeError, ValueError):
            raise ValueError("Invalid number of hours")
        if requested != requested or requested < 0 or requested > 1000:
            raise ValueError("Invalid number of hours")
        billed = math.ceil(max(requested, rate_info["min_hours"]))
        label = f"{billed} hour{'s' if billed != 1 else ''}"
        return _round(billed * hourly), label

    if db is not None:
        if service_type not in MONTHLY_PRICES or tier not in MONTHLY_PRICES[service_type]:
            raise ValueError("Unknown service package")
        base = load_tier_base(db, service_type, tier)
    else:
        prices = MONTHLY_PRICES.get(service_type)
        if not prices or tier not in prices:
            raise ValueError("Unknown service package")
        base = prices[tier]

    if payment_option == "monthly":
        return _round(base), "monthly"
    if payment_option == "quarterly":
        return _round(base * 3 * 0.95), "quarterly"
    if payment_option == "annual":
        return _round(base * 12 * 0.90), "annual"
    if payment_option == "halfdown":
        return _round((base * 6) / 2), "50% down + 6 months"
    raise ValueError("Unknown payment option")
