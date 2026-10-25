"""
Admin access control.

Admins are the accounts whose email is listed in the ADMIN_EMAILS environment
variable (comma-separated). Set it on Railway, for example:
    ADMIN_EMAILS=you@example.com,partner@example.com
"""

import os

from fastapi import Depends, HTTPException

from auth import get_current_user
from models import User

ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.getenv("ADMIN_EMAILS", "").split(",")
    if e.strip()
}


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.email.lower() not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admins only.")
    return current_user
