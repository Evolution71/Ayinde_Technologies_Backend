"""
Seed script to initialize database with sample data.
Includes users, courses, and other initial data.
Run from backend directory: python seed.py
"""

import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from database import engine, SessionLocal, Base
from models import User, Course
from auth import hash_password

# Load environment variables
load_dotenv()

# Create all tables
Base.metadata.create_all(bind=engine)

def seed_database():
    """Seed the database with sample data"""
    db: Session = SessionLocal()
    
    try:
        print("🌱 Seeding database...\n")
        
        # ========== SEED USERS ==========
        print("📝 Seeding users...")
        existing_users = db.query(User).count()
        if existing_users == 0:
            users = [
                User(
                    name="Demo User",
                    email="demo@ayindetechnologies.com",
                    hashed_password=hash_password("password123"),
                ),
                User(
                    name="Test Admin",
                    email="admin@ayindetechnologies.com",
                    hashed_password=hash_password("admin123"),
                ),
            ]
            for user in users:
                db.add(user)
                print(f"✅ Added user: {user.email}")
            db.commit()
        else:
            print(f"✅ Database already has {existing_users} users. Skipping users.")
        
        # ========== SEED COURSES ==========
        print("\n📚 Seeding courses...")
        existing_courses = db.query(Course).count()
        if existing_courses == 0:
            courses = [
                Course(
                    title="Python Fundamentals",
                    description="Learn Python basics from scratch. Perfect for beginners who want to start their programming journey.",
                    instructor="John Doe",
                    price=49.99,
                    duration="4 weeks",
                    level="Beginner",
                    is_active=True,
                    icon="https://via.placeholder.com/300x200?text=Python+Fundamentals",
                    currency="USD"
                ),
                Course(
                    title="Web Development with React",
                    description="Master React and build modern, interactive web applications. Learn components, hooks, and state management.",
                    instructor="Jane Smith",
                    price=79.99,
                    duration="6 weeks",
                    level="Intermediate",
                    is_active=True,
                    icon="https://via.placeholder.com/300x200?text=React",
                    currency="USD"
                ),
                Course(
                    title="Data Science Masterclass",
                    description="Learn data science, machine learning, and AI. From data cleaning to model deployment.",
                    instructor="Mike Johnson",
                    price=99.99,
                    duration="8 weeks",
                    level="Advanced",
                    is_active=True,
                    icon="https://via.placeholder.com/300x200?text=Data+Science",
                    currency="USD"
                ),
                Course(
                    title="Mobile App Development",
                    description="Build native iOS and Android applications. Learn mobile app design patterns and best practices.",
                    instructor="Sarah Lee",
                    price=89.99,
                    duration="7 weeks",
                    level="Intermediate",
                    is_active=True,
                    icon="https://via.placeholder.com/300x200?text=Mobile+Dev",
                    currency="USD"
                ),
                Course(
                    title="Advanced JavaScript",
                    description="Deep dive into JavaScript ES6+, async programming, and modern web development patterns.",
                    instructor="Alex Brown",
                    price=69.99,
                    duration="5 weeks",
                    level="Advanced",
                    is_active=True,
                    icon="https://via.placeholder.com/300x200?text=JavaScript",
                    currency="USD"
                ),
                Course(
                    title="DevOps & Cloud Deployment",
                    description="Learn Docker, Kubernetes, and cloud platforms. Master CI/CD pipelines and infrastructure as code.",
                    instructor="Chris Wilson",
                    price=89.99,
                    duration="6 weeks",
                    level="Advanced",
                    is_active=True,
                    icon="https://via.placeholder.com/300x200?text=DevOps",
                    currency="USD"
                ),
            ]
            for course in courses:
                db.add(course)
                print(f"✅ Added course: {course.title}")
            db.commit()
            print(f"\n✅ Successfully added {len(courses)} courses!")
        else:
            print(f"✅ Database already has {existing_courses} courses. Skipping courses.")
        
        print("\n✅ Database seeding complete!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()