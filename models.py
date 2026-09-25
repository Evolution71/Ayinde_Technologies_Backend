from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, Enum, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

# ========== USER MODEL ==========
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, default="")
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)  # ✅ ROUTER EXPECTS THIS NAME
    created_at = Column(DateTime, default=datetime.utcnow)

# ========== COURSE MODEL ==========
class Course(Base):
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Float, default=0)
    currency = Column(String(10), default="USD")
    icon = Column(String(255), nullable=True)
    instructor = Column(String(255), nullable=True)
    duration = Column(String(100), nullable=True)
    level = Column(String(50), default="Beginner")
    is_active = Column(Boolean, default=True)  # ✅ ROUTER NEEDS THIS
    trial_duration_days = Column(Integer, default=30)  # ✅ ROUTER NEEDS THIS
    trial_end_date = Column(DateTime, nullable=True)  # ✅ ROUTER NEEDS THIS
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ========== COURSE ENROLLMENT MODEL (Routers expect this name) ==========
class CourseEnrollment(Base):
    __tablename__ = "enrollments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    status = Column(String(50), default="trial")  # 'trial', 'active', 'expired', 'payment_failed'
    trial_ends_at = Column(DateTime, nullable=True)
    access_expires_at = Column(DateTime, nullable=True)
    enrolled_at = Column(DateTime, default=datetime.utcnow)  # When enrollment started
    progress_percentage = Column(Float, default=0)  # Overall course progress
    last_accessed_at = Column(DateTime, nullable=True)  # Last time accessed
    payment_method_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ========== LESSON MODEL ==========
class Lesson(Base):
    __tablename__ = "lessons"
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    content_html = Column(Text, nullable=True)  # HTML content
    video_url = Column(String(255), nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    order = Column(Integer, default=0)
    resources = Column(JSON, nullable=True)  # Store resources as JSON
    has_quiz = Column(Boolean, default=False)
    quiz_data = Column(JSON, nullable=True)  # Store quiz data as JSON
    is_published = Column(Boolean, default=False)  # ✅ REQUIRED BY ROUTER
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ========== LESSON PROGRESS MODEL (Routers expect this name) ==========
class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    is_completed = Column(Boolean, default=False)
    progress_percentage = Column(Float, default=0)
    time_spent_seconds = Column(Integer, default=0)  # Track time spent
    quiz_score = Column(Float, nullable=True)  # Quiz score if completed
    completed_at = Column(DateTime, nullable=True)  # When lesson was completed
    last_accessed_at = Column(DateTime, nullable=True)  # Last time accessed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ========== PAYMENT MODEL ==========
class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USD")
    status = Column(String(50), default="pending")  # pending, completed, failed
    payment_method = Column(String(100))  # square, flutterwave, paystack
    transaction_id = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ========== CAPTCHA MODEL ==========
class Captcha(Base):
    __tablename__ = "captchas"
    
    id = Column(String(36), primary_key=True, index=True)
    challenge = Column(String(10), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

# ========== SERVICE MODEL ==========
class Service(Base):
    __tablename__ = "services"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    icon = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ========== TEAM MEMBER MODEL ==========
class TeamMember(Base):
    __tablename__ = "team_members"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    role = Column(String(255))
    bio = Column(Text)
    image = Column(String(255), nullable=True)
    expertise = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ========== PROJECT MODEL ==========
class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    client = Column(String(255))
    category = Column(String(100))
    description = Column(Text)
    image = Column(String(255), nullable=True)
    technologies = Column(Text)
    results = Column(Text)
    app_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ========== CONTACT MESSAGE MODEL ==========
class ContactMessage(Base):
    __tablename__ = "contact_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    subject = Column(String(255))
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# ========== SERVICE ORDER MODEL (Premium Services) ==========
class ServiceOrder(Base):
    """Premium service order model for Website Pro, Application Pro, and Supreme VIP Platinum"""
    __tablename__ = "service_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Service details
    tier = Column(String(50), nullable=False)  # website, application, supreme
    tier_name = Column(String(255), nullable=False)  # "Website Pro", "Application Pro", etc.
    amount = Column(Float, nullable=False)  # Price in USD
    currency = Column(String(10), default="USD")
    payment_option = Column(String(50))  # monthly, annual, threeyear, halfdown
    discount_percent = Column(Integer, default=0)  # 0, 5, 10, 20
    period = Column(String(100))  # "/month", "/2 years", "/3 years", etc.
    
    # Billing information
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    company = Column(String(255), nullable=True)
    postal_code = Column(String(20), nullable=False)
    country = Column(String(2), default="US")
    
    # Service duration
    status = Column(String(50), default="active")  # active, expired, cancelled, suspended
    service_starts_at = Column(DateTime, default=datetime.utcnow)
    service_ends_at = Column(DateTime, nullable=False)  # When service expires
    
    # Payment information
    payment_status = Column(String(50), default="pending")  # pending, completed, failed, refunded
    payment_method = Column(String(50), default="square")  # square, other
    payment_source_id = Column(String(255), nullable=True)  # Square token
    transaction_id = Column(String(255), unique=True, nullable=True)  # Unique transaction ID
    payment_completed_at = Column(DateTime, nullable=True)  # When payment was processed
    
    # Cancellation
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    
    # Additional data
    order_metadata = Column(JSON, default=dict)  # Stores features, IP, user agent, etc.
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)