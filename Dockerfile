FROM python:3.11-slim

# Force rebuild timestamp
ARG BUILD_DATE=unknown
ENV BUILD_DATE=$BUILD_DATE

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first so this layer is cached unless deps change
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the whole app
COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]