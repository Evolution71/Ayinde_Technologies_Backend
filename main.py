from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import logging
import os
from datetime import datetime
import threading

# Database
from database import engine, Base

# Models
import models

# Routers
from routers.auth import router as auth_router
from routers.courses import router as courses_router
from routers.services import router as services_router
from routers.team import router as team_router
from routers.projects import router as projects_router
from routers.contact import router as contact_router
from routers.lessons import router as lessons_router
from routers.payments import router as payments_router
from routers.captcha import router as captcha_router

# Create tables
Base.metadata.create_all(bind=engine)

# Initialize app
app = FastAPI(
    title="Ayinde Technologies API",
    description="Premium Web & App Development Services",
    version="1.0.0"
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== CORS CONFIGURATION ==========
allow_origins = [
    'http://localhost:3000',
    'http://localhost:8000',
    'https://ayindetechnologies.com',
    'https://www.ayindetechnologies.com'
]

print(f"✅ CORS enabled for: {allow_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== AUTO-CHARGE SCHEDULER (Uses APScheduler) ==========
# Starts on FastAPI startup
def start_auto_charge_scheduler():
    """Initialize auto-charge scheduler in background thread"""
    try:
        from auto_charge_scheduler import start_scheduler
        start_scheduler()
        logger.info("[startup] ✅ Auto-charge scheduler initialized")
    except ImportError:
        logger.warning("[startup] ⚠️ auto_charge_scheduler.py not found - auto-charge disabled")
    except Exception as e:
        logger.error(f"[startup] ❌ Failed to start scheduler: {e}")

# Start scheduler on app startup
@app.on_event("startup")
async def startup_event():
    """Run on FastAPI startup"""
    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=start_auto_charge_scheduler, daemon=True)
    scheduler_thread.start()

# ========== ROUTERS ==========
# Include all routers
app.include_router(auth_router)
app.include_router(courses_router)
app.include_router(services_router)  # ✅ Premium Services
app.include_router(team_router)
app.include_router(projects_router)
app.include_router(contact_router)
app.include_router(lessons_router)
app.include_router(payments_router)
app.include_router(captcha_router)  # ✅ Captcha (text-based)

# ========== HEALTH CHECK ==========
@app.get("/health")
async def health_check():
    """API health check endpoint"""
    return {
        "status": "healthy",
        "service": "Ayinde Technologies API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "Welcome to Ayinde Technologies API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
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

# ========== ERROR HANDLERS ==========
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

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