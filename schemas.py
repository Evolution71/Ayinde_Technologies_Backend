"""Pydantic schemas — request bodies and API response shapes."""

from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------- Auth ----------

class UserRegister(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    captcha_token: str
    captcha_answer: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    captcha_token: str
    captcha_answer: str


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Services / Team ----------

class ServiceOut(BaseModel):
    id: int
    name: str
    description: str
    icon: str
    features: List[str]

    class Config:
        from_attributes = True


class TeamMemberOut(BaseModel):
    id: int
    name: str
    role: str
    bio: str
    image: str
    expertise: List[str]
    email: Optional[str] = None
    phone: Optional[str] = None

    class Config:
        from_attributes = True


# ---------- Projects ----------

class ProjectOut(BaseModel):
    id: int
    title: str
    client: str
    category: str
    description: str
    image: str
    technologies: List[str]
    results: List[str]
    app_url: Optional[str] = None

    class Config:
        from_attributes = True


# ========== COURSES & LEARNING ==========

class LessonOut(BaseModel):
    """Lesson details for enrolled users."""
    id: int
    course_id: int
    title: str
    description: Optional[str] = None
    order: int
    duration_minutes: Optional[int] = None
    video_url: Optional[str] = None
    content_html: Optional[str] = None
    resources: Optional[List[dict]] = None
    has_quiz: bool = False
    
    class Config:
        from_attributes = True


class LessonProgressOut(BaseModel):
    """User's progress on a lesson."""
    id: int
    lesson_id: int
    is_completed: bool
    time_spent_seconds: int
    quiz_score: Optional[float] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class CourseOut(BaseModel):
    """Basic course info for public view."""
    id: int
    title: str
    description: str
    level: str
    duration: str
    icon: str
    instructor: Optional[str] = None
    price: float = 100.0
    currency: str = "USD"
    trial_duration_days: int = 30
    enrolled: bool = False
    access_status: str = "not_enrolled"  # not_enrolled / trial / active / expired
    trial_ends_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CourseDetailOut(CourseOut):
    """Detailed course view with lessons (for enrolled users)."""
    lessons: List[LessonOut] = []
    progress_percentage: float = 0.0
    last_accessed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class CourseEnrollmentOut(BaseModel):
    """Enrollment status."""
    id: int
    course_id: int
    user_id: int
    status: str  # trial / active / expired / cancelled
    enrolled_at: datetime
    trial_ends_at: Optional[datetime] = None
    access_expires_at: Optional[datetime] = None
    progress_percentage: float
    last_accessed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ========== PAYMENTS ==========

class PaymentInitRequest(BaseModel):
    course_id: int
    redirect_url: Optional[str] = None


class PaymentInitResponse(BaseModel):
    status: str  # "success" | "trial_active" | "already_enrolled" | "error"
    message: str
    payment_link: Optional[str] = None
    payment_id: Optional[int] = None


class PaymentVerifyRequest(BaseModel):
    payment_id: int
    transaction_id: str


class PaymentVerifyResponse(BaseModel):
    status: str  # "success" | "error"
    message: str
    course_id: Optional[int] = None
    enrollment_id: Optional[int] = None


class PaymentStatusOut(BaseModel):
    """Payment details."""
    id: int
    status: str  # pending / success / failed / cancelled
    amount: float
    currency: str
    payment_method: Optional[str] = None
    created_at: datetime
    verified_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ---------- Contact ----------

class ContactForm(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = None
    company: Optional[str] = None
    subject: Optional[str] = None
    message: str = Field(min_length=1, max_length=5000)
    captcha_token: str
    captcha_answer: str


class ContactResponse(BaseModel):
    status: str
    message: str


# ---------- Captcha ----------

class CaptchaOut(BaseModel):
    token: str
    image: str