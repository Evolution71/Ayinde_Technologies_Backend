FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first so this layer is cached unless deps change
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the whole app — database.py, models.py, schemas.py, auth.py,
# security.py, seed.py, payments.py, main.py, routers/, etc.
# (.dockerignore keeps venv/, .env, __pycache__, and *.db out of the image)
COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Real secrets (SECRET_KEY, DATABASE_URL, FLUTTERWAVE_*, etc.) come from
# environment variables set in your hosting platform's dashboard — not
# baked into the image. $PORT is set automatically by most platforms
# (Railway, Render); falls back to 8000 if unset. Written as an explicit
# JSON-form CMD (wrapping sh -c ourselves) so Docker still forwards
# shutdown signals (SIGTERM) straight to uvicorn for clean, fast restarts
# during redeploys, instead of a shell process sitting in between.
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
