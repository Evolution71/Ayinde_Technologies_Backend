"""
Bookings (website calendar).

Public endpoints:
- GET  /api/bookings/availability?date=YYYY-MM-DD   Open time slots for a day
- POST /api/bookings/                               Request a call (CAPTCHA, rate limited)

Admin endpoints:
- GET   /api/bookings/admin/                        List bookings
- PATCH /api/bookings/admin/{booking_id}            Confirm, complete or cancel

Environment variables:
- BUSINESS_TIMEZONE  IANA timezone for opening hours (default "America/New_York")
- ADMIN_EMAILS       Used by admin.py to decide who can manage bookings
"""

import html as html_lib
import logging
import os
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Literal, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from admin import ADMIN_EMAILS, require_admin
from database import get_db
from email_utils import email_sender
from models import Booking, User
from routers.crm import upsert_contact
from security import limiter, verify_captcha

logger = logging.getLogger(__name__)
router = APIRouter(tags=["bookings"])

# ---- Working hours: change these to match your week ----
SLOT_MINUTES = 60
OPEN_HOUR = 9                        # first slot starts at 09:00 business time
CLOSE_HOUR = 17                      # last slot must finish by 17:00 business time
WORKING_WEEKDAYS = {0, 1, 2, 3, 4}   # Monday=0 ... Sunday=6

esc = html_lib.escape


# ========== TIME HELPERS ==========

def _business_tz() -> ZoneInfo:
    return ZoneInfo(os.getenv("BUSINESS_TIMEZONE", "America/New_York"))


def _to_naive_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _slots_for_day(day: date) -> List[datetime]:
    if day.weekday() not in WORKING_WEEKDAYS:
        return []
    tz = _business_tz()
    current = datetime.combine(day, time(OPEN_HOUR), tzinfo=tz)
    close = datetime.combine(day, time(CLOSE_HOUR), tzinfo=tz)
    slots = []
    while current + timedelta(minutes=SLOT_MINUTES) <= close:
        slots.append(current.astimezone(timezone.utc))
        current += timedelta(minutes=SLOT_MINUTES)
    return slots


def _format_local(dt_utc: datetime) -> str:
    return dt_utc.astimezone(_business_tz()).strftime("%A, %B %d %Y at %I:%M %p %Z")


def _booking_to_dict(b: Booking) -> dict:
    return {
        "id": b.id,
        "contact_id": b.contact_id,
        "name": b.name,
        "email": b.email,
        "phone": b.phone,
        "company": b.company,
        "service_interest": b.service_interest,
        "preferred_start": b.preferred_start.replace(tzinfo=timezone.utc).isoformat(),
        "notes": b.notes,
        "status": b.status,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }


# ========== SCHEMAS ==========

class BookingRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=50)
    company: Optional[str] = Field(None, max_length=150)
    service_interest: Optional[str] = Field(None, max_length=100)
    preferred_start: datetime  # ISO 8601 with offset, e.g. 2026-10-20T10:00:00+01:00
    notes: Optional[str] = Field(None, max_length=2000)
    captcha_token: str
    captcha_answer: str


class BookingStatusUpdate(BaseModel):
    status: Literal["confirmed", "completed", "cancelled"]


# ========== PUBLIC ==========

@router.get("/api/bookings/availability")
async def get_availability(
    day: str = Query(..., alias="date", description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_db),
):
    try:
        requested_day = date.fromisoformat(day)
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be in YYYY-MM-DD format.")

    tz = _business_tz()
    if requested_day < datetime.now(tz).date():
        raise HTTPException(status_code=400, detail="That date has already passed.")

    slots = _slots_for_day(requested_day)
    if not slots:
        return {"date": requested_day.isoformat(), "timezone": str(tz), "slots": []}

    taken = {row[0] for row in db.query(Booking.preferred_start).filter(
        Booking.preferred_start >= _to_naive_utc(slots[0]),
        Booking.preferred_start <= _to_naive_utc(slots[-1]),
        Booking.status != "cancelled",
    ).all()}
    now = datetime.now(timezone.utc)

    available = [
        {"start": s.isoformat(), "label": s.astimezone(tz).strftime("%I:%M %p")}
        for s in slots
        if s > now and _to_naive_utc(s) not in taken
    ]
    return {"date": requested_day.isoformat(), "timezone": str(tz), "slots": available}


