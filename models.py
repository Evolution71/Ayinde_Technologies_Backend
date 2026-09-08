"""
SQLAlchemy models. This is where the data actually lives now — nothing
about services, team members, projects, or courses is hardcoded into the
route handlers anymore; it's all rows in the database, queried at request
time. `seed.py` inserts starter rows on first run so the site isn't empty,
but from then on it's ordinary database data you can edit like any other.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    enrollments = relationship("Enrollment", back_populates="user")


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    icon = Column(String, nullable=False)
    features = Column(Text, nullable=False)  # comma-separated; split on read


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    bio = Column(Text, nullable=False)
    image = Column(String, nullable=False)
    expertise = Column(Text, nullable=False)  # comma-separated
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)


class Project(Base):
    """
    A built app / project case study. Listing these requires a logged-in
    user — see routers/projects.py.
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    client = Column(String, nullable=False)
    category = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    image = Column(String, nullable=False)
    technologies = Column(Text, nullable=False)  # comma-separated
    results = Column(Text, nullable=False)  # comma-separated
    app_url = Column(String, nullable=True)  # link to the live app, if any


class Course(Base):
    """
    An online course. Listing these requires a logged-in user — see
    routers/courses.py.
    """
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    level = Column(String, nullable=False)  # Beginner / Intermediate / Advanced
    duration = Column(String, nullable=False)
    icon = Column(String, nullable=False)
    price = Column(Float, default=15000.0)  # monthly price after the free trial
    currency = Column(String, default="NGN")

    enrollments = relationship("Enrollment", back_populates="course")


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    enrolled_at = Column(DateTime, default=datetime.utcnow)

    # Every enrollment starts with a free trial. is_paid flips to True once a
    # real payment is confirmed (via webhook or verified callback).
    trial_ends_at = Column(DateTime, nullable=True)
    is_paid = Column(Boolean, default=False)
    last_tx_ref = Column(String, nullable=True)
    paid_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")


class Payment(Base):
    """One row per payment attempt, so nothing is only tracked in memory."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    tx_ref = Column(String, unique=True, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending / successful / failed
    flw_transaction_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    company = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
