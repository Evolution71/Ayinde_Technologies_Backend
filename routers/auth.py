"""
Authentication router - login, register, logout, get current user, verify token.

Imports utility functions from backend/auth.py
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from database import get_db
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_current_user_optional,
)
from models import User
import schemas

logger = logging.getLogger(__name__)
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
    access_token = create_access_token(data={"sub": str(new_user.id)})
    
    logger.info(f"[register] New user created: {new_user.id} ({new_user.email})")
    
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
    
    Returns:
    - access_token: JWT token for authentication
    - token_type: "bearer"
    - user: User details
    
    Errors:
    - 401: Invalid email or password
    """
    
    # Find user by email
    user = db.query(User).filter(User.email == user_data.email).first()
    
    if not user:
        logger.warning(f"[login] Failed login attempt: email not found ({user_data.email})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(user_data.password, user.hashed_password):
        logger.warning(f"[login] Failed login attempt: wrong password ({user_data.email})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Generate token
    access_token = create_access_token(data={"sub": str(user.id)})
    
    logger.info(f"[login] User logged in: {user.id} ({user.email})")
    
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
    
    Requires: Valid JWT token in Authorization header
    
    Returns:
    - User details (id, name, email, created_at)
    
    Errors:
    - 401: Not authenticated
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
    Frontend should delete the token from localStorage after this call.
    
    Requires: Valid JWT token in Authorization header
    
    Returns:
    - message: Logout confirmation
    - user_id: User ID that logged out
    
    Errors:
    - 401: Not authenticated
    """
    
    logger.info(f"[logout] User logged out: {current_user.id}")
    
    return {
        "message": "Logged out successfully",
        "user_id": current_user.id
    }


# ========== VERIFY TOKEN ==========

@router.get("/verify/")
async def verify_token(
    current_user: User = Depends(get_current_user_optional),
):
    """
    Verify if current token is valid.
    
    Returns:
    - is_authenticated: True if token is valid
    - user: User details if authenticated, null otherwise
    """
    
    if current_user:
        return {
            "is_authenticated": True,
            "user": {
                "id": current_user.id,
                "name": current_user.name,
                "email": current_user.email,
            }
        }
    
    return {
        "is_authenticated": False,
        "user": None
    }