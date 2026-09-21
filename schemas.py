"""
Pydantic schemas for Ayinde Technologies API.
All request/response models with validators for list fields.
"""

from pydantic import BaseModel, Field, field_validator, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime


# ========== TOKEN SCHEMAS ==========

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[str] = None


# ========== AUTH SCHEMAS ==========

class UserBase(BaseModel):
    name: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserRegister(BaseModel):
    """Schema for user registration - includes captcha fields"""
    name: str
    email: EmailStr
    password: str
    captcha_token: Optional[str] = None
    captcha_answer: Optional[str] = None

class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str
    captcha_token: Optional[str] = None
    captcha_answer: Optional[str] = None

class UserResponse(UserBase):
    """Schema for user response"""
    id: int
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    captcha_token: Optional[str] = None
    captcha_answer: Optional[str] = None

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    captcha_token: Optional[str] = None
    captcha_answer: Optional[str] = None

class AuthResponse(BaseModel):
    """Generic auth response"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ========== LESSON SCHEMAS ==========

class LessonBase(BaseModel):
    title: str
    description: Optional[str] = None
    order: int
    video_url: Optional[str] = None
    duration_minutes: Optional[int] = None
    content_html: Optional[str] = None
    has_quiz: bool = False
    quiz_data: Optional[Dict[str, Any]] = None
    is_published: bool = True

class LessonCreate(LessonBase):
    course_id: int

class LessonResponse(LessonBase):
    id: int
    course_id: int
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class LessonOut(LessonResponse):
    """Alias for LessonResponse - used by lessons.py"""
    pass


# ========== COURSE SCHEMAS ==========

class CourseBase(BaseModel):
    title: str
    description: str
    instructor: Optional[str] = None
    price: float = 100.0
    currency: str = "USD"
    level: str = "Beginner"
    duration: str
    icon: Optional[str] = None
    trial_duration_days: int = 30
    is_active: bool = True

class CourseCreate(CourseBase):
    pass

class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    instructor: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    level: Optional[str] = None
    duration: Optional[str] = None
    icon: Optional[str] = None
    trial_duration_days: Optional[int] = None
    is_active: Optional[bool] = None

class CourseResponse(CourseBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    lessons: List[LessonResponse] = []
    
    class Config:
        from_attributes = True

class CourseListResponse(BaseModel):
    id: int
    title: str
    description: str
    level: str
    duration: str
    icon: Optional[str] = None
    instructor: Optional[str] = None
    price: float
    currency: str
    trial_duration_days: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class CourseDetailResponse(CourseResponse):
    pass

class CourseDetailOut(CourseResponse):
    """Alias for CourseDetailResponse - used by courses.py"""
    pass

class CourseOut(CourseResponse):
    pass


# ========== ENROLLMENT SCHEMAS ==========

class EnrollmentBase(BaseModel):
    user_id: int
    course_id: int
    status: str = "active"

class EnrollmentCreate(EnrollmentBase):
    pass

class EnrollmentResponse(EnrollmentBase):
    id: int
    enrolled_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class CourseEnrollmentOut(EnrollmentResponse):
    """Alias for EnrollmentResponse - used by enrollment endpoints"""
    pass


# ========== SERVICE SCHEMAS ==========

class ServiceBase(BaseModel):
    name: str
    description: str
    icon: Optional[str] = None

class ServiceCreate(ServiceBase):
    pass

class ServiceResponse(ServiceBase):
    id: int
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ServiceOut(ServiceResponse):
    pass


# ========== TEAM MEMBER SCHEMAS ==========

class TeamMemberBase(BaseModel):
    name: str
    role: str
    bio: Optional[str] = None
    image: Optional[str] = None
    expertise: Optional[str] = None

class TeamMemberCreate(TeamMemberBase):
    pass

class TeamMemberResponse(TeamMemberBase):
    id: int
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class TeamMemberOut(TeamMemberResponse):
    pass


# ========== PROJECT SCHEMAS ==========

class ProjectBase(BaseModel):
    title: str
    client: Optional[str] = None
    category: Optional[str] = None
    description: str
    image: Optional[str] = None
    technologies: Optional[str] = None
    results: Optional[str] = None
    app_url: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    id: int
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ProjectOut(ProjectResponse):
    pass


# ========== CONTACT SCHEMAS ==========

class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    subject: str
    message: str

class ContactForm(ContactRequest):
    """Alias for ContactRequest - used by contact.py"""
    pass

class ContactResponse(BaseModel):
    id: int
    name: str
    email: str
    subject: str
    message: str
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ========== PAYMENT SCHEMAS ==========

class PaymentIntentRequest(BaseModel):
    course_id: int
    amount: float = Field(default=0.0)
    currency: str = Field(default="USD")

class PaymentVerificationRequest(BaseModel):
    payment_id: str
    nonce: str

class PaymentResponse(BaseModel):
    id: int
    user_id: int
    course_id: int
    amount: float
    currency: str
    status: str
    square_payment_id: Optional[str] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class PaymentOut(PaymentResponse):
    pass


# ========== CAPTCHA SCHEMAS ==========

class CaptchaResponse(BaseModel):
    success: bool
    score: float
    action: str

class CaptchaOut(CaptchaResponse):
    pass

class CaptchaGenerateResponse(BaseModel):
    """Response when generating a new captcha challenge"""
    captcha_id: str
    captcha_image: Optional[str] = None
    
    class Config:
        from_attributes = True

class CaptchaVerifyResponse(BaseModel):
    """Response when verifying a captcha answer"""
    success: bool
    message: Optional[str] = None
    score: Optional[float] = None
    
    class Config:
        from_attributes = True