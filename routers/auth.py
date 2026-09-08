from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth import hash_password, verify_password, create_access_token, get_current_user
from security import limiter, verify_captcha

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=schemas.Token, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, payload: schemas.UserRegister, db: Session = Depends(get_db)):
    if not verify_captcha(payload.captcha_token, payload.captcha_answer):
        raise HTTPException(status_code=400, detail="Captcha incorrect or expired — please try again.")

    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with that email already exists.")

    user = models.User(
        name=payload.name.strip(),
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return schemas.Token(access_token=token, user=schemas.UserOut.model_validate(user))


@router.post("/login", response_model=schemas.Token)
@limiter.limit("10/minute")
def login(request: Request, payload: schemas.UserLogin, db: Session = Depends(get_db)):
    if not verify_captcha(payload.captcha_token, payload.captcha_answer):
        raise HTTPException(status_code=400, detail="Captcha incorrect or expired — please try again.")

    user = db.query(models.User).filter(models.User.email == payload.email).first()

    # Deliberately vague error either way — don't reveal whether the email
    # exists, that's an easy way to leak which addresses have accounts.
    invalid = HTTPException(status_code=401, detail="Incorrect email or password.")

    if not user or not verify_password(payload.password, user.hashed_password):
        raise invalid
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated.")

    token = create_access_token({"sub": str(user.id)})
    return schemas.Token(access_token=token, user=schemas.UserOut.model_validate(user))


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user
