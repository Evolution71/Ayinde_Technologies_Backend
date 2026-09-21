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
    created_at: datetime
    
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


# ========== COURSE SCHEMAS ==========

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
    created_at: datetime
    
    class Config:
        from_attributes = True

class CourseBase(BaseModel):
    title: str
    description: str
    level: str = "Beginner"
    duration: str
    icon: str
    instructor: Optional[str] = None
    price: float = 100.0
    currency: str = "USD"
    trial_duration_days: int = 30
    is_active: bool = True

class CourseCreate(CourseBase):
    pass

class CourseResponse(CourseBase):
    id: int
    created_at: datetime
    updated_at: datetime
    lessons: List[LessonResponse] = []
    
    class Config:
        from_attributes = True

class CourseListResponse(BaseModel):
    id: int
    title: str
    description: str
    level: str
    duration: str
    icon: str
    instructor: Optional[str]
    price: float
    currency: str
    trial_duration_days: int
    is_active: bool
    
    class Config:
        from_attributes = True


# ========== ENROLLMENT SCHEMAS ==========

class EnrollmentBase(BaseModel):
    user_id: int
    course_id: int
    status: str = "trial"

class EnrollmentCreate(EnrollmentBase):
    pass

class EnrollmentResponse(EnrollmentBase):
    id: int
    enrolled_at: datetime
    trial_ends_at: Optional[datetime]
    access_expires_at: Optional[datetime]
    progress_percentage: float
    last_accessed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ========== PAYMENT SCHEMAS ==========

class PaymentInitRequest(BaseModel):
    course_id: int

class PaymentVerifyRequest(BaseModel):
    payment_id: int
    square_payment_id: str
    square_receipt_url: Optional[str] = None

class PaymentResponse(BaseModel):
    id: int
    amount: float
    currency: str
    status: str
    payment_method: Optional[str]
    created_at: datetime
    verified_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ========== TEAM SCHEMAS ==========

class TeamMemberBase(BaseModel):
    name: str
    role: str
    bio: str
    image: str
    expertise: List[str]
    email: Optional[str] = None
    phone: Optional[str] = None

class TeamMemberCreate(TeamMemberBase):
    pass

class TeamMemberResponse(BaseModel):
    """Team member with list validator for expertise"""
    id: int
    name: str
    role: str
    bio: str
    image: str
    expertise: List[str]
    email: Optional[str]
    phone: Optional[str]
    
    @field_validator('expertise', mode='before')
    @classmethod
    def parse_expertise(cls, v):
        """Convert comma-separated string to list if needed."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(',') if item.strip()]
        return v if isinstance(v, list) else []
    
    class Config:
        from_attributes = True


# ========== SERVICE SCHEMAS ==========

class ServiceBase(BaseModel):
    name: str
    description: str
    icon: str
    features: List[str]

class ServiceCreate(ServiceBase):
    pass

class ServiceResponse(BaseModel):
    """Service with list validator for features"""
    id: int
    name: str
    description: str
    icon: str
    features: List[str]
    
    @field_validator('features', mode='before')
    @classmethod
    def parse_features(cls, v):
        """Convert comma-separated string to list if needed."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(',') if item.strip()]
        return v if isinstance(v, list) else []
    
    class Config:
        from_attributes = True


# ========== PROJECT SCHEMAS ==========

class ProjectBase(BaseModel):
    title: str
    client: str
    category: str
    description: str
    image: str
    technologies: List[str]
    results: List[str]
    app_url: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(BaseModel):
    """Project with list validators for technologies and results"""
    id: int
    title: str
    client: str
    category: str
    description: str
    image: str
    technologies: List[str]
    results: List[str]
    app_url: Optional[str]
    
    @field_validator('technologies', mode='before')
    @classmethod
    def parse_technologies(cls, v):
        """Convert comma-separated string to list if needed."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(',') if item.strip()]
        return v if isinstance(v, list) else []
    
    @field_validator('results', mode='before')
    @classmethod
    def parse_results(cls, v):
        """Convert comma-separated string to list if needed."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(',') if item.strip()]
        return v if isinstance(v, list) else []
    
    class Config:
        from_attributes = True


# ========== CONTACT SCHEMAS ==========

class ContactMessageBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    company: Optional[str] = None
    subject: Optional[str] = None
    message: str

class ContactMessageCreate(ContactMessageBase):
    pass

class ContactMessageResponse(ContactMessageBase):
    id: int
    created_at: datetime
    read: bool = False
    
    class Config:
        from_attributes = True


# ========== LESSON PROGRESS SCHEMAS ==========

class LessonProgressBase(BaseModel):
    lesson_id: int
    is_completed: bool = False
    time_spent_seconds: int = 0
    quiz_score: Optional[float] = None

class LessonProgressCreate(LessonProgressBase):
    pass

class LessonProgressResponse(LessonProgressBase):
    id: int
    user_id: int
    started_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ========== CAPTCHA SCHEMAS ==========

class CaptchaVerifyRequest(BaseModel):
    token: str
    user_answer: Optional[str] = None

class CaptchaVerifyResponse(BaseModel):
    valid: bool
    message: str


# ========== SCHEMA ALIASES ==========
# For backwards compatibility with existing routers

ServiceOut = ServiceResponse
TeamMemberOut = TeamMemberResponse
ProjectOut = ProjectResponse
CourseOut = CourseResponse
EnrollmentOut = EnrollmentResponse
PaymentOut = PaymentResponse
LessonOut = LessonResponse
ContactMessageOut = ContactMessageResponse
LessonProgressOut = LessonProgressResponse

# Token aliases
LoginOut = LoginResponse
RegisterOut = AuthResponse
UserOut = UserResponse