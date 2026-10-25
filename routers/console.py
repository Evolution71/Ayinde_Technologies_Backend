"""
Admin console API (the client management dashboard at /console).

Admin endpoints (require_admin: the logged-in email must be in ADMIN_EMAILS):

  GET    /api/console/me/                         Admin profile
  PATCH  /api/console/me/                         Update name / change password
  GET    /api/console/stats/                      Dashboard numbers + recent items
  GET    /api/console/projects/                   All client services (projects)
  PATCH  /api/console/projects/{id}/              Update status, phase, progress
  GET    /api/console/service-requests/           Pending requests
  POST   /api/console/service-requests/{id}/approve/   Set price, activate, create invoice
  POST   /api/console/service-requests/{id}/reject/    Cancel a request
  GET    /api/console/clients/                    Client list (for dropdowns)
  GET    /api/console/messages/                   All message threads
  POST   /api/console/messages/                   Reply to one client
  POST   /api/console/messages/broadcast/        Message every client
  POST   /api/console/messages/{id}/read/         Mark a client message read
  GET    /api/console/files/                      Shared files
  POST   /api/console/files/                      Upload a deliverable (multipart)
  GET    /api/console/files/{id}/download/        Download (auth header required)
  DELETE /api/console/files/{id}/                 Delete a file
  GET    /api/console/contacts/                   Contact form submissions
  POST   /api/console/contacts/{id}/read/         Mark read
  DELETE /api/console/contacts/{id}/              Delete
  GET    /api/console/newsletters/                Newsletter subscribers
  DELETE /api/console/newsletters/{id}/           Remove subscriber
  GET    /api/console/broadcasts/                 Broadcast history
  POST   /api/console/broadcasts/                 Send newsletter broadcast (background)

Public endpoints (router `public_router`, prefix /api/console/public):

  POST   /api/console/public/newsletter/          Subscribe to the newsletter
  POST   /api/console/public/requests/            Submit a service request (CAPTCHA)
"""

import logging
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from admin import require_admin
from auth import hash_password, verify_password
from console_models import (
    ConsoleBroadcast,
    ConsoleClient,
    ConsoleFile,
    ConsoleMessage,
    ConsoleService,
    ConsoleTransaction,
    NewsletterSubscriber,
)
from database import get_db
from email_utils import email_sender
from models import ContactMessage, User
from security import verify_captcha

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/console", tags=["console"])
public_router = APIRouter(prefix="/api/console/public", tags=["console-public"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "png", "jpg", "jpeg", "gif", "zip"}
PROJECT_STATUSES = ("Pending", "Active", "Completed", "Cancelled")
CLOSED_STATUSES = ("Completed", "Cancelled")


# ════════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════════

def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _client_name(client: ConsoleClient) -> str:
    return f"{client.first_name} {client.last_name}".strip()


def _split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split(" ", 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


def _new_reference(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(3).upper()}"


def _service_row(service: ConsoleService, client: ConsoleClient) -> dict:
    return {
        "id": service.id,
        "client_id": client.id,
        "client_name": _client_name(client),
        "client_email": client.email,
        "service_type": service.service_type,
        "tracking_reference": service.tracking_reference,
        "details": service.details,
        "status": service.status,
        "current_phase": service.current_phase,
        "progress_percentage": service.progress_percentage,
        "created_at": _iso(service.created_at),
    }


def _get_service(db: Session, service_id: int) -> ConsoleService:
    service = db.query(ConsoleService).filter(ConsoleService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Project not found.")
    return service


def _get_client(db: Session, client_id: int) -> ConsoleClient:
    client = db.query(ConsoleClient).filter(ConsoleClient.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
    return client


def _message_row(message: ConsoleMessage, client: ConsoleClient) -> dict:
    return {
        "id": message.id,
        "client_id": client.id,
        "client_name": _client_name(client),
        "client_email": client.email,
        "sender": message.sender,
        "subject": message.subject,
        "message": message.body,
        "is_read": bool(message.is_read),
        "created_at": _iso(message.created_at),
    }


def _contact_row(c: ContactMessage) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "company": c.company,
        "subject": c.subject,
        "message": c.message,
        "is_read": bool(c.is_read),
        "created_at": _iso(c.created_at),
    }


def _upsert_client(db: Session, *, name: str, email: str, phone: Optional[str]) -> ConsoleClient:
    """Find a client by email or create one. Does not commit."""
    email = email.lower()
    client = db.query(ConsoleClient).filter(ConsoleClient.email == email).first()
    first, last = _split_name(name)
    if client is None:
        client = ConsoleClient(first_name=first, last_name=last, email=email, phone=phone)
        db.add(client)
        db.flush()
    else:
        client.phone = client.phone or phone
    return client


# ════════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ════════════════════════════════════════════════════════════════════════════════

class MeUpdate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=200)
    current_password: Optional[str] = Field(None, max_length=200)
    new_password: Optional[str] = Field(None, max_length=200)
    confirm_password: Optional[str] = Field(None, max_length=200)


class ProjectUpdate(BaseModel):
    status: Literal["Pending", "Active", "Completed", "Cancelled"]
    current_phase: str = Field(..., min_length=1, max_length=100)
    progress_percentage: int = Field(..., ge=0, le=100)


class ApproveIn(BaseModel):
    amount: Decimal = Field(..., gt=0, le=Decimal("10000000"))


class MessageIn(BaseModel):
    client_id: int
    subject: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1, max_length=20000)


class BroadcastMessageIn(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1, max_length=20000)


class NewsletterBroadcastIn(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1, max_length=200000)


class PublicNewsletterIn(BaseModel):
    email: EmailStr


class PublicRequestIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=50)
    service_type: str = Field(..., min_length=2, max_length=100)
    details: Optional[str] = Field(None, max_length=5000)
    captcha_token: str
    captcha_answer: str


