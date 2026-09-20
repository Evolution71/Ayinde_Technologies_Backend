"""
Authentication router - login, register, logout, get current user.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

from database import get_db
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)
from models import User
import schemas

router = APIRouter(prefix="/api/auth", tags=["auth"])

ACCESS_TOKEN_EXPIRE_MINUTES = 60


# ========== REGISTER ==========

@router.post("/register/", response_model=schemas.AuthResponse)
async def register(
    user_data: schemas.UserRegister,
    db: Session = Depends(get_db),
):
    """
    Register a new user.
    
    Request:
    - name: User's full name
    - email: User's email (must be unique)
    - password: User's password
    - captcha_token: Optional captcha verification token
    - captcha_answer: Optional captcha answer
    
    Returns:
    - access_token: JWT token for authentication
    - token_type: "bearer"
    - user: User details
    """
    
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = hash_password(user_data.password)
    new_user = User(
        name=user_data.name,
        email=user_data.email,
        hashed_password=hashed_password
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Generate token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": new_user.email},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "name": new_user.name,
            "email": new_user.email,
            "created_at": new_user.created_at,
        }
    }


# ========== LOGIN ==========

@router.post("/login/", response_model=schemas.AuthResponse)
async def login(
    user_data: schemas.UserLogin,
    db: Session = Depends(get_db),
):
    """
    Login with email and password.
    
    Request:
    - email: User's email
    - password: User's password
    - captcha_token: Optional captcha verification token
    - captcha_answer: Optional captcha answer
    
    Returns:
    - access_token: JWT token for authentication
    - token_type: "bearer"
    - user: User details
    """
    
    # Find user by email
    user = db.query(User).filter(User.email == user_data.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Generate token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "created_at": user.created_at,
        }
    }


# ========== GET CURRENT USER ==========

@router.get("/me/", response_model=schemas.UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    Get current authenticated user's profile.
    
    Returns:
    - User details (id, name, email, created_at)
    """
    
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "created_at": current_user.created_at,
    }


# ========== LOGOUT ==========

@router.post("/logout/")
async def logout(
    current_user: User = Depends(get_current_user),
):
    """
    Logout current user.
    
    Note: JWT tokens don't have server-side logout.
    Frontend should delete the token from localStorage.
    
    Returns:
    - message: Logout confirmation
    """
    
    return {
        "message": "Logged out successfully",
        "user_id": current_user.id
    }