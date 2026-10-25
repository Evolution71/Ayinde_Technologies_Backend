"""
Forms builder.

Admin endpoints:
- GET    /api/forms/admin/              List forms
- POST   /api/forms/admin/              Create a form
- PATCH  /api/forms/admin/{form_id}     Update title, fields, or active state
- DELETE /api/forms/admin/{form_id}     Delete a form and its submissions
- GET    /api/forms/admin/{form_id}/submissions   Submissions for one form

Public endpoints:
- GET  /api/forms/{slug}          Get a form's fields so the website can render it
- POST /api/forms/{slug}/submit   Submit a form (CAPTCHA, rate limited). Creates or updates a contact.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from admin import require_admin
from database import get_db
from email_utils import email_sender
from models import FormDefinition, FormSubmission, User
from routers.crm import upsert_contact
from security import limiter, verify_captcha

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/forms", tags=["forms"])

FIELD_TYPES = {"text", "email", "phone", "textarea", "select", "checkbox"}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class FieldSpec(BaseModel):
    key: str = Field(..., pattern=r"^[a-z][a-z0-9_]{0,39}$")
    label: str = Field(..., min_length=1, max_length=200)
    type: str = "text"
    required: bool = False
    options: Optional[List[str]] = None


class FormCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    fields: List[FieldSpec]
    is_active: bool = True


class FormUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    fields: Optional[List[FieldSpec]] = None
    is_active: Optional[bool] = None


class FormSubmit(BaseModel):
    values: Dict[str, Any]
    captcha_token: str
    captcha_answer: str


def _validate_fields(fields: List[FieldSpec]) -> None:
    keys = [f.key for f in fields]
    if len(keys) != len(set(keys)):
        raise HTTPException(status_code=400, detail="Each field needs a unique key.")
    for f in fields:
        if f.type not in FIELD_TYPES:
            raise HTTPException(status_code=400, detail=f"Unsupported field type: {f.type}")
        if f.type == "select" and not f.options:
            raise HTTPException(status_code=400, detail=f"Select field '{f.key}' needs options.")


def _form_to_dict(form: FormDefinition, include_admin_fields: bool = False) -> dict:
    data = {
        "id": form.id,
        "slug": form.slug,
        "title": form.title,
        "description": form.description,
        "fields": form.fields or [],
        "is_active": form.is_active,
    }
    return data


def _get_form_or_404(db: Session, form_id: int) -> FormDefinition:
    form = db.query(FormDefinition).filter(FormDefinition.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found.")
    return form


# ========== PUBLIC ==========

@router.get("/{slug}")
async def get_public_form(slug: str, db: Session = Depends(get_db)):
    form = db.query(FormDefinition).filter(FormDefinition.slug == slug).first()
    if not form or not form.is_active:
        raise HTTPException(status_code=404, detail="Form not found.")
    return _form_to_dict(form)


@router.post("/{slug}/submit", status_code=201)
@limiter.limit("5/minute")
async def submit_form(slug: str, request: Request, body: FormSubmit, db: Session = Depends(get_db)):
    if not verify_captcha(body.captcha_token, body.captcha_answer):
        raise HTTPException(status_code=400, detail="Invalid CAPTCHA. Please try again.")

    form = db.query(FormDefinition).filter(FormDefinition.slug == slug).first()
    if not form or not form.is_active:
        raise HTTPException(status_code=404, detail="Form not found.")

    # Check required fields and pick out the contact details
    cleaned: Dict[str, Any] = {}
    for spec in form.fields or []:
        value = body.values.get(spec["key"])
        if isinstance(value, str):
            value = value.strip()[:2000]
        if spec.get("required") and value in (None, "", False):
            raise HTTPException(status_code=400, detail=f"'{spec['label']}' is required.")
        if value not in (None, ""):
            cleaned[spec["key"]] = value

    email = cleaned.get("email")
    name = cleaned.get("name")
    if not email:
        raise HTTPException(status_code=400, detail="This form needs an email field.")
    if not name:
        name = email.split("@")[0]

    try:
        contact = upsert_contact(
            db,
            name=str(name)[:100],
            email=str(email),
            phone=str(cleaned["phone"]) if "phone" in cleaned else None,
            company=str(cleaned["company"]) if "company" in cleaned else None,
            source=f"form:{form.slug}",
            tags=form.slug,
        )
        submission = FormSubmission(form_id=form.id, contact_id=contact.id, data=cleaned)
        db.add(submission)
        db.commit()
        db.refresh(submission)
    except Exception:
        db.rollback()
        logger.exception("Failed to save form submission")
        raise HTTPException(status_code=500, detail="Could not submit the form. Please try again.")

    return {"status": "success", "submission_id": submission.id, "message": "Thanks! We'll be in touch soon."}


# ========== ADMIN ==========

@router.get("/admin/")
async def list_forms(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [_form_to_dict(f) for f in db.query(FormDefinition).order_by(FormDefinition.created_at.desc()).all()]


@router.post("/admin/", status_code=201)
async def create_form(body: FormCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not SLUG_RE.match(body.slug):
        raise HTTPException(status_code=400, detail="slug may only contain lowercase letters, numbers and hyphens.")
    if db.query(FormDefinition.id).filter(FormDefinition.slug == body.slug).first():
        raise HTTPException(status_code=409, detail="A form with this slug already exists.")
    _validate_fields(body.fields)
    try:
        form = FormDefinition(
            slug=body.slug,
            title=body.title,
            description=body.description,
            fields=[f.model_dump() for f in body.fields],
            is_active=body.is_active,
        )
        db.add(form)
        db.commit()
        db.refresh(form)
    except Exception:
        db.rollback()
        logger.exception("Failed to create form")
        raise HTTPException(status_code=500, detail="Could not create the form.")
    return _form_to_dict(form)


@router.patch("/admin/{form_id}")
async def update_form(form_id: int, body: FormUpdate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    form = _get_form_or_404(db, form_id)
    data = body.model_dump(exclude_unset=True)
    if "fields" in data and data["fields"] is not None:
        _validate_fields(body.fields)
        form.fields = [f.model_dump() for f in body.fields]
        data.pop("fields")
    for field, value in data.items():
        setattr(form, field, value)
    db.commit()
    db.refresh(form)
    return _form_to_dict(form)


@router.delete("/admin/{form_id}")
async def delete_form(form_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    form = _get_form_or_404(db, form_id)
    db.delete(form)
    db.commit()
    return {"status": "deleted", "id": form_id}


@router.get("/admin/{form_id}/submissions")
async def list_submissions(form_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    _get_form_or_404(db, form_id)
    rows = (
        db.query(FormSubmission)
        .filter(FormSubmission.form_id == form_id)
        .order_by(FormSubmission.created_at.desc())
        .limit(500)
        .all()
    )
    return [
        {"id": s.id, "contact_id": s.contact_id, "data": s.data, "created_at": s.created_at.isoformat() if s.created_at else None}
        for s in rows
    ]
