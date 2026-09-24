from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import logging
import os

# Database
from database import engine, Base

# Models
import models

# Routers
from routers import auth, courses, services, team, projects, contact, lessons, payments, captcha

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

# ========== ROUTERS ==========
# Include all routers
app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(services.router)  # ✅ NEW: Premium Services
app.include_router(team.router)
app.include_router(projects.router)
app.include_router(contact.router)
app.include_router(lessons.router)
app.include_router(payments.router)
app.include_router(captcha.router)

# ========== HEALTH CHECK ==========
@app.get("/health")
async def health_check():
    """API health check endpoint"""
    return {
        "status": "healthy",
        "service": "Ayinde Technologies API",
        "version": "1.0.0"
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