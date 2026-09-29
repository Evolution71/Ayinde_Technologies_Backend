"""
SQLAlchemy ORM models for Ayinde Technologies.

Tables:
- User (authentication & profile)
- Course (course catalog)
- CourseEnrollment (user enrollments with trial/subscription tracking)
- Payment (payment records - Square, Flutterwave, etc)
- Lesson (course lessons)
- LessonProgress (user progress tracking)
- FAQ (course FAQs)
- ServiceOrder (service orders/requests from clients)
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, JSON, Text, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

Base = declarative_base()


class User(Base):
    """
    User account table.
    
    Fields:
    - id: Primary key
    - email: Unique email address
    - first_name, last_name: Profile info
    - password_hash: Hashed password (bcrypt)
    - is_active: Account status
    - created_at: Account creation date
    - updated_at: Last update date
    
    Relationships:
    - enrollments: Courses user is enrolled in
    - payments: User's payment history
    - service_orders: Service orders placed by user
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    enrollments = relationship("CourseEnrollment", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    lesson_progress = relationship("LessonProgress", back_populates="user")
    service_orders = relationship("ServiceOrder", back_populates="user")


class Course(Base):
    """
    Course catalog table.
    
    Fields:
    - id: Primary key
    - title: Course name
    - description: Long description
    - price: Course price in USD
    - currency: Currency code (USD, NGN, etc)
    - instructor: Instructor name
    - level: Course level (Beginner, Intermediate, Advanced)
    - duration: Course duration (e.g., "4 weeks")
    - icon: Course icon/image URL
    - trial_duration_days: Free trial duration in days (default 30)
    - is_active: Whether course is active
    - is_published: Visibility
    - created_at, updated_at: Timestamps
    
    Relationships:
    - enrollments: Users enrolled in this course
    - lessons: Course lessons
    - faqs: Course FAQs
    - payments: Payments for this course
    """
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    price = Column(Float, default=0.0)
    currency = Column(String(3), default="USD")
    instructor = Column(String(255))
    level = Column(String(100), default="Beginner")
    duration = Column(String(255))
    icon = Column(String(512))
    trial_duration_days = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    enrollments = relationship("CourseEnrollment", back_populates="course")
    lessons = relationship("Lesson", back_populates="course")
    faqs = relationship("FAQ", back_populates="course")
    payments = relationship("Payment", back_populates="course")


class CourseEnrollment(Base):
    """
    User course enrollment table.
    
    Status:
    - trial: Free trial period (default 30 days)
    - active: Paid access
    - expired: Trial/subscription expired
    - cancelled: User cancelled
    
    Fields:
    - id: Primary key
    - user_id: User (FK)
    - course_id: Course (FK)
    - status: trial, active, expired, cancelled
    - trial_ends_at: When free trial expires
    - access_ends_at: When paid access expires
    - payment_method_id: Saved payment method (Square nonce)
    - progress_percentage: User's progress in course (0-100)
    - auto_charge_attempted: Whether auto-charge was attempted
    - last_accessed_at: Last time user accessed course
    - created_at, updated_at: Timestamps
    
    Relationships:
    - user: User who enrolled
    - course: Course enrolled in
    - payments: Payments for this enrollment
    """
    __tablename__ = "enrollments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    status = Column(String(50), default="trial", index=True)  # trial, active, expired, cancelled
    trial_ends_at = Column(DateTime)
    access_ends_at = Column(DateTime)
    payment_method_id = Column(String(255))  # Square nonce - VARCHAR, not UUID
    progress_percentage = Column(Float, default=0.0)
    auto_charge_attempted = Column(Boolean, default=False)
    last_accessed_at = Column(DateTime)
    enrolled_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")
    payments = relationship("Payment", back_populates="enrollment")
    lesson_progress = relationship("LessonProgress", back_populates="enrollment")


class Payment(Base):
    """
    Payment transaction table.
    
    Supports multiple payment gateways:
    - Square (square_payment_id, square_receipt_url)
    - Flutterwave (flutterwave_transaction_id, flutterwave_reference, flw_transaction_id)
    
    Status:
    - pending: Payment initiated, awaiting verification
    - completed: Payment successful, access granted
    - failed: Payment failed
    - refunded: Payment refunded
    
    Fields:
    - id: Primary key
    - enrollment_id: Enrollment (FK)
    - user_id: User (FK)
    - course_id: Course (FK)
    - tx_ref: Unique transaction reference (for Flutterwave)
    - amount: Amount charged
    - currency: Currency (USD, NGN, etc)
    - status: pending, completed, failed, refunded
    - payment_method: square, flutterwave, paystack, etc
    - payment_link: Payment URL (for Flutterwave redirect)
    - payment_data: Raw response data (JSON)
    
    Square fields:
    - square_payment_id: Square payment ID
    - square_receipt_url: Receipt URL
    
    Flutterwave fields:
    - flutterwave_transaction_id: Flutterwave transaction ID
    - flutterwave_reference: Flutterwave reference
    - flw_transaction_id: Alternative reference
    
    Timestamps:
    - transaction_id: Transaction reference (generic)
    - paid_at: When payment was confirmed
    - verified_at: When payment was verified
    - expires_at: When link expires (Flutterwave)
    - created_at, updated_at: Record timestamps
    
    Relationships:
    - enrollment: Related enrollment
    - user: User who paid
    - course: Course paid for
    """
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    
    # Transaction references
    tx_ref = Column(String(255), unique=True, index=True)  # Flutterwave reference
    transaction_id = Column(String(255), index=True)  # Generic transaction ID
    
    # Amount
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD")  # USD, NGN, etc
    
    # Status and method
    status = Column(String(50), default="pending", index=True)  # pending, completed, failed, refunded
    payment_method = Column(String(50))  # square, flutterwave, paystack
    
    # Payment link (for redirect flows)
    payment_link = Column(String(512))
    payment_data = Column(JSON)  # Raw response from payment gateway
    
    # Square-specific
    square_payment_id = Column(String(255), index=True)
    square_receipt_url = Column(String(512))
    
    # Flutterwave-specific
    flutterwave_transaction_id = Column(String(255), index=True)
    flutterwave_reference = Column(String(255), index=True)
    flw_transaction_id = Column(String(255), index=True)
    
    # Timestamps
    paid_at = Column(DateTime)  # When payment was completed
    verified_at = Column(DateTime)  # When payment was verified
    expires_at = Column(DateTime)  # When payment link expires
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    enrollment = relationship("CourseEnrollment", back_populates="payments")
    user = relationship("User", back_populates="payments")
    course = relationship("Course", back_populates="payments")


class Lesson(Base):
    """
    Course lesson table.
    
    Fields:
    - id: Primary key
    - course_id: Course (FK)
    - title: Lesson title
    - description: Lesson description
    - content: Lesson content (HTML or Markdown)
    - content_html: HTML version of lesson content
    - video_url: Video URL (optional)
    - duration_minutes: Lesson duration in minutes
    - order: Lesson order in course
    - has_quiz: Whether lesson has a quiz
    - quiz_data: Quiz questions/answers (JSON)
    - resources: Lesson resources (JSON or links)
    - is_published: Visibility
    - created_at, updated_at: Timestamps
    
    Relationships:
    - course: Course this lesson belongs to
    - progress: User progress on this lesson
    """
    __tablename__ = "lessons"
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    content = Column(Text)
    content_html = Column(Text)
    video_url = Column(String(512))
    duration_minutes = Column(Integer)
    order = Column(Integer, default=0)
    has_quiz = Column(Boolean, default=False)
    quiz_data = Column(JSON)
    resources = Column(JSON)
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    course = relationship("Course", back_populates="lessons")
    progress = relationship("LessonProgress", back_populates="lesson")


class LessonProgress(Base):
    """
    User lesson progress table.
    
    Tracks completion status for each user-lesson pair.
    
    Fields:
    - id: Primary key
    - user_id: User (FK)
    - enrollment_id: Enrollment (FK)
    - lesson_id: Lesson (FK)
    - is_completed: Lesson completion status
    - completed_at: When lesson was marked complete
    - created_at, updated_at: Timestamps
    
    Relationships:
    - user: User
    - enrollment: Related enrollment
    - lesson: Lesson
    """
    __tablename__ = "lesson_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id"), nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("User", back_populates="lesson_progress")
    enrollment = relationship("CourseEnrollment", back_populates="lesson_progress")
    lesson = relationship("Lesson", back_populates="progress")


