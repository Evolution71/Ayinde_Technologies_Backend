from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from database import Base, engine
from routers import auth, courses, services, team, projects, contact, lessons, payments, captcha

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ayinde Technologies API", version="1.0.0")

# ========== CORS CONFIGURATION ==========
# Get allowed origins from environment, with defaults for local + production
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,https://ayindetechnologies.com').split(',')

# Clean up whitespace
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS]

print(f"✅ CORS enabled for: {ALLOWED_ORIGINS}")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== ROUTES ==========
app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(services.router)
app.include_router(team.router)
app.include_router(projects.router)
app.include_router(contact.router)
app.include_router(lessons.router)
app.include_router(payments.router)
app.include_router(captcha.router)

# ========== HEALTH CHECK ==========
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "message": "✅ Application startup complete"
    }

@app.get("/")
def read_root():
    return {
        "message": "Ayinde Technologies API",
        "version": "1.0.0",
        "endpoints": [
            "/api/auth",
            "/api/courses",
            "/api/services",
            "/api/team",
            "/api/projects",
            "/api/contact",
            "/api/lessons",
            "/api/payments",
            "/api/captcha"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)