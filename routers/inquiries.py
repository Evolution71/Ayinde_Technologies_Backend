"""
Client inquiry endpoints, ported from the PHP handlers in api/process_*.php.

POST /api/inquiries/web-development/
POST /api/inquiries/app-development/
POST /api/inquiries/tech-consultancy/
POST /api/inquiries/premium-services/
POST /api/inquiries/project-startup/
GET  /api/inquiries/my-services/       (logged-in user's requests)
POST /api/newsletter/subscribe/

No emails are sent (same as the PHP site). Priority checkout records a
Pending transaction; it is not marked Successful until a real payment completes.
"""
import logging
import uuid
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from database import get_db, engine, Base
from auth import get_current_user
from models import User
import inquiry_models as im

# Create the inquiry tables if they don't exist yet (safe to run on every start)
Base.metadata.create_all(bind=engine)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["inquiries"])

# Prices from the official Ayinde service fliers (see service_pricing.py).
# Both the flier names and the older names are accepted so existing forms still work.
WEB_PLANS = {
    "Starter": 297.00, "Basic": 297.00,
    "Professional": 497.00, "Intermediate": 497.00,
    "Advanced": 697.00,
    "Premium": 897.00, "Custom": 897.00,
}
APP_PLANS = {
    "Starter": 897.00, "MVP": 897.00,
    "Professional": 1097.00, "CrossPlatform": 1097.00,
    "Advanced": 1297.00, "Native": 1297.00,
    "Premium": 1497.00, "Enterprise": 1497.00,
}
# Minimum package totals: Starter 1 hr x $50, Standard 3 hrs x $100, Enterprise 10 hrs x $300
CONSULT_PLANS = {"Starter": 50.00, "Standard": 300.00, "Enterprise": 3000.00}
# Premium (Supreme VIP Platinum) at $2,394/month. Longer plans use the same
# discount rules as service_pricing.py (quarterly 5%, annual 10%).
PREMIUM_PLANS = {
    "Monthly": 2394.00,
    "Quarterly": 2394.00 * 3 * 0.95,
    "BiAnnually": 2394.00 * 6,
    "Annually": 2394.00 * 12 * 0.90,
}


class PersonIn(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=50)


class PlanInquiryIn(PersonIn):
    plan: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=1, max_length=5000)
    priority_checkout: bool = False


class PremiumInquiryIn(PlanInquiryIn):
    company_name: str = Field(..., min_length=1, max_length=150)
    terms_accepted: bool = False


class StartupInquiryIn(PersonIn):
    company: Optional[str] = Field(None, max_length=150)
    service_type: str = Field(..., min_length=1, max_length=100)
    budget: str = Field(..., min_length=1, max_length=50)
    project_details: str = Field(..., min_length=1, max_length=5000)
    attachments: List[str] = []  # file names only; file storage is not part of this port
    terms_accepted: bool = False


class NewsletterIn(BaseModel):
    email: EmailStr