# ════════════════════════════════════════════════════════════════════════════════
# ADMIN PROFILE
# ════════════════════════════════════════════════════════════════════════════════

@router.get("/me/")
async def get_me(admin: User = Depends(require_admin)):
    return {
        "id": admin.id,
        "full_name": f"{admin.first_name or ''} {admin.last_name or ''}".strip() or admin.email,
        "first_name": admin.first_name or "",
        "last_name": admin.last_name or "",
        "email": admin.email,
    }


@router.patch("/me/")
async def update_me(body: MeUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    first, last = _split_name(body.full_name)
    admin.first_name = first
    admin.last_name = last

    wants_password = any([body.current_password, body.new_password, body.confirm_password])
    if wants_password:
        if not (body.current_password and body.new_password and body.confirm_password):
            raise HTTPException(status_code=400, detail="Please fill in all password fields to change your password.")
        if not verify_password(body.current_password, admin.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")
        if body.new_password != body.confirm_password:
            raise HTTPException(status_code=400, detail="New passwords do not match.")
        if len(body.new_password) < 8:
            raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")
        admin.password_hash = hash_password(body.new_password)

    db.commit()
    return {"status": "success", "message": "Profile updated successfully.", "full_name": body.full_name.strip()}


# ════════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════════════════════════

@router.get("/stats/")
async def get_stats(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    active_projects = (
        db.query(func.count(ConsoleService.id))
        .filter(ConsoleService.status.notin_(CLOSED_STATUSES))
        .scalar()
    )
    pending_requests = db.query(func.count(ConsoleService.id)).filter(ConsoleService.status == "Pending").scalar()
    unread_messages = (
        db.query(func.count(ConsoleMessage.id))
        .filter(ConsoleMessage.sender == "client", ConsoleMessage.is_read.is_(False))
        .scalar()
    )
    pending_total = (
        db.query(func.coalesce(func.sum(ConsoleTransaction.amount), 0))
        .filter(ConsoleTransaction.status.in_(["Pending", "Failed"]))
        .scalar()
    )

    recent_requests = (
        db.query(ConsoleService, ConsoleClient)
        .join(ConsoleClient, ConsoleService.client_id == ConsoleClient.id)
        .order_by(ConsoleService.created_at.desc())
        .limit(4)
        .all()
    )
    recent_messages = (
        db.query(ConsoleMessage, ConsoleClient)
        .join(ConsoleClient, ConsoleMessage.client_id == ConsoleClient.id)
        .filter(ConsoleMessage.sender == "client")
        .order_by(ConsoleMessage.created_at.desc())
        .limit(4)
        .all()
    )

    return {
        "active_projects": active_projects or 0,
        "pending_requests": pending_requests or 0,
        "unread_messages": unread_messages or 0,
        "pending_payments": float(pending_total or 0),
        "recent_requests": [
            {
                "id": s.id,
                "client_name": _client_name(c),
                "service_type": s.service_type,
                "status": s.status,
                "created_at": _iso(s.created_at),
            }
            for s, c in recent_requests
        ],
        "recent_messages": [
            {
                "id": m.id,
                "client_name": _client_name(c),
                "subject": m.subject,
                "is_read": bool(m.is_read),
                "created_at": _iso(m.created_at),
            }
            for m, c in recent_messages
        ],
    }


# ════════════════════════════════════════════════════════════════════════════════
# PROJECTS & SERVICE REQUESTS
# ════════════════════════════════════════════════════════════════════════════════

@router.get("/projects/")
async def list_projects(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = (
        db.query(ConsoleService, ConsoleClient)
        .join(ConsoleClient, ConsoleService.client_id == ConsoleClient.id)
        .order_by(ConsoleService.created_at.desc())
        .all()
    )
    return {"items": [_service_row(s, c) for s, c in rows]}


@router.patch("/projects/{service_id}/")
async def update_project(
    service_id: int,
    body: ProjectUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = _get_service(db, service_id)
    service.status = body.status
    service.current_phase = body.current_phase.strip()
    service.progress_percentage = body.progress_percentage
    service.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(service)
    client = _get_client(db, service.client_id)
    return {"status": "success", "message": "Project updated successfully.", "item": _service_row(service, client)}


@router.get("/service-requests/")
async def list_service_requests(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = (
        db.query(ConsoleService, ConsoleClient)
        .join(ConsoleClient, ConsoleService.client_id == ConsoleClient.id)
        .filter(ConsoleService.status == "Pending")
        .order_by(ConsoleService.created_at.desc())
        .all()
    )
    return {"items": [_service_row(s, c) for s, c in rows]}


@router.post("/service-requests/{service_id}/approve/")
async def approve_request(
    service_id: int,
    body: ApproveIn,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = _get_service(db, service_id)
    if service.status != "Pending":
        raise HTTPException(status_code=409, detail="This request has already been processed.")

    service.status = "Active"
    service.current_phase = "Discovery"
    service.progress_percentage = 10
    service.updated_at = datetime.now(timezone.utc)
    db.add(ConsoleTransaction(
        service_id=service.id,
        amount=Decimal(body.amount).quantize(Decimal("0.01")),
        reference=_new_reference("INV"),
        status="Pending",
    ))
    db.commit()
    return {"status": "success", "message": "Request approved and invoice generated."}


@router.post("/service-requests/{service_id}/reject/")
async def reject_request(service_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    service = _get_service(db, service_id)
    if service.status != "Pending":
        raise HTTPException(status_code=409, detail="This request has already been processed.")
    service.status = "Cancelled"
    service.current_phase = "Rejected"
    service.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "success", "message": "Service request rejected."}


# ════════════════════════════════════════════════════════════════════════════════
# CLIENTS & MESSAGES
# ════════════════════════════════════════════════════════════════════════════════

@router.get("/clients/")
async def list_clients(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    clients = db.query(ConsoleClient).order_by(ConsoleClient.first_name.asc()).all()
    return {"items": [{"id": c.id, "client_name": _client_name(c), "email": c.email} for c in clients]}


@router.get("/messages/")
async def list_messages(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = (
        db.query(ConsoleMessage, ConsoleClient)
        .join(ConsoleClient, ConsoleMessage.client_id == ConsoleClient.id)
        .order_by(ConsoleMessage.created_at.desc())
        .all()
    )
    return {"items": [_message_row(m, c) for m, c in rows]}


@router.post("/messages/", status_code=201)
async def send_message(body: MessageIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    client = _get_client(db, body.client_id)
    message = ConsoleMessage(
        client_id=client.id,
        sender="admin",
        subject=body.subject.strip(),
        body=body.message.strip(),
        is_read=False,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return {"status": "success", "message": "Reply sent.", "item": _message_row(message, client)}


@router.post("/messages/broadcast/", status_code=201)
async def broadcast_message(body: BroadcastMessageIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    clients = db.query(ConsoleClient).all()
    if not clients:
        raise HTTPException(status_code=400, detail="There are no clients to message yet.")
    subject = body.subject.strip()
    text = body.message.strip()
    for client in clients:
        db.add(ConsoleMessage(client_id=client.id, sender="admin", subject=subject, body=text, is_read=False))
    db.commit()
    return {"status": "success", "message": f"Broadcast delivered to {len(clients)} client(s).", "recipients": len(clients)}


@router.post("/messages/{message_id}/read/")
async def mark_message_read(message_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    message = db.query(ConsoleMessage).filter(ConsoleMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found.")
    if message.sender == "client":
        message.is_read = True
        db.commit()
    return {"status": "success"}


# ════════════════════════════════════════════════════════════════════════════════
# SHARED FILES
# ════════════════════════════════════════════════════════════════════════════════

@router.get("/files/")
async def list_files(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = (
        db.query(ConsoleFile, ConsoleClient, ConsoleService)
        .join(ConsoleClient, ConsoleFile.client_id == ConsoleClient.id)
        .outerjoin(ConsoleService, ConsoleFile.service_id == ConsoleService.id)
        .order_by(ConsoleFile.created_at.desc())
        .all()
    )
    return {
        "items": [
            {
                "id": f.id,
                "client_id": c.id,
                "client_name": _client_name(c),
                "tracking_reference": s.tracking_reference if s else None,
                "original_name": f.original_name,
                "file_type": f.file_type,
                "file_size": f.file_size,
                "uploaded_by": f.uploaded_by,
                "created_at": _iso(f.created_at),
            }
            for f, c, s in rows
        ]
    }


@router.post("/files/", status_code=201)
async def upload_file(
    client_id: int = Form(...),
    service_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    client = _get_client(db, client_id)
    name = (file.filename or "").strip()
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File type not allowed. Use PDF, DOC, PPT, image or ZIP files.")

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 20MB.")
    if not data:
        raise HTTPException(status_code=400, detail="The file is empty.")

    if service_id:
        service = _get_service(db, service_id)
        if service.client_id != client.id:
            raise HTTPException(status_code=400, detail="That project does not belong to this client.")

    record = ConsoleFile(
        client_id=client.id,
        service_id=service_id or None,
        uploaded_by="admin",
        original_name=name[:255],
        file_type=ext,
        content_type=file.content_type or "application/octet-stream",
        file_size=len(data),
        data=data,
    )
    db.add(record)
    db.commit()
    return {"status": "success", "message": "File uploaded and shared with the client.", "id": record.id}


@router.get("/files/{file_id}/download/")
async def download_file(file_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    record = db.query(ConsoleFile).filter(ConsoleFile.id == file_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="File not found.")
    return Response(
        content=record.data,
        media_type=record.content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(record.original_name)}"},
    )


@router.delete("/files/{file_id}/")
async def delete_file(file_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    record = db.query(ConsoleFile).filter(ConsoleFile.id == file_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="File not found.")
    db.delete(record)
    db.commit()
    return {"status": "success", "message": "File deleted."}


# ════════════════════════════════════════════════════════════════════════════════
# CONTACT SUBMISSIONS
# ════════════════════════════════════════════════════════════════════════════

@router.get("/contacts/")
async def list_contacts(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(ContactMessage).order_by(ContactMessage.created_at.desc()).all()
    return {"items": [_contact_row(c) for c in rows]}


@router.post("/contacts/{contact_id}/read/")
async def mark_contact_read(contact_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    contact = db.query(ContactMessage).filter(ContactMessage.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Message not found.")
    contact.is_read = True
    db.commit()
    return {"status": "success"}


@router.delete("/contacts/{contact_id}/")
async def delete_contact(contact_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    contact = db.query(ContactMessage).filter(ContactMessage.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Message not found.")
    db.delete(contact)
    db.commit()
    return {"status": "success", "message": "Message deleted."}


# ════════════════════════════════════════════════════════════════════════════════
# NEWSLETTER & BROADCASTS
# ════════════════════════════════════════════════════════════════════════════════

@router.get("/newsletters/")
async def list_subscribers(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(NewsletterSubscriber).order_by(NewsletterSubscriber.created_at.desc()).all()
    return {
        "total": len(rows),
        "items": [{"id": s.id, "email": s.email, "created_at": _iso(s.created_at)} for s in rows],
    }


@router.delete("/newsletters/{subscriber_id}/")
async def delete_subscriber(subscriber_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    sub = db.query(NewsletterSubscriber).filter(NewsletterSubscriber.id == subscriber_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscriber not found.")
    db.delete(sub)
    db.commit()
    return {"status": "success", "message": "Subscriber removed."}


@router.get("/broadcasts/")
async def list_broadcasts(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(ConsoleBroadcast).order_by(ConsoleBroadcast.created_at.desc()).limit(20).all()
    return {
        "items": [
            {"id": b.id, "subject": b.subject, "recipient_count": b.recipient_count, "created_at": _iso(b.created_at)}
            for b in rows
        ]
    }


def _deliver_newsletter(recipients: List[str], subject: str, html: str) -> None:
    """Runs in the background so the request returns straight away."""
    sent = 0
    for email in recipients:
        try:
            if email_sender._send_email(email, subject, html):
                sent += 1
        except Exception:  # keep going for the rest of the list
            logger.exception("Newsletter send failed for %s", email)
    logger.info("[Console] Newsletter '%s' delivered to %d of %d recipients", subject, sent, len(recipients))


@router.post("/broadcasts/", status_code=201)
async def send_broadcast(
    body: NewsletterBroadcastIn,
    background_tasks: BackgroundTasks,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    recipients = [s.email for s in db.query(NewsletterSubscriber).all()]
    if not recipients:
        raise HTTPException(status_code=400, detail="There are no newsletter subscribers yet.")

    subject = body.subject.strip()
    db.add(ConsoleBroadcast(subject=subject, body=body.message, recipient_count=len(recipients)))
    db.commit()

    background_tasks.add_task(_deliver_newsletter, recipients, subject, body.message)
    return {
        "status": "success",
        "message": f"Newsletter is being sent to {len(recipients)} subscriber(s).",
        "recipients": len(recipients),
    }


# ════════════════════════════════════════════════════════════════════════════════
# PUBLIC ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════════

@public_router.post("/newsletter/")
async def subscribe_newsletter(body: PublicNewsletterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    exists = db.query(NewsletterSubscriber.id).filter(NewsletterSubscriber.email == email).first()
    if not exists:
        db.add(NewsletterSubscriber(email=email))
        db.commit()
    return {"status": "subscribed", "message": "Thank you for subscribing!"}


@public_router.post("/requests/", status_code=201)
async def submit_service_request(body: PublicRequestIn, db: Session = Depends(get_db)):
    if not verify_captcha(body.captcha_token, body.captcha_answer):
        raise HTTPException(status_code=400, detail="Invalid CAPTCHA. Please try again.")

    try:
        client = _upsert_client(db, name=body.name, email=body.email, phone=body.phone)
        service = ConsoleService(
            client_id=client.id,
            service_type=body.service_type.strip(),
            tracking_reference=_new_reference("AYT"),
            details=(body.details or "").strip() or None,
            status="Pending",
            current_phase="Review",
            progress_percentage=0,
        )
        db.add(service)
        db.commit()
        db.refresh(service)
    except Exception:
        db.rollback()
        logger.exception("Could not save console service request")
        raise HTTPException(status_code=500, detail="Could not submit your request. Please try again.")

    return {
        "status": "received",
        "message": "Your request has been received. We will be in touch shortly.",
        "tracking_reference": service.tracking_reference,
    }
