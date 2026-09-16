"""
Authentication endpoints: register, login, get current user.

Endpoints:
- POST /api/auth/register - Create new user account
- POST /api/auth/login - Login with email and password
- GET /api/auth/me - Get current user info (requires auth)
- POST /api/auth/logout - Logout (frontend deletes token)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from database import get_db
from auth import hash_password, verify_password, create_access_token, get_current_user
from models import User
import schemas
from security import verify_captcha, limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=schemas.Token)
@limiter.limit("5/minute")
async def register(
    request: Request,
    user_data: schemas.UserRegister,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.
    
    Required fields:
    - name: User's full name (1-100 chars)
    - email: Valid email address (must be unique)
    - password: Min 8 chars, must contain letter + number
    - captcha_token: From /api/captcha endpoint
    - captcha_answer: User's answer to captcha
    
    Returns: JWT access token
    
    Errors:
    - 400: Email already registered, password too weak, invalid captcha
    - 429: Too many requests (rate limited to 5/min)
    """
    
    try:
        # Verify captcha
        if not verify_captcha(user_data.captcha_token, user_data.captcha_answer):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid captcha. Please try again."
            )
        
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered. Please login or use a different email."
            )
        
        # Create new user
        hashed_password = hash_password(user_data.password)
        new_user = User(
            name=user_data.name,
            email=user_data.email,
            hashed_password=hashed_password,
            is_active=True
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Create JWT token
        access_token = create_access_token({"sub": str(new_user.id)})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": schemas.UserOut.from_attributes(new_user)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create account. Please try again."
        )


@router.post("/login", response_model=schemas.Token)
@limiter.limit("10/minute")
async def login(
    request: Request,
    credentials: schemas.UserLogin,
    db: Session = Depends(get_db)
):
    """
    Login with email and password.
    
    Required fields:
    - email: Registered email address
    - password: Account password
    - captcha_token: From /api/captcha endpoint
    - captcha_answer: User's answer to captcha
    
    Returns: JWT access token
    
    Errors:
    - 401: Invalid email/password combination
    - 403: Account is disabled
    - 400: Invalid captcha
    - 429: Too many login attempts (rate limited to 10/min)
    """
    
    try:
        # Verify captcha
        if not verify_captcha(credentials.captcha_token, credentials.captcha_answer):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid captcha. Please try again."
            )
        
        # Find user
        user = db.query(User).filter(User.email == credentials.email).first()
        
        if not user or not verify_password(credentials.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if account is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled. Please contact support."
            )
        
        # Create JWT token
        access_token = create_access_token({"sub": str(user.id)})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": schemas.UserOut.from_attributes(user)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again."
        )


@router.get("/me", response_model=schemas.UserOut)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current logged-in user's profile information.
    
    Requires: Valid JWT token in Authorization header
    
    Returns: Current user's details
    
    Errors:
    - 401: Missing or invalid token
    """
    return schemas.UserOut.from_attributes(current_user)


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Logout endpoint (informational - actual logout happens on frontend).
    
    Frontend should:
    1. Call this endpoint (optional, for logging purposes)
    2. Delete the JWT token from localStorage/cookies
    3. Redirect to login page
    
    Returns: Success message
    """
    return {
        "status": "success",
        "message": "Logged out successfully. Please delete your token."
    }