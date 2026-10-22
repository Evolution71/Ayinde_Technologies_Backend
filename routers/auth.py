"""
Authentication router - login, register, logout, get current user.
FIXED to match actual User model schema with password_hash and first_name/last_name
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

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
    - first_name: User's first name
    - last_name: User's last name
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

    # Create new user with correct field names
    password_hash = hash_password(user_data.password)
    new_user = User(
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        email=user_data.email,
        password_hash=password_hash  # ← CORRECT FIELD NAME
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generate token
    access_token = create_access_token(data={"sub": str(new_user.id)})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "first_name": new_user.first_name,
            "last_name": new_user.last_name,
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
    """

    # Find user by email
    user = db.query(User).filter(User.email == user_data.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Defensive check: Ensure user has password_hash (fix for orphaned records)
    if not hasattr(user, 'password_hash') or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Verify password against password_hash field
    if not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Generate token
    access_token = create_access_token(data={"sub": str(user.id)})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
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
    - User details (id, first_name, last_name, email, created_at)
    """

    return {
        "id": current_user.id,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
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