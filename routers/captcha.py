from fastapi import APIRouter

import schemas
from security import generate_captcha

router = APIRouter(prefix="/api/captcha", tags=["captcha"])


@router.get("", response_model=schemas.CaptchaOut)
def get_captcha():
    token, image_base64 = generate_captcha()
    return schemas.CaptchaOut(token=token, image=f"data:image/png;base64,{image_base64}")
