"""Pydantic schemas — request bodies and API response shapes."""

from datetime import datetime
from typing import List, Optional
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


# ---------- Projects (login required) ----------

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


# ---------- Courses (login required) ----------

class CourseOut(BaseModel):
    id: int
    title: str
    description: str
    level: str
    duration: str
    icon: str
    price: Optional[float] = None
    currency: Optional[str] = None
    enrolled: bool = False
    access_status: str = "not_enrolled"  # not_enrolled / trial / active / expired
    trial_ends_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EnrollResponse(BaseModel):
    status: str
    course_id: int
    trial_ends_at: Optional[datetime] = None


# ---------- Payments ----------

class PaymentInitRequest(BaseModel):
    course_id: int
    redirect_url: Optional[str] = None


class PaymentInitResponse(BaseModel):
    status: str  # "success" | "unavailable" | "error"
    message: str
    payment_link: Optional[str] = None


class PaymentVerifyRequest(BaseModel):
    transaction_id: str


class PaymentVerifyResponse(BaseModel):
    status: str  # "success" | "unavailable" | "error"
    message: str


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