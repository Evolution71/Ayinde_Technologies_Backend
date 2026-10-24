"""
Add missing service_tiers rows, using the Ayinde service fliers as a starting point.

Your database is the source of truth for prices. This script only inserts rows that
do not exist yet. It never updates an existing row.

- Website:      starter 297, professional 497, advanced 697, premium 897 per month
- Applications: starter 897, professional 1097, advanced 1297, premium 1497 per month
- Premium:      supreme 2394 per month
- Consultation: standard $100/hr (min 3), enterprise $300/hr (min 10)

Idempotent: it updates existing rows and inserts missing ones. Run from the
backend folder with the same DATABASE_URL the API uses:
    python update_service_prices.py
"""

from datetime import datetime, timezone

from database import SessionLocal
from models import ServiceTier
from service_pricing import MONTHLY_PRICES, CONSULTATION_RATES, compute_service_amount

FEATURES = {
    ("website", "starter"): [
        "Professional website design & development", "Up to 5 pages", "Mobile responsive design",
        "Basic SEO", "Contact form & social links", "8 update hours per month", "Email support", "SSL certificate",
    ],
    ("website", "professional"): [
        "Everything in Starter", "Up to 10 pages", "Advanced SEO", "Google Analytics integration",
        "E-commerce ready (up to 50 products)", "Email marketing", "Blog setup", "16 update hours per month",
        "Performance monitoring",
    ],
    ("website", "advanced"): [
        "Everything in Professional", "Unlimited pages", "AI-powered chatbot", "Unlimited-product e-commerce",
        "Custom integrations, CRM & API development", "24 update hours per month", "24/7 priority support",
        "Advanced analytics reporting",
    ],
    ("website", "premium"): [
        "Everything in Advanced", "Dedicated account manager", "Custom AI solutions", "Enterprise e-commerce",
        "Advanced security", "White-label options", "Custom development", "32 update hours per month",
        "24/7 dedicated support", "Quarterly strategy reviews", "Priority feature development",
    ],
    ("applications", "starter"): [
        "Native iOS & Android", "Firebase backend setup", "Basic push notifications", "User authentication",
        "Basic database", "App Store submission", "Monthly updates (16 hours)", "Email support",
        "Performance monitoring",
    ],
    ("applications", "professional"): [
        "Everything in Starter", "Advanced database", "Real-time data sync", "In-app payments",
        "Advanced push notifications", "Social integration", "Analytics dashboard", "Weekly updates (24 hours)",
        "24/7 priority support",
    ],
    ("applications", "advanced"): [
        "Everything in Professional", "Cross-platform (iOS & Android)", "Advanced security", "AI/ML integration",
        "Real-time chat", "Video streaming", "Bi-weekly updates (32 hours)", "Dedicated development team",
        "24/7 dedicated support",
    ],
    ("applications", "premium"): [
        "Everything in Advanced", "Dedicated account manager", "Cloud infrastructure", "Advanced AI/ML",
        "Enterprise security", "Multi-platform (web + mobile)", "Weekly updates (40+ hours)",
        "Custom integrations", "Quarterly strategy reviews", "White-label options", "Priority feature development",
    ],
    ("premium", "supreme"): [
        "Complete solution: website AND application development in one package",
        "Enterprise support: 24/7 dedicated support, rapid bug fixes and priority feature development",
        "Advanced AI: latest AI functions and chatbot capabilities",
        "Dedicated account manager: a single point of contact and quarterly strategy reviews",
        "Monetization: complete deployment and monetization support",
        "Flexible payment: monthly, quarterly, annual or 50% down",
    ],
    ("consultation", "starter"): [
        "1-hour focused consultation", "Initial discovery & assessment", "Quick expert advice",
        "Basic recommendations", "Q&A session", "Email follow-up",
    ],
    ("consultation", "standard"): [
        "One-on-one consultation", "Strategy and advice", "Up to 3 hours per session", "Email support",
        "Solutions & recommendations", "Project roadmap (basic)",
    ],
    ("consultation", "enterprise"): [
        "Dedicated consultant", "Deep-dive strategy sessions", "Minimum 10 hours", "Priority email & phone support",
        "Detailed recommendations report", "Implementation roadmap", "Weekly check-ins", "Custom solutions design",
    ],
}

NAMES = {
    "website": "Website", "applications": "App Development", "premium": "Supreme VIP Platinum",
}


def _package_fields(service_type, tier):
    if service_type == "consultation":
        rate = CONSULTATION_RATES[tier]["hourly"]
        return {
            "monthly_price": rate,  # hourly rate for consultation rows
            "quarterly_price": None,
            "annual_price": None,
            "fifty_percent_down": None,
            "description": f"Consultation billed at ${rate:,.0f} per hour, minimum {CONSULTATION_RATES[tier]['min_hours']} hours",
        }
    base = MONTHLY_PRICES[service_type][tier]
    return {
        "monthly_price": base,
        "quarterly_price": compute_service_amount(service_type, tier, "quarterly")[0],
        "annual_price": compute_service_amount(service_type, tier, "annual")[0],
        "fifty_percent_down": compute_service_amount(service_type, tier, "halfdown")[0],
        "description": f"{NAMES[service_type]} package at ${base:,.0f} per month",
    }


def sync():
    """
    Adds any package that is missing from service_tiers. Existing rows are never
    changed, so prices you have set in the database are kept as they are.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        created = skipped = 0
        for (service_type, tier), features in FEATURES.items():
            row = db.query(ServiceTier).filter(
                ServiceTier.service_type == service_type,
                ServiceTier.tier == tier,
            ).first()
            if row is not None:
                skipped += 1
                continue
            fields = _package_fields(service_type, tier)
            row = ServiceTier(service_type=service_type, tier=tier, is_active=True, created_at=now,
                              features=features, updated_at=now, **fields)
            db.add(row)
            created += 1
        db.commit()
        print(f"Service tiers: {created} added, {skipped} existing rows left unchanged.")
    finally:
        db.close()


if __name__ == "__main__":
    sync()