def _tracking(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"


def _get_or_create_client(db: Session, person: PersonIn) -> im.Client:
    email = person.email.lower()
    client = db.query(im.Client).filter(im.Client.email == email).first()
    if client is None:
        client = im.Client(first_name=person.first_name, last_name=person.last_name, email=email, phone=person.phone)
        db.add(client)
        db.flush()
    else:
        client.first_name = person.first_name
        client.last_name = person.last_name
        if person.phone:
            client.phone = person.phone
    return client


def _plan_inquiry(db, body, plans, service_label, prefix, detail_model, company_name=None):
    if body.plan not in plans:
        raise HTTPException(status_code=400, detail=f"Unknown plan '{body.plan}'")
    amount = plans[body.plan]

    client = _get_or_create_client(db, body)
    svc = im.ClientService(client_id=client.id, service_type=service_label,
                           tracking_reference=_tracking(prefix), status="Pending")
    db.add(svc)
    db.flush()

    if detail_model is im.PremiumService:
        db.add(im.PremiumService(client_service_id=svc.id, company_name=company_name or "",
                                 plan_tier=body.plan, project_description=body.description,
                                 payment_status="Unpaid"))
    else:
        db.add(detail_model(client_service_id=svc.id, plan_tier=body.plan,
                            project_description=body.description, payment_status="Unpaid"))

    if body.priority_checkout:
        db.add(im.Transaction(client_service_id=svc.id, amount=amount,
                              transaction_reference=_tracking("TXN"), status="Pending"))

    db.commit()
    return {
        "success": True,
        "tracking_reference": svc.tracking_reference,
        "amount_due": amount,
        "priority_checkout": body.priority_checkout,
    }


@router.post("/inquiries/web-development/", status_code=status.HTTP_201_CREATED)
def web_development_inquiry(body: PlanInquiryIn, db: Session = Depends(get_db)):
    return _plan_inquiry(db, body, WEB_PLANS, "Website Development", "AY-WEB", im.WebDevelopmentService)


@router.post("/inquiries/app-development/", status_code=status.HTTP_201_CREATED)
def app_development_inquiry(body: PlanInquiryIn, db: Session = Depends(get_db)):
    return _plan_inquiry(db, body, APP_PLANS, "App Development", "AY-APP", im.AppDevelopmentService)


@router.post("/inquiries/tech-consultancy/", status_code=status.HTTP_201_CREATED)
def tech_consultancy_inquiry(body: PlanInquiryIn, db: Session = Depends(get_db)):
    return _plan_inquiry(db, body, CONSULT_PLANS, "Tech Consultancy", "AY-CON", im.TechConsultancyService)


@router.post("/inquiries/premium-services/", status_code=status.HTTP_201_CREATED)
def premium_services_inquiry(body: PremiumInquiryIn, db: Session = Depends(get_db)):
    if not body.terms_accepted:
        raise HTTPException(status_code=400, detail="You must accept the Terms and Conditions.")
    return _plan_inquiry(db, body, PREMIUM_PLANS, "Premium Enterprise", "AY-PREM", im.PremiumService,
                         company_name=body.company_name)


@router.post("/inquiries/project-startup/", status_code=status.HTTP_201_CREATED)
def project_startup_inquiry(body: StartupInquiryIn, db: Session = Depends(get_db)):
    if not body.terms_accepted:
        raise HTTPException(status_code=400, detail="You must accept the Terms and Conditions.")

    client = _get_or_create_client(db, body)
    svc = im.ClientService(client_id=client.id, service_type=f"Project Startup: {body.service_type}",
                           tracking_reference=_tracking("AY-START"), status="Pending")
    db.add(svc)
    db.flush()
    db.add(im.ProjectStartup(client_service_id=svc.id, company_name=body.company,
                             service_type=body.service_type, budget_range=body.budget,
                             project_details=body.project_details,
                             attachments=json.dumps(body.attachments)))
    db.commit()
    return {"success": True, "tracking_reference": svc.tracking_reference}


@router.get("/inquiries/my-services/")
def my_services(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Requests made with the logged-in user's email address."""
    client_ids = [c.id for c in db.query(im.Client).filter(im.Client.email == current_user.email.lower()).all()]
    if not client_ids:
        return []
    services = (db.query(im.ClientService)
                .filter(im.ClientService.client_id.in_(client_ids))
                .order_by(im.ClientService.created_at.desc())
                .all())
    return [{
        "tracking_reference": s.tracking_reference,
        "service_type": s.service_type,
        "status": s.status,
        "progress_percentage": s.progress_percentage,
        "current_phase": s.current_phase,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    } for s in services]


class HrWiseDemoIn(PersonIn):
    company: str = Field(..., min_length=1, max_length=150)
    employee_count: int = Field(..., ge=1, le=1000000)
    message: Optional[str] = Field(None, max_length=5000)
    terms_accepted: bool = False


@router.post("/inquiries/hr-wise-demo/", status_code=status.HTTP_201_CREATED)
def hr_wise_demo_inquiry(body: HrWiseDemoIn, db: Session = Depends(get_db)):
    """Demo request for HR-Wise. Online subscription is not open yet, so no payment is taken here."""
    if not body.terms_accepted:
        raise HTTPException(status_code=400, detail="You must accept the Privacy Policy and Terms of Service.")

    client = _get_or_create_client(db, body)
    svc = im.ClientService(client_id=client.id, service_type="HR-Wise Demo",
                           tracking_reference=_tracking("AY-HR"), status="Pending")
    db.add(svc)
    db.flush()
    db.add(im.ProjectStartup(client_service_id=svc.id, company_name=body.company,
                             service_type="HR-Wise", budget_range="Not specified",
                             project_details=f"Employees: {body.employee_count}\n{body.message or ''}".strip(),
                             attachments="[]"))
    db.commit()
    return {"success": True, "tracking_reference": svc.tracking_reference}


@router.post("/newsletter/subscribe/", status_code=status.HTTP_201_CREATED)
def subscribe_newsletter(body: NewsletterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    existing = db.query(im.NewsletterSubscription).filter(im.NewsletterSubscription.email == email).first()
    if existing:
        if existing.status != "active":
            existing.status = "active"
            db.commit()
        return {"success": True, "message": "You are already subscribed."}
    db.add(im.NewsletterSubscription(email=email))
    db.commit()
    return {"success": True, "message": "Thanks for subscribing!"}
