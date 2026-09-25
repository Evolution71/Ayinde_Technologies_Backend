"""
Ayinde Technologies API
FastAPI backend with authentication, courses, and subscription system
"""

import os
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from database import get_db, engine
from auth import router as auth_router
from routers import courses, services, captcha

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "https://www.ayindetechnologies.com,https://ayindetechnologies.com,http://localhost:3000,http://localhost:8000"
).split(",")

# Clean up whitespace in origins
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS]

PORT = int(os.getenv("PORT", 8000))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# ============================================================
# STARTUP & SHUTDOWN EVENTS
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    
    # ===== STARTUP =====
    logger.info("🚀 Ayinde Technologies API starting...")
    
    # Log CORS configuration
    logger.info(f"✅ CORS enabled for: {ALLOWED_ORIGINS}")
    
    # Log environment
    logger.info(f"📌 Environment: {ENVIRONMENT}")
    logger.info(f"📌 Server port: {PORT}")
    
    # Try to start auto-charge scheduler (optional)
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from auto_charge_scheduler import start_scheduler
        start_scheduler()
        logger.info("✅ Auto-charge scheduler started")
    except ImportError:
        logger.warning("⚠️ auto_charge_scheduler not found - auto-charge disabled")
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}")
    
    # Register all routers
    logger.info("✅ All routers registered")
    
    yield
    
    # ===== SHUTDOWN =====
    logger.info("🛑 Shutting down...")


# ============================================================
# CREATE FASTAPI APP
# ============================================================

app = FastAPI(
    title="Ayinde Technologies API",
    description="Backend for Ayinde Technologies platform",
    version="1.0.0",
    lifespan=lifespan
)

# ============================================================
# CORS MIDDLEWARE (MUST BE FIRST)
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods: GET, POST, PUT, DELETE, PATCH, OPTIONS
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],  # Expose all response headers
    max_age=3600,  # Cache preflight for 1 hour
)

# ============================================================
# OPTIONS HANDLER FOR PREFLIGHT
# ============================================================

@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """Handle CORS preflight requests for all routes"""
    return JSONResponse(
        content={},
        status_code=status.HTTP_200_OK,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
    )

# ============================================================
# ROUTERS
# ============================================================

app.include_router(auth_router)
app.include_router(courses.router)
app.include_router(services.router)
app.include_router(captcha.router)

# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health/")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": ENVIRONMENT
    }

# ============================================================
# ROOT ENDPOINT
# ============================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Ayinde Technologies API",
        "version": "1.0.0",
        "status": "running"
    }

# ============================================================
# LOGGING & ERROR HANDLING
# ============================================================

@app.get("/api/")
async def api_root():
    """API root"""
    return {
        "message": "Ayinde Technologies API v1",
        "endpoints": {
            "auth": "/api/auth/",
            "courses": "/api/courses/",
            "services": "/api/services/",
            "captcha": "/api/captcha/"
        }
    }

# ============================================================
# STARTUP LOGGING
# ============================================================

@app.on_event("startup")
async def startup():
    """Called when app starts"""
    logger.info("🚀 Ayinde Technologies API started")
    logger.info(f"📌 CORS Origins: {', '.join(ALLOWED_ORIGINS)}")
    logger.info("✅ All systems operational")

# ============================================================
# RUN INSTRUCTIONS
# ============================================================
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        reload=ENVIRONMENT == "development",
        log_level="info"
    )