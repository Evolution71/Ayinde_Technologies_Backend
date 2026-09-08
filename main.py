import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from dotenv import load_dotenv

load_dotenv()

from database import Base, engine, SessionLocal
from security import limiter, SecurityHeadersMiddleware
from seed import seed_if_empty
from routers import auth, services, team, projects, courses, contact, captcha

# Create tables if they don't exist yet, and seed starter data.
Base.metadata.create_all(bind=engine)
_db = SessionLocal()
try:
    seed_if_empty(_db)
finally:
    _db.close()

app = FastAPI(title="Ayinde Technologies API", version="2.0.0")

# --- Rate limiting ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Security headers ---
app.add_middleware(SecurityHeadersMiddleware)

# --- CORS ---
# Locked to specific origins rather than "*" — set ALLOWED_ORIGINS in .env
# to a comma-separated list once you know your real frontend URL(s).
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(auth.router)
app.include_router(services.router)
app.include_router(team.router)
app.include_router(projects.router)
app.include_router(courses.router)
app.include_router(contact.router)
app.include_router(captcha.router)


@app.get("/")
def root():
    return {"message": "Welcome to Ayinde Technologies API", "version": "2.0.0", "status": "running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
