"""
Admin console tables (client management).

These tables back the admin console at /console in the React site. They mirror
the tables of the PHP admin dashboard so the data model stays familiar:

    PHP table               -> SQLAlchemy model / Postgres table
    ---------------------------------------------------------------
    clients                 -> ConsoleClient       (console_clients)
    client_services         -> ConsoleService      (console_services)
    transactions            -> ConsoleTransaction  (console_transactions)
    messages                -> ConsoleMessage      (console_messages)
    shared_files            -> ConsoleFile         (console_files)
    newsletter_subscriptions-> NewsletterSubscriber(newsletter_subscribers)
    (broadcast history)     -> ConsoleBroadcast    (console_broadcasts)

Contact submissions use the existing ContactMessage model in models.py.

Imported by routers/console.py, so the tables are registered on Base before
Base.metadata.create_all() runs in main.py.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


def _now():
    return datetime.now(timezone.utc)


class ConsoleClient(Base):
    """A client the agency works with. Matched by email."""

    __tablename__ = "console_clients"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False, default="")
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=_now)

    services = relationship("ConsoleService", back_populates="client", cascade="all, delete-orphan")
    messages = relationship("ConsoleMessage", back_populates="client", cascade="all, delete-orphan")
    files = relationship("ConsoleFile", back_populates="client", cascade="all, delete-orphan")


class ConsoleService(Base):
    """
    A client service request / project.

    Status flow (same as the PHP dashboard):
        Pending -> Active (approved, invoice created) -> Completed
        Pending -> Cancelled (rejected)
    """

    __tablename__ = "console_services"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("console_clients.id", ondelete="CASCADE"), nullable=False, index=True)
    service_type = Column(String(100), nullable=False)
    tracking_reference = Column(String(40), unique=True, nullable=False)
    details = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="Pending", index=True)
    current_phase = Column(String(100), nullable=False, default="Review")
    progress_percentage = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    client = relationship("ConsoleClient", back_populates="services")
    transactions = relationship("ConsoleTransaction", back_populates="service", cascade="all, delete-orphan")


class ConsoleTransaction(Base):
    """An invoice / payment line for a service. Status: Pending, Successful, Failed."""

    __tablename__ = "console_transactions"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("console_services.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    reference = Column(String(60), unique=True, nullable=False)
    status = Column(String(20), nullable=False, default="Pending", index=True)
    created_at = Column(DateTime, default=_now)

    service = relationship("ConsoleService", back_populates="transactions")


class ConsoleMessage(Base):
    """A message in a client thread. sender is 'admin' or 'client'."""

    __tablename__ = "console_messages"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("console_clients.id", ondelete="CASCADE"), nullable=False, index=True)
    sender = Column(String(10), nullable=False)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=_now)

    client = relationship("ConsoleClient", back_populates="messages")


class ConsoleFile(Base):
    """
    A shared file (deliverable or client asset).

    The bytes are stored in the database (BYTEA). Keep uploads small (20 MB limit).
    """

    __tablename__ = "console_files"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("console_clients.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(Integer, ForeignKey("console_services.id", ondelete="SET NULL"), nullable=True, index=True)
    uploaded_by = Column(String(10), nullable=False, default="admin")
    original_name = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False, default="")
    content_type = Column(String(120), nullable=False, default="application/octet-stream")
    file_size = Column(Integer, nullable=False, default=0)
    data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=_now)

    client = relationship("ConsoleClient", back_populates="files")


class NewsletterSubscriber(Base):
    """Public newsletter list (the PHP newsletter_subscriptions table)."""

    __tablename__ = "newsletter_subscribers"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=_now)


class ConsoleBroadcast(Base):
    """History of newsletter broadcasts sent from the console."""

    __tablename__ = "console_broadcasts"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    recipient_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=_now)
