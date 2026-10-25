"""
CRM: contacts and sales pipeline (admin only, except the shared helper).

Admin endpoints:
- GET    /api/crm/contacts/              List contacts (filters: stage, tag, q, limit, offset)
- POST   /api/crm/contacts/              Create a contact
- GET    /api/crm/contacts/{id}          Get one contact
- PATCH  /api/crm/contacts/{id}          Update details, tags, notes
- DELETE /api/crm/contacts/{id}          Delete a contact
- PATCH  /api/crm/contacts/{id}/stage    Move a contact along the pipeline
- GET    /api/crm/pipeline               Contact counts per stage

Shared helper:
- upsert_contact()  Used by bookings and forms so each person has one record.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from admin import require_admin
from database import get_db
from models import Contact, PIPELINE_STAGES, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crm", tags=["crm"])


# ========== SHARED HELPER ==========

def _merge_tags(existing: str, new: Optional[str]) -> str:
    current = {t.strip() for t in (existing or "").split(",") if t.strip()}
    if new:
        current |= {t.strip() for t in new.split(",") if t.strip()}
    return ",".join(sorted(current))


def upsert_contact(
    db: Session,
    *,
    name: str,
    email: str,
    phone: Optional[str] = None,
    company: Optional[str] = None,
    source: str = "website",
    notes: Optional[str] = None,
    tags: Optional[str] = None,
) -> Contact:
    """
    Find a contact by email and update it, or create one. Does NOT commit;
    the caller commits together with its own record (booking, submission).
    """
    email = email.lower()
    contact = db.query(Contact).filter(Contact.email == email).first()
    if contact is None:
        contact = Contact(
            name=name.strip(),
            email=email,
            phone=phone,
            company=company,
            source=source,
            pipeline_stage="new",
            tags=_merge_tags("", tags),
            notes=notes,
        )
        db.add(contact)
        db.flush()  # assigns contact.id without committing
        return contact

    # Existing contact: fill in blanks, never overwrite what the admin entered
    contact.name = contact.name or name.strip()
    contact.phone = contact.phone or phone
    contact.company = contact.company or company
    if notes:
        contact.notes = f"{contact.notes}\n\n[{source}] {notes}" if contact.notes else f"[{source}] {notes}"
    contact.tags = _merge_tags(contact.tags, tags)
    contact.updated_at = datetime.now(timezone.utc)
    return contact


# ========== SCHEMAS ==========

class ContactCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=50)
    company: Optional[str] = Field(None, max_length=150)
    source: Optional[str] = Field("manual", max_length=50)
    tags: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=5000)


class ContactUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    company: Optional[str] = Field(None, max_length=150)
    tags: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=5000)


class StageUpdate(BaseModel):
    stage: str


def _contact_to_dict(c: Contact) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "company": c.company,
        "source": c.source,
        "pipeline_stage": c.pipeline_stage,
        "tags": [t for t in (c.tags or "").split(",") if t],
        "notes": c.notes,
        "last_contacted_at": c.last_contacted_at.isoformat() if c.last_contacted_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _get_or_404(db: Session, contact_id: int) -> Contact:
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found.")
    return contact


# ========== ENDPOINTS ==========

@router.get("/contacts/")
async def list_contacts(
    stage: Optional[str] = None,
    tag: Optional[str] = None,
    q: Optional[str] = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Contact)
    if stage:
        query = query.filter(Contact.pipeline_stage == stage)
    if tag:
        query = query.filter(Contact.tags.like(f"%{tag}%"))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Contact.name.ilike(like), Contact.email.ilike(like), Contact.company.ilike(like)))
    total = query.count()
    rows = query.order_by(Contact.created_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "items": [_contact_to_dict(c) for c in rows]}


@router.post("/contacts/", status_code=201)
async def create_contact(body: ContactCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(Contact.id).filter(Contact.email == body.email.lower()).first():
        raise HTTPException(status_code=409, detail="A contact with this email already exists.")
    try:
        contact = upsert_contact(
            db,
            name=body.name,
            email=body.email,
            phone=body.phone,
            company=body.company,
            source=body.source or "manual",
            notes=body.notes,
            tags=body.tags,
        )
        db.commit()
        db.refresh(contact)
    except Exception:
        db.rollback()
        logger.exception("Failed to create contact")
        raise HTTPException(status_code=500, detail="Could not create contact.")
    return _contact_to_dict(contact)


@router.get("/contacts/{contact_id}")
async def get_contact(contact_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return _contact_to_dict(_get_or_404(db, contact_id))


@router.patch("/contacts/{contact_id}")
async def update_contact(
    contact_id: int,
    body: ContactUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    contact = _get_or_404(db, contact_id)
    data = body.model_dump(exclude_unset=True)
    if "tags" in data:
        contact.tags = _merge_tags("", data.pop("tags"))  # replaces the tag list
    for field, value in data.items():
        setattr(contact, field, value.strip() if isinstance(value, str) else value)
    contact.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(contact)
    return _contact_to_dict(contact)


@router.patch("/contacts/{contact_id}/stage")
async def move_stage(
    contact_id: int,
    body: StageUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if body.stage not in PIPELINE_STAGES:
        raise HTTPException(status_code=400, detail=f"stage must be one of: {', '.join(PIPELINE_STAGES)}")
    contact = _get_or_404(db, contact_id)
    contact.pipeline_stage = body.stage
    contact.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(contact)
    return _contact_to_dict(contact)


@router.delete("/contacts/{contact_id}")
async def delete_contact(contact_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    contact = _get_or_404(db, contact_id)
    db.delete(contact)
    db.commit()
    return {"status": "deleted", "id": contact_id}


@router.get("/pipeline")
async def pipeline_summary(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    counts = {stage: 0 for stage in PIPELINE_STAGES}
    for stage, in db.query(Contact.pipeline_stage).all():
        if stage in counts:
            counts[stage] += 1
    return {"stages": PIPELINE_STAGES, "counts": counts}
