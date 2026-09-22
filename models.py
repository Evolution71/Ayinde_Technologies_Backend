"""
SQLAlchemy models for Ayinde Technologies API.
Includes courses with lessons, pricing, and payment tracking.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta
import enum
from database import Base


# ========== Users & Auth ==========

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    enrollments = relationship("CourseEnrollment", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    progress = relationship("LessonProgress", back_populates="user", cascade="all, delete-orphan")


# ========== Courses & Learning ==========

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=False)
    level = Column(String, default="Beginner")  # Beginner, Intermediate, Advanced
    duration = Column(String, nullable=False)  # e.g., "4 weeks"
    icon = Column(String, nullable=False)  # URL to icon
    instructor = Column(String, nullable=True)
    
    # Pricing
    price = Column(Float, default=100.0)  # $100 USD
    currency = Column(String, default="USD")
    trial_duration_days = Column(Integer, default=30)  # 1-month free trial
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    lessons = relationship("Lesson", back_populates="course", cascade="all, delete-orphan")
    enrollments = relationship("CourseEnrollment", back_populates="course", cascade="all, delete-orphan")


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    order = Column(Integer, nullable=False)  # Lesson sequence
    
    # Content
    video_url = Column(String, nullable=True)  # Supabase Storage or Mux URL
    duration_minutes = Column(Integer, nullable=True)
    content_html = Column(Text, nullable=True)  # Rich text/markdown
    resources = Column(JSON, nullable=True)  # [{name: "PDF", url: "..."}, ...]
    
    # Quiz/Assessment
    has_quiz = Column(Boolean, default=False)
    quiz_data = Column(JSON, nullable=True)  # {questions: [...]}
    
    is_published = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    course = relationship("Course", back_populates="lessons")
    progress = relationship("LessonProgress", back_populates="lesson", cascade="all, delete-orphan")


class LessonProgress(Base):
    __tablename__ = "lesson_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    
    is_completed = Column(Boolean, default=False)
    time_spent_seconds = Column(Integer, default=0)
    quiz_score = Column(Float, nullable=True)  # 0-100
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    last_accessed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="progress")
    lesson = relationship("Lesson", back_populates="progress")


# ========== Enrollment & Access ==========

class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    
    # Status
    status = Column(String, default="trial")  # trial / active / expired / cancelled
    
    # Dates
    enrolled_at = Column(DateTime, server_default=func.now())
    trial_ends_at = Column(DateTime, nullable=True)  # Set to 30 days from now
    access_expires_at = Column(DateTime, nullable=True)  # For paid subscriptions
    
    # Progress
    progress_percentage = Column(Float, default=0.0)
    last_accessed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")
    payments = relationship("Payment", back_populates="enrollment")


# ========== Payments (Square) ==========

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    enrollment_id = Column(Integer, ForeignKey("course_enrollments.id"), nullable=True)
    
    # Transaction Reference
    tx_ref = Column(String, unique=True, index=True, nullable=False)  # ← ADDED THIS
    
    # Square Transaction Fields
    square_payment_id = Column(String, unique=True, index=True, nullable=True)  # Square payment ID (nonce)
    square_receipt_url = Column(String, nullable=True)  # Square receipt/receipt URL
    amount = Column(Float, nullable=False)  # Amount in dollars
    currency = Column(String, default="USD")  # USD, etc.
    
    # Status
    status = Column(String, default="pending")  # pending / success / failed / cancelled
    payment_method = Column(String, nullable=True)  # card / apple_pay / google_pay / etc.
    
    # Metadata (using payment_data instead of metadata to avoid SQLAlchemy reserved word)
    payment_data = Column(JSON, nullable=True)  # {course_id, user_email, user_name, idempotency_key, ...}
    
    # Dates
    created_at = Column(DateTime, server_default=func.now())
    verified_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # Payment intent expiry

    # Relationships
    user = relationship("User", back_populates="payments")
    enrollment = relationship("CourseEnrollment", back_populates="payments")


# ========== Services & Team ==========

class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    icon = Column(String, nullable=False)
    features = Column(JSON, nullable=False)  # List of strings
    created_at = Column(DateTime, server_default=func.now())


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    bio = Column(Text, nullable=False)
    image = Column(String, nullable=False)
    expertise = Column(JSON, nullable=False)  # List of strings
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    client = Column(String, nullable=False)
    category = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    image = Column(String, nullable=False)
    technologies = Column(JSON, nullable=False)  # List of strings
    results = Column(JSON, nullable=False)  # List of strings
    app_url = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# ========== Contact ==========

class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    company = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    read = Column(Boolean, default=False)  