"""
Ayinde Technologies - FastAPI Backend

Main application file with CORS, routers, and middleware.

Routers:
- auth: User authentication (register, login, logout)
- courses: Course endpoints and enrollments
- payments: Payment processing
- captcha: Captcha verification
- services: Service order management
- achievements: Company achievements and team members
- quotes: Inspirational quotes with images
- team: Team member profiles
- lessons: Course lesson content and progress
- projects: Portfolio projects
- contact: Contact form submissions
- seed: Database seeding endpoints

Database: Supabase PostgreSQL
Auth: JWT tokens (stored in browser as 'ayinde_token')
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging
import os
from datetime import datetime, timezone

# ════════════════════════════════════════════════════════════════════════════════
# IMPORT ALL ROUTERS
# ════════════════════════════════════════════════════════════════════════════════

from routers.auth import router as auth_router
from routers.courses import router as courses_router
from routers.payments import router as payments_router
from routers.captcha import router as captcha_router
from routers.services import router as services_router
from routers.achievements import router as achievements_router
from routers.quotes import router as quotes_router
from routers.team import router as team_router
from routers.lessons import router as lessons_router
from routers.projects import router as projects_router
from routers.contact import router as contact_router
from routers.seed import router as seed_router

# Import database
from database import engine, get_db
from models import Base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Ayinde Technologies API",
    description="Backend for Ayinde Technologies platform",
    version="1.0.0"
)

# ════════════════════════════════════════════════════════════════════════════════
# 🔴 CRITICAL: CORS MIDDLEWARE MUST BE FIRST!
# ════════════════════════════════════════════════════════════════════════════════

allow_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://www.ayindetechnologies.com",
    "https://ayindetechnologies.com",
]

# ✅ CORS MIDDLEWARE - MUST BE BEFORE ALL OTHER MIDDLEWARE
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods: GET, POST, PUT, DELETE, PATCH, OPTIONS
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],  # Expose all response headers to client
    max_age=3600,  # Cache preflight for 1 hour
)

logger.info("[CORS] Middleware configured for origins: " + ", ".join(allow_origins))

# ════════════════════════════════════════════════════════════════════════════════
# OPTIONS PREFLIGHT HANDLER - Handles CORS preflight requests
# ════════════════════════════════════════════════════════════════════════════════

@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """
    Handle CORS preflight OPTIONS requests.
    
    Browser sends OPTIONS request before actual request to check CORS headers.
    This endpoint must respond with proper CORS headers for preflight to succeed.
    """
    return JSONResponse(
        content={},
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, Accept",
            "Access-Control-Max-Age": "3600",
        }
    )

logger.info("[OPTIONS] Preflight handler registered for all routes")

# ════════════════════════════════════════════════════════════════════════════════
# ROUTERS - ALL ENDPOINTS REGISTERED HERE
# ════════════════════════════════════════════════════════════════════════════════

# Authentication
app.include_router(auth_router)

# Course Management
app.include_router(courses_router)
app.include_router(lessons_router)

# Payments & Services
app.include_router(payments_router)
app.include_router(services_router)

# Security & Forms
app.include_router(captcha_router)
app.include_router(contact_router)

# Public Content
app.include_router(achievements_router)
app.include_router(quotes_router)
app.include_router(team_router)

# Portfolio
app.include_router(projects_router)

# Database Seeding
app.include_router(seed_router)

logger.info("[Routers] ✅ Auth router loaded → /api/auth")
logger.info("[Routers] ✅ Courses router loaded → /api/courses")
logger.info("[Routers] ✅ Lessons router loaded → /api/lessons")
logger.info("[Routers] ✅ Payments router loaded → /api/payments")
logger.info("[Routers] ✅ Services router loaded → /api/services")
logger.info("[Routers] ✅ Captcha router loaded → /api/captcha")
logger.info("[Routers] ✅ Contact router loaded → /api/contact")
logger.info("[Routers] ✅ Achievements router loaded → /api/achievements")
logger.info("[Routers] ✅ Quotes router loaded → /api/quotes")
logger.info("[Routers] ✅ Team router loaded → /api/team")
logger.info("[Routers] ✅ Projects router loaded → /api/projects")
logger.info("[Routers] ✅ Seed router loaded → /api/seed")

# ════════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {
        "status": "running",
        "message": "Ayinde Technologies API is live",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }


@app.get("/health/")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ayinde-backend",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/health/")
async def api_health():
    """API health check endpoint."""
    try:
        # Try to connect to database
        db = next(get_db())
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"[Health] Database connection failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

# ════════════════════════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ════════════════════════════════════════════════════════════════════════════════

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with CORS headers."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={
            "Access-Control-Allow-Origin": "*",
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle all other exceptions."""
    logger.error(f"[Error] Unhandled exception: {type(exc).__name__}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers={
            "Access-Control-Allow-Origin": "*",
        }
    )

# ════════════════════════════════════════════════════════════════════════════════
# STARTUP EVENT
# ════════════════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    """Log startup information."""
    logger.info("════════════════════════════════════════════════════════════════════════════════")
    logger.info("🚀 Ayinde Technologies API Starting")
    logger.info("════════════════════════════════════════════════════════════════════════════════")
    logger.info(f"[Startup] Database: {os.getenv('DATABASE_URL', 'NOT SET')[:50]}...")
    logger.info(f"[Startup] Environment: {os.getenv('ENVIRONMENT', 'production')}")
    logger.info(f"[Startup] Allowed Origins: {', '.join(allow_origins)}")
    logger.info("")
    logger.info("[Startup] ✅ Auth endpoints: /api/auth/register, /api/auth/login, /api/auth/me")
    logger.info("[Startup] ✅ Course endpoints: /api/courses, /api/courses/{id}, /api/courses/{id}/enroll")
    logger.info("[Startup] ✅ Lesson endpoints: /api/lessons/{id}, /api/lessons/{id}/progress")
    logger.info("[Startup] ✅ Payment endpoints: /api/payments/create-intent, /api/payments/verify")
    logger.info("[Startup] ✅ Service endpoints: /api/services/tiers/{type}, /api/services/checkout")
    logger.info("[Startup] ✅ Captcha endpoints: /api/captcha, /api/captcha/verify")
    logger.info("[Startup] ✅ Contact endpoint: /api/contact")
    logger.info("[Startup] ✅ Achievement endpoints: /api/achievements, /api/team-members")
    logger.info("[Startup] ✅ Quote endpoints: /api/quotes, /api/quotes/{id}")
    logger.info("[Startup] ✅ Team endpoints: /api/team, /api/team/{id}")
    logger.info("[Startup] ✅ Project endpoints: /api/projects, /api/projects/{id}")
    logger.info("[Startup] ✅ Seed endpoints: /api/seed/team, /api/seed/quotes, /api/seed/all")
    logger.info("")
    logger.info("[Startup] ✅ CORS middleware configured")
    logger.info("[Startup] ✅ OPTIONS handler registered")
    logger.info("[Startup] ✅ Error handlers registered")
    logger.info("════════════════════════════════════════════════════════════════════════════════")
    logger.info("🟢 Ayinde Technologies API is ONLINE")
    logger.info("════════════════════════════════════════════════════════════════════════════════")

# ════════════════════════════════════════════════════════════════════════════════
# For local testing with uvicorn:
# uvicorn main:app --reload --host 0.0.0.0 --port 8000
# ════════════════════════════════════════════════════════════════════════════════