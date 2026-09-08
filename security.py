"""
Application-level security:

- A self-hosted image CAPTCHA (no external API key needed).
- Rate limiting on sensitive endpoints (login, register, contact) to slow
  down brute-force and spam attempts.
- A handful of security response headers.

Important honesty note: this is *application-level* hardening, not a
network firewall. A real firewall / WAF (blocking malicious traffic before
it ever reaches this code, DDoS mitigation, IP reputation blocking, etc.)
is infrastructure, not something a Python app can provide for itself — see
README.md for what to turn on at the hosting/CDN level.
"""

import io
import time
import random
import string
import uuid
import base64

from PIL import Image, ImageDraw, ImageFont
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


# ---------------------------------------------------------------------------
# CAPTCHA (in-memory store — fine for a single instance; swap for Redis if
# you ever run this behind a load balancer with multiple instances)
# ---------------------------------------------------------------------------
CAPTCHA_TTL_SECONDS = 5 * 60
_captcha_store = {}  # token -> (answer, expires_at)


def _cleanup_captchas():
    now = time.time()
    for t in [t for t, (_, exp) in _captcha_store.items() if exp < now]:
        _captcha_store.pop(t, None)


def generate_captcha():
    _cleanup_captchas()
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    token = str(uuid.uuid4())
    _captcha_store[token] = (code, time.time() + CAPTCHA_TTL_SECONDS)

    width, height = 180, 64
    img = Image.new("RGB", (width, height), color=(244, 246, 242))
    draw = ImageDraw.Draw(img)

    for _ in range(6):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        draw.line((x1, y1, x2, y2), fill=(201, 210, 218), width=2)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
    except Exception:
        font = ImageFont.load_default()

    x_cursor = 15
    for ch in code:
        y_offset = random.randint(-6, 6)
        draw.text((x_cursor, 14 + y_offset), ch, font=font, fill=(22, 41, 74))
        x_cursor += 30

    for _ in range(80):
        x, y = random.randint(0, width - 1), random.randint(0, height - 1)
        draw.point((x, y), fill=(198, 154, 60))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    image_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")
    return token, image_base64


def verify_captcha(token: str, answer: str) -> bool:
    _cleanup_captchas()
    entry = _captcha_store.get(token)
    if not entry:
        return False
    code, expires_at = entry
    _captcha_store.pop(token, None)  # one-time use
    if time.time() > expires_at:
        return False
    return answer.strip().upper() == code
