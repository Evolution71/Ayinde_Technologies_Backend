from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os

# Database
from database import engine, Base

# Models
import models

# Create tables
Base.metadata.create_all(bind=engine)

# Initialize app FIRST
app = FastAPI(
    title="Ayinde Technologies API",
    description="Premium Web & App Development Services",
    version="1.0.0"
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== CORS CONFIGURATION (MUST BE FIRST!) ==========
allow_origins = [
    'http://localhost:3000',
    'http://localhost:8000',
    'https://ayindetechnologies.com',
    'https://www.ayindetechnologies.com',
    'https://ayindetechnologies.com/',
    'https://www.ayindetechnologies.com/'
]

# Add from environment if set
env_origins = os.getenv('ALLOWED_ORIGINS', '')
if env_origins:
    allow_origins.extend(env_origins.split(','))

# Remove duplicates
allow_origins = list(set(allow_origins))

logger.info(f"✅ CORS enabled for: {allow_origins}")

# ADD CORS MIDDLEWARE FIRST (before any routers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# ========== ROUTERS (Import AFTER middleware) ==========
from routers.auth import router as auth_router
from routers.courses import router as courses_router
from routers.services import router as services_router
from routers.team import router as team_router
from routers.projects import router as projects_router
from routers.contact import router as contact_router
from routers.lessons import router as lessons_router
from routers.payments import router as payments_router
from routers.captcha import router as captcha_router

# Include all routers
app.include_router(auth_router)
app.include_router(courses_router)
app.include_router(services_router)  # ✅ Premium Services
app.include_router(team_router)
app.include_router(projects_router)
app.include_router(contact_router)
app.include_router(lessons_router)
app.include_router(payments_router)
app.include_router(captcha_router)

logger.info("✅ All routers registered")

# ========== HEALTH CHECK ==========
@app.get("/health")
async def health_check():
    """API health check endpoint"""
    return {
        "status": "healthy",
        "service": "Ayinde Technologies API",
        "version": "1.0.0",
        "cors_origins": allow_origins
    }

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "Welcome to Ayinde Technologies API",
        "version": "1.0.0",
        "endpoints": {
            "auth": "/api/auth",
            "courses": "/api/courses",
            "services": "/api/services",
            "team": "/api/team",
            "projects": "/api/projects",
            "contact": "/api/contact",
            "lessons": "/api/lessons",
            "payments": "/api/payments",
            "captcha": "/api/captcha"
        }
    }

# ========== OPTIONS HANDLER (for CORS preflight) ==========
@app.options("/{full_path:path}")
async def preflight_handler(full_path: str):
    """Handle CORS preflight requests"""
    return {}

# ========== ERROR HANDLERS ==========
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# ========== STARTUP EVENT ==========
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Ayinde Technologies API started")
    logger.info(f"📌 CORS Origins: {', '.join(allow_origins)}")
    
    # Start scheduler if available
    try:
        from auto_charge_scheduler import start_scheduler
        import threading
        scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
        scheduler_thread.start()
        logger.info("✅ Auto-charge scheduler started")
    except ImportError:
        logger.warning("⚠️ auto_charge_scheduler not found - auto-charge disabled")
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}")

# ========== SHUTDOWN EVENT ==========
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Ayinde Technologies API shutdown")

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )