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
- ServiceTier (pricing tiers for services) - NEW
- ServiceSubscription (active service subscriptions) - NEW
- PromoCode (promotional/discount codes) - NEW
- Achievement (company achievements & milestones) - NEW
- TeamMember (team members & leadership) - NEW
- Quote (inspirational business quotes) - NEW
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, JSON, Text, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


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
    - service_subscriptions: Active service subscriptions
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
    service_subscriptions = relationship("ServiceSubscription", back_populates="user")


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


class ServiceTier(Base):
    """
    Service pricing tier table. NEW MODEL

    Defines pricing tiers for different service types.

    Service Types:
    - website: Website development ($297-$897/month)
    - applications: Mobile/Web app development ($897-$1497/month)
    - consultation: Expert consulting ($100-$300/hour)
    - premium: Enterprise all-in-one ($2,394/month or $50k flat)

    Tiers:
    - starter, professional, advanced, premium

    Fields:
    - id: Primary key
    - service_type: website | applications | consultation | premium
    - tier: starter | professional | advanced | premium
    - monthly_price: Monthly billing price
    - quarterly_price: Quarterly billing price (5% discount)
    - annual_price: Annual billing price (10% discount)
    - fifty_percent_down: 50% down payment option
    - features: JSON array of included features
    - description: Tier description
    - is_active: Whether tier is available
    - created_at, updated_at: Timestamps

    Relationships:
    - subscriptions: Active subscriptions using this tier
    """
    __tablename__ = "service_tiers"

    id = Column(Integer, primary_key=True, index=True)
    service_type = Column(String(50), nullable=False, index=True)  # website, applications, consultation, premium
    tier = Column(String(50), nullable=False, index=True)  # starter, professional, advanced, premium

    # Pricing
    monthly_price = Column(Float, nullable=False)
    quarterly_price = Column(Float)  # 5% discount applied
    annual_price = Column(Float)  # 10% discount applied
    fifty_percent_down = Column(Float)  # 50% down, rest billed monthly

    # Details
    features = Column(JSON)  # List of features included
    description = Column(Text)
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    subscriptions = relationship("ServiceSubscription", back_populates="tier")


class ServiceSubscription(Base):
    """
    Active service subscription table. NEW MODEL

    Tracks user subscriptions to Ayinde services.

    Status:
    - active: Currently active subscription
    - paused: Temporarily paused
    - cancelled: Cancelled by user
    - expired: Subscription period ended

    Fields:
    - id: Primary key
    - user_id: User (FK)
    - tier_id: Service tier (FK)
    - service_type: Type of service (for quick lookup)
    - tier_name: Tier name (for quick lookup)
    - status: active | paused | cancelled | expired
    - payment_option: monthly | quarterly | annual | fifty_percent_down
    - amount: Amount billed
    - currency: Currency (USD, NGN, etc)
    - promo_code: Applied promo code (if any)
    - discount_amount: Discount applied
    - started_at: When subscription started
    - expires_at: When subscription expires
    - next_billing_date: When next payment is due
    - payment_method_id: Saved payment method
    - transaction_id: Transaction reference
    - cancelled_at: When cancelled (if applicable)
    - created_at, updated_at: Timestamps

    Relationships:
    - user: User who has subscription
    - tier: Service tier subscribed to
    """
    __tablename__ = "service_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tier_id = Column(Integer, ForeignKey("service_tiers.id"), nullable=False, index=True)

    # Service details (cached for quick lookup)
    service_type = Column(String(50), nullable=False, index=True)  # website, applications, consultation, premium
    tier_name = Column(String(50), nullable=False)  # starter, professional, advanced, premium

    # Subscription status
    status = Column(String(50), default="active", index=True)  # active, paused, cancelled, expired
    payment_option = Column(String(50), nullable=False)  # monthly, quarterly, annual, fifty_percent_down

    # Pricing
    amount = Column(Float, nullable=False)  # Amount for current billing cycle
    currency = Column(String(3), default="USD")
    promo_code = Column(String(100))  # Applied promotional code
    discount_amount = Column(Float, default=0.0)  # Discount applied

    # Dates
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)  # When subscription period ends
    next_billing_date = Column(DateTime)  # When next payment is due

    # Payment
    payment_method_id = Column(String(255))  # Saved payment method (Square nonce)
    transaction_id = Column(String(255), index=True)  # Transaction reference

    # Cancellation
    cancelled_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="service_subscriptions")
    tier = relationship("ServiceTier", back_populates="subscriptions")


class PromoCode(Base):
    """
    Promotional code table. NEW MODEL

    Manages promotional and discount codes.

    Code Types:
    - percentage: Discount by percentage (e.g., 10%)
    - fixed: Fixed discount amount (e.g., $10 off)
    - free_trial: Free trial extension

    Status:
    - active: Code is active and can be used
    - inactive: Code is inactive
    - expired: Code has expired

    Fields:
    - id: Primary key
    - code: Promotional code (e.g., "SAVE10")
    - discount_type: percentage | fixed | free_trial
    - discount_value: Discount value (10 for 10%, $10 for fixed, days for trial)
    - max_uses: Maximum number of times code can be used
    - times_used: Number of times code has been used
    - valid_from: When code becomes valid
    - valid_until: When code expires
    - applicable_services: JSON list of applicable service types (empty = all)
    - status: active | inactive | expired
    - created_at, updated_at: Timestamps

    Relationships:
    - None (used by subscriptions via promo_code field)
    """
    __tablename__ = "promo_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False, index=True)  # SAVE10, WELCOME20, etc

    # Discount details
    discount_type = Column(String(50), nullable=False)  # percentage, fixed, free_trial
    discount_value = Column(Float, nullable=False)  # 10 (for %), $10, or days

    # Usage limits
    max_uses = Column(Integer)  # NULL = unlimited
    times_used = Column(Integer, default=0)

    # Validity period
    valid_from = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    valid_until = Column(DateTime)

    # Restrictions
    applicable_services = Column(JSON)  # NULL = all services, ["website", "premium"] = specific services

    # Status
    status = Column(String(50), default="active", index=True)  # active, inactive, expired

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


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
    - tier: Service tier (starter, professional, advanced, premium)
    - tier_name: Human-readable tier name
    - amount: Service amount/price
    - currency: Currency (USD, NGN, etc)
    - payment_option: Payment option (monthly, quarterly, annual, fifty_percent_down)
    - discount_percent: Discount percentage applied
    - period: Billing period
    - status: pending, in_progress, completed, cancelled, active
    - payment_status: pending, completed, failed
    - payment_method: Payment method used (square, etc)
    - payment_source_id: Payment source ID
    - transaction_id: Transaction reference
    - service_starts_at: When service starts
    - service_ends_at: When service ends
    - payment_completed_at: When payment was completed
    - full_name, email, phone, company: Customer info
    - postal_code, country: Address
    - order_metadata: Additional metadata (JSON)
    - cancelled_at: When cancelled (if applicable)
    - created_at, updated_at: Timestamps

    Relationships:
    - user: User who placed the order
    """
    __tablename__ = "service_orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Service details
    service_type = Column(String(255), nullable=False, index=True)  # website, applications, consultation, premium
    tier = Column(String(50))  # starter, professional, advanced, premium
    tier_name = Column(String(255))

    # Pricing
    amount = Column(Float, default=0.0)
    currency = Column(String(3), default="USD")
    payment_option = Column(String(50))  # monthly, quarterly, annual, fifty_percent_down
    discount_percent = Column(Integer, default=0)
    period = Column(String(50))

    # Status
    status = Column(String(50), default="pending", index=True)  # pending, in_progress, completed, cancelled, active
    payment_status = Column(String(50), default="pending")  # pending, completed, failed

    # Payment
    payment_method = Column(String(50))  # square, etc
    payment_source_id = Column(String(255))
    transaction_id = Column(String(255), index=True)
    payment_completed_at = Column(DateTime)

    # Service period
    service_starts_at = Column(DateTime)
    service_ends_at = Column(DateTime)

    # Customer info
    full_name = Column(String(255))
    email = Column(String(255))
    phone = Column(String(20))
    company = Column(String(255))
    postal_code = Column(String(20))
    country = Column(String(100), default="US")

    # Metadata
    order_metadata = Column(JSON)

    # Timestamps
    cancelled_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="service_orders")


class Achievement(Base):
    """
    Company achievements & milestones table.

    Displays company achievements, awards, and key metrics.

    Fields:
    - id: Primary key
    - title: Achievement title (e.g., "500+ Successful Projects Delivered")
    - description: Achievement description
    - category: Achievement category (general, award, metric, etc)
    - icon: Emoji or icon for display
    - order: Display order on page
    - is_active: Whether achievement is displayed
    - created_at, updated_at: Timestamps
    """
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(50), default="general")  # general, award, metric
    icon = Column(String(10), default="🎯")  # Emoji
    order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class TeamMember(Base):
    """
    Team member profile table.

    Displays company leadership and team members.

    Fields:
    - id: Primary key
    - name: Full name
    - title: Job title/position
    - quote: Leadership quote or statement
    - achievement: Key achievement or accomplishment
    - image: Emoji or image representation
    - gender: male | female (for UI grouping)
    - category: leadership | team | consultant
    - order: Display order on page
    - is_active: Whether member is displayed
    - created_at, updated_at: Timestamps
    """
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    quote = Column(Text, nullable=False)
    achievement = Column(Text)
    image = Column(String(10), default="👤")  # Emoji
    gender = Column(String(20), default="other")  # male, female, other
    category = Column(String(50), default="team")  # leadership, team, consultant
    order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Quote(Base):
    """
    Inspirational business quotes table.

    Displays motivational and inspirational business quotes.

    Fields:
    - id: Primary key
    - text: Quote text
    - author: Quote author name
    - image_url: URL to author image
    - category: Quote category (business, leadership, growth, success, etc)
    - order: Display order on page
    - is_active: Whether quote is displayed
    - created_at, updated_at: Timestamps
    """
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    author = Column(String(255), nullable=False)
    image_url = Column(String(512))  # URL to author image
    category = Column(String(50), default="business")  # business, leadership, growth, success, motivation
    order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    image_url = Column(String(500), nullable=True)
    link = Column(String(500), nullable=True)
    github_link = Column(String(500), nullable=True)
    technologies = Column(String(500), nullable=True)
    order = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ContactMessage(Base):
    """
    Contact form submissions table.
    
    Stores messages from the contact form on the website.
    
    Fields:
    - id: Primary key
    - name: Sender's name
    - email: Sender's email
    - subject: Message subject
    - message: Message content
    - created_at: When message was submitted
    """
    __tablename__ = "contact_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))