@router.post("/api/bookings/", status_code=201)
@limiter.limit("5/minute")
async def create_booking(request: Request, body: BookingRequest, db: Session = Depends(get_db)):
    if not verify_captcha(body.captcha_token, body.captcha_answer):
        raise HTTPException(status_code=400, detail="Invalid CAPTCHA. Please try again.")

    if body.preferred_start.tzinfo is None:
        raise HTTPException(status_code=400, detail="preferred_start must include a timezone offset.")

    start_utc = body.preferred_start.astimezone(timezone.utc)
    if start_utc <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Please choose a time in the future.")

    local_day = start_utc.astimezone(_business_tz()).date()
    if start_utc not in _slots_for_day(local_day):
        raise HTTPException(status_code=400, detail="That time is outside our booking hours.")

    if db.query(Booking.id).filter(
        Booking.preferred_start == _to_naive_utc(start_utc),
        Booking.status != "cancelled",
    ).first():
        raise HTTPException(status_code=409, detail="That time was just booked. Please choose another slot.")

    try:
        contact = upsert_contact(
            db,
            name=body.name,
            email=body.email,
            phone=body.phone,
            company=body.company,
            source="booking",
            notes=f"Requested a call: {body.service_interest or 'general'}",
            tags="booked-call",
        )
        booking = Booking(
            contact_id=contact.id,
            name=body.name.strip(),
            email=body.email.lower(),
            phone=body.phone,
            company=body.company,
            service_interest=body.service_interest,
            preferred_start=_to_naive_utc(start_utc),
            notes=body.notes,
            status="requested",
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
    except Exception:
        db.rollback()
        logger.exception("Failed to save booking")
        raise HTTPException(status_code=500, detail="Could not save your booking. Please try again.")

    when = _format_local(start_utc)
    for admin_email in ADMIN_EMAILS:
        email_sender._send_email(
            admin_email,
            f"New booking request: {booking.name}",
            f"<p><strong>{esc(booking.name)}</strong> ({esc(booking.email)}) requested a call on {esc(when)}.</p>"
            f"<p>Service: {esc(booking.service_interest or 'not specified')}</p>"
            f"<p>Notes: {esc(booking.notes or '-')}</p>",
        )
    email_sender._send_email(
        booking.email,
        "We received your booking request",
        f"<p>Hi {esc(booking.name)},</p>"
        f"<p>Thanks for requesting a call with Ayinde Technologies on <strong>{esc(when)}</strong>.</p>"
        "<p>We'll confirm your appointment by email shortly.</p>"
        "<p>Ayinde Technologies</p>",
    )

    return {
        "status": "success",
        "booking_id": booking.id,
        "message": "Booking request received. We'll confirm by email.",
    }


# ========== ADMIN ==========

@router.get("/api/bookings/admin/")
async def list_bookings(
    status: Optional[str] = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Booking)
    if status:
        query = query.filter(Booking.status == status)
    rows = query.order_by(Booking.preferred_start.desc()).limit(200).all()
    return [_booking_to_dict(b) for b in rows]


@router.patch("/api/bookings/admin/{booking_id}")
async def update_booking_status(
    booking_id: int,
    body: BookingStatusUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    booking.status = body.status
    db.commit()
    db.refresh(booking)

    if body.status == "confirmed":
        when = _format_local(booking.preferred_start.replace(tzinfo=timezone.utc))
        email_sender._send_email(
            booking.email,
            "Your call is confirmed",
            f"<p>Hi {esc(booking.name)},</p>"
            f"<p>Your call with Ayinde Technologies is confirmed for <strong>{esc(when)}</strong>.</p>"
            "<p>Ayinde Technologies</p>",
        )

    return _booking_to_dict(booking)
