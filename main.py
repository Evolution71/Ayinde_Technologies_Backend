"""
Main FastAPI application for Ayinde Technologies.
Includes CORS, middleware, and all routers.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import database and routers
from database import Base, engine, get_db
from routers import auth, courses, services, team, projects, contact, lessons, payments, captcha

# Create tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Ayinde Technologies API",
    description="Full-stack API for Ayinde Technologies platform",
    version="1.0.0",
    redirect_slashes=False
)

# ========== CORS CONFIGURATION ==========

# Read from environment variable, with fallback to defaults
ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS", "")

if ALLOWED_ORIGINS_ENV:
    # Parse from env var (comma-separated, with proper whitespace stripping)
    ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS_ENV.split(",") if origin.strip()]
else:
    # Fallback defaults
    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://ayindetechnologies.com",
        "https://www.ayindetechnologies.com",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Log CORS configuration
print(f"✓ CORS configured with allowed origins: {ALLOWED_ORIGINS}")


# ========== ROUTES ==========

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Ayinde Technologies API",
        "version": "1.0.0",
        "status": "online"
    }


@app.get("/health")
async def health():
    """Health check for monitoring"""
    return {
        "status": "healthy",
        "service": "Ayinde Technologies API"
    }


# ========== ROUTER INCLUDES ==========

app.include_router(auth.router)
app.include_router(captcha.router)
app.include_router(courses.router)
app.include_router(services.router)
app.include_router(team.router)
app.include_router(projects.router)
app.include_router(contact.router)
app.include_router(lessons.router)
app.include_router(payments.router)


# ========== ERROR HANDLERS ==========

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle unexpected errors gracefully"""
    return {
        "error": "Internal server error",
        "detail": str(exc)
    }


# ========== STARTUP EVENTS ==========

@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    print("🚀 Ayinde Technologies API starting up...")
    print(f"📍 Environment: {os.getenv('SQUARE_ENVIRONMENT', 'development')}")
    print("✅ All routers loaded successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    print("👋 Ayinde Technologies API shutting down...")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)