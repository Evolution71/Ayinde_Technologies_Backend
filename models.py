from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timedelta

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    enrollments = relationship("CourseEnrollment", back_populates="user")
    payments = relationship("Payment", back_populates="user")

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(String)
    price = Column(Float)
    currency = Column(String, default="USD")
    level = Column(String)
    duration = Column(String)
    instructor = Column(String)
    icon = Column(String, nullable=True)
    trial_duration_days = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    enrollments = relationship("CourseEnrollment", back_populates="course")
    lessons = relationship("Lesson", back_populates="course")

class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    status = Column(String, default="trial")  # trial, active, expired, payment_failed
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    trial_ends_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=30))
    access_expires_at = Column(DateTime, nullable=True)  # ✅ NEW: subscription end
    payment_method_id = Column(String, nullable=True)  # ✅ NEW: Square token
    auto_charge_attempted = Column(Boolean, default=False)  # ✅ NEW: prevent duplicate charges
    
    user = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")
    progress = relationship("LessonProgress", back_populates="enrollment")

class Lesson(Base):
    __tablename__ = "lessons"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    title = Column(String)
    description = Column(String, nullable=True)
    video_url = Column(String, nullable=True)
    order = Column(Integer)
    course = relationship("Course", back_populates="lessons")
    progress = relationship("LessonProgress", back_populates="lesson")

class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    id = Column(Integer, primary_key=True)
    enrollment_id = Column(Integer, ForeignKey("course_enrollments.id"))
    lesson_id = Column(Integer, ForeignKey("lessons.id"))
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    
    enrollment = relationship("CourseEnrollment", back_populates="progress")
    lesson = relationship("Lesson", back_populates="progress")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    amount = Column(Float)
    status = Column(String, default="pending")  # pending, success, failed
    payment_method = Column(String)  # square_tokenize, square_auto_charge
    square_payment_id = Column(String, nullable=True)
    tx_ref = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="payments")

class SubscriptionCharge(Base):
    __tablename__ = "subscription_charges"
    id = Column(Integer, primary_key=True)
    enrollment_id = Column(Integer, ForeignKey("course_enrollments.id"))
    amount = Column(Float)
    status = Column(String, default="pending")  # pending, success, failed
    square_payment_id = Column(String, nullable=True)
    attempted_at = Column(DateTime, default=datetime.utcnow)
    next_retry_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)