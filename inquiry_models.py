"""
Client inquiry tables, ported from the PHP site (ayinde_tech.sql).

Tables: clients, client_services, transactions, newsletter_subscriptions,
website_development_services, app_development_services,
tech_consultancy_services, premium_services, project_startups.
The PHP `contacts` table is not duplicated here: the existing Contact model handles that form.
"""
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, ForeignKey
from sqlalchemy.sql import func

from database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ClientService(Base):
    __tablename__ = "client_services"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    service_type = Column(String(100), nullable=False)
    tracking_reference = Column(String(50), nullable=False, unique=True, index=True)
    status = Column(String(30), nullable=False, default="Pending")
    progress_percentage = Column(Integer, nullable=False, default=0)
    current_phase = Column(String(100), nullable=False, default="Onboarding")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    client_service_id = Column(Integer, ForeignKey("client_services.id"), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    transaction_reference = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="Pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class NewsletterSubscription(Base):
    __tablename__ = "newsletter_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    status = Column(String(50), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class _PlanDetail(object):
    """Shared columns for the plan-based service tables."""
    id = Column(Integer, primary_key=True, index=True)
    client_service_id = Column(Integer, ForeignKey("client_services.id"), nullable=False, index=True)
    plan_tier = Column(String(50), nullable=False)
    project_description = Column(Text, nullable=False)
    payment_status = Column(String(20), nullable=False, default="Unpaid")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WebDevelopmentService(_PlanDetail, Base):
    __tablename__ = "website_development_services"


class AppDevelopmentService(_PlanDetail, Base):
    __tablename__ = "app_development_services"


class TechConsultancyService(_PlanDetail, Base):
    __tablename__ = "tech_consultancy_services"


class PremiumService(Base):
    __tablename__ = "premium_services"

    id = Column(Integer, primary_key=True, index=True)
    client_service_id = Column(Integer, ForeignKey("client_services.id"), nullable=False, index=True)
    company_name = Column(String(150), nullable=False)
    plan_tier = Column(String(50), nullable=False)
    project_description = Column(Text, nullable=False)
    document_link = Column(String(255), nullable=True)
    payment_status = Column(String(20), nullable=False, default="Unpaid")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ProjectStartup(Base):
    __tablename__ = "project_startups"

    id = Column(Integer, primary_key=True, index=True)
    client_service_id = Column(Integer, ForeignKey("client_services.id"), nullable=False, index=True)
    company_name = Column(String(150), nullable=True)
    service_type = Column(String(100), nullable=False)
    budget_range = Column(String(50), nullable=False)
    project_details = Column(Text, nullable=False)
    attachments = Column(Text, nullable=True)  # JSON list of file names
    created_at = Column(DateTime(timezone=True), server_default=func.now())