class FAQ(Base):
    """
    Course FAQ table.
    
    Fields:
    - id: Primary key
    - course_id: Course (FK)
    - question: FAQ question
    - answer: FAQ answer
    - order: Display order
    - created_at, updated_at: Timestamps
    
    Relationships:
    - course: Course this FAQ belongs to
    """
    __tablename__ = "faqs"
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    question = Column(String(512), nullable=False)
    answer = Column(Text, nullable=False)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    course = relationship("Course", back_populates="faqs")


class ServiceOrder(Base):
    """
    Service order table for custom client services.
    
    Tracks orders for consulting, development, design, and other services.
    
    Status:
    - pending: Order received, awaiting review
    - in_progress: Work started
    - completed: Work completed
    - cancelled: Order cancelled
    
    Fields:
    - id: Primary key
    - user_id: User who placed order (FK)
    - service_type: Type of service (consulting, development, design, etc)
    - title: Order title/name
    - description: Order description/details
    - status: pending, in_progress, completed, cancelled
    - price: Service price
    - currency: Currency (USD, NGN, etc)
    - payment_status: Payment status (unpaid, paid, partially_paid)
    - completed_at: When service was completed
    - created_at, updated_at: Timestamps
    
    Relationships:
    - user: User who placed the order
    """
    __tablename__ = "service_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    service_type = Column(String(255), nullable=False, index=True)  # consulting, development, design, etc
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="pending", index=True)  # pending, in_progress, completed, cancelled
    price = Column(Float, default=0.0)
    currency = Column(String(3), default="USD")
    payment_status = Column(String(50), default="unpaid")  # unpaid, paid, partially_paid
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("User", back_populates="service_orders")