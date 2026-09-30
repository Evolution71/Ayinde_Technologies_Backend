"""
Seed script to initialize database with sample data.
Includes users, courses, achievements, and team members.
Run from backend directory: python seed.py
"""

import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from database import engine, SessionLocal, Base
from models import User, Course, Achievement, TeamMember  # ✓ FIXED: Added Achievement and TeamMember
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

        # ========== SEED ACHIEVEMENTS ========== (✓ NEW)
        print("\n🏆 Seeding achievements...")
        existing_achievements = db.query(Achievement).count()
        if existing_achievements == 0:
            achievements = [
                Achievement(
                    title="500+ Successful Projects",
                    description="Delivered over 500 successful projects across various industries",
                    category="metric",
                    icon="🎯",
                    order=1,
                    is_active=True
                ),
                Achievement(
                    title="Industry Award 2024",
                    description="Recognized as the Best Tech Training Provider",
                    category="award",
                    icon="🏅",
                    order=2,
                    is_active=True
                ),
                Achievement(
                    title="500+ Happy Clients",
                    description="Trusted by over 500 satisfied clients worldwide",
                    category="metric",
                    icon="😊",
                    order=3,
                    is_active=True
                ),
                Achievement(
                    title="15+ Years Experience",
                    description="Delivering excellence for over 15 years",
                    category="metric",
                    icon="📅",
                    order=4,
                    is_active=True
                ),
                Achievement(
                    title="ISO Certified",
                    description="ISO 9001:2015 certified for quality management",
                    category="award",
                    icon="✅",
                    order=5,
                    is_active=True
                ),
            ]
            for achievement in achievements:
                db.add(achievement)
                print(f"✅ Added achievement: {achievement.title}")
            db.commit()
            print(f"\n✅ Successfully added {len(achievements)} achievements!")
        else:
            print(f"✅ Database already has {existing_achievements} achievements. Skipping achievements.")

        # ========== SEED TEAM MEMBERS ========== (✓ NEW)
        print("\n👥 Seeding team members...")
        existing_team = db.query(TeamMember).count()
        if existing_team == 0:
            team_members = [
                TeamMember(
                    name="Albert Cabrela",
                    title="Founder & CEO",
                    quote="Innovation and excellence drive everything we do.",
                    achievement="Led the company to $10M+ annual revenue",
                    image="👨‍💼",
                    gender="male",
                    category="leadership",
                    order=1,
                    is_active=True
                ),
                TeamMember(
                    name="Sarah Johnson",
                    title="Chief Technology Officer",
                    quote="Great technology solves real problems.",
                    achievement="20+ years in software architecture",
                    image="👩‍💻",
                    gender="female",
                    category="leadership",
                    order=2,
                    is_active=True
                ),
                TeamMember(
                    name="Mike Peterson",
                    title="Product Manager",
                    quote="User satisfaction is our north star.",
                    achievement="Built 3 successful product lines",
                    image="👨‍💼",
                    gender="male",
                    category="team",
                    order=3,
                    is_active=True
                ),
                TeamMember(
                    name="Emily Rodriguez",
                    title="Lead Engineer",
                    quote="Code quality is not negotiable.",
                    achievement="Architect of core platform system",
                    image="👩‍🔬",
                    gender="female",
                    category="team",
                    order=4,
                    is_active=True
                ),
                TeamMember(
                    name="James Chen",
                    title="DevOps Lead",
                    quote="Infrastructure is the backbone of reliability.",
                    achievement="99.99% uptime track record",
                    image="👨‍💻",
                    gender="male",
                    category="team",
                    order=5,
                    is_active=True
                ),
                TeamMember(
                    name="Diana Watson",
                    title="UX/UI Designer",
                    quote="Design should be intuitive and beautiful.",
                    achievement="Design lead for award-winning interface",
                    image="👩‍🎨",
                    gender="female",
                    category="team",
                    order=6,
                    is_active=True
                ),
            ]
            for member in team_members:
                db.add(member)
                print(f"✅ Added team member: {member.name}")
            db.commit()
            print(f"\n✅ Successfully added {len(team_members)} team members!")
        else:
            print(f"✅ Database already has {existing_team} team members. Skipping team members.")

        print("\n✅ Database seeding complete!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()