"""
Seeds starter rows into the database the first time it's empty.

This is the one place actual content still originates as Python data — but
the difference from before matters: it's written into the database once,
and every API response after that comes from a real query against that
database, not from an in-memory list baked into the route handler. Edit
these rows through the database (or add an admin endpoint later) and the
API reflects it immediately — no code changes or redeploys needed.
"""

from sqlalchemy.orm import Session
import models


def seed_if_empty(db: Session):
    if db.query(models.Service).count() == 0:
        services = [
            dict(name="AI App Development",
                 description="Build intelligent, AI-powered applications tailored to your business needs",
                 icon="brain",
                 features="Custom AI Solutions,Machine Learning Models,Natural Language Processing,Computer Vision"),
            dict(name="Website Development",
                 description="Create stunning, responsive websites that convert visitors into customers",
                 icon="globe",
                 features="Full-Stack Development,Mobile Responsive,E-commerce Integration,SEO Optimization"),
            dict(name="Tech Consulting",
                 description="Strategic guidance to implement new technologies and transform your business",
                 icon="target",
                 features="Technology Strategy,Digital Transformation,Process Optimization,AI Implementation"),
            dict(name="Business & Marketing Planning",
                 description="Comprehensive planning to scale your business with modern tech strategies",
                 icon="chart",
                 features="Market Analysis,Growth Strategy,Digital Marketing,Business Proposals"),
            dict(name="Implementation Support",
                 description="End-to-end support in developing and deploying your technology solutions",
                 icon="rocket",
                 features="Project Management,Development Support,Deployment,Training & Support"),
            dict(name="AI Technology Guidance",
                 description="Expert guidance on adopting cutting-edge AI technologies for your organization",
                 icon="zap",
                 features="AI Roadmap Planning,Technology Selection,Team Training,Best Practices"),
        ]
        db.bulk_save_objects([models.Service(**s) for s in services])

    if db.query(models.TeamMember).count() == 0:
        team = [
            dict(name="Albert A. D. Cabrera", role="Founder & CEO",
                 bio="Founder and CEO of Ayinde Technologies, leading strategy and client partnerships.",
                 image="👨‍💼", expertise="Strategic Planning,Business Development,Client Partnerships",
                 email="support@ayindetechnologies.com", phone="949-520-8178"),
            dict(name="Ezuma Festus", role="Tech Lead",
                 bio="Tech Lead at Ayinde Technologies, overseeing build quality and implementation.",
                 image="👨‍💻", expertise="Backend Development,System Architecture,AI Implementation",
                 email="support@ayindetechnologies.com", phone=None),
            dict(name="AI Consultant", role="ML Engineer",
                 bio="Specialized in implementing machine learning solutions for enterprises",
                 image="👨‍🔬", expertise="Machine Learning,Data Science,AI Solutions",
                 email=None, phone=None),
        ]
        db.bulk_save_objects([models.TeamMember(**t) for t in team])

    if db.query(models.Project).count() == 0:
        projects = [
            dict(title="Enterprise AI Dashboard", client="Tech Corp Nigeria", category="AI Application",
                 description="Developed an intelligent dashboard with AI-powered analytics and predictions",
                 image="📊", technologies="Python,FastAPI,React,TensorFlow",
                 results="40% increase in decision-making speed,Reduced manual analysis by 60%",
                 app_url=None),
            dict(title="E-Commerce Platform", client="Digital Store Ltd", category="Web Development",
                 description="Built a complete e-commerce platform with AI recommendations",
                 image="🛍️", technologies="React,Node.js,MongoDB,Stripe",
                 results="2.5x increase in sales,95% customer satisfaction",
                 app_url=None),
            dict(title="Business Intelligence System", client="Finance Solutions",
                 category="Consulting & Implementation",
                 description="Strategic implementation of BI tools and AI analytics",
                 image="📈", technologies="Python,Power BI,SQL,AWS",
                 results="Real-time business insights,Optimized operations by 45%",
                 app_url=None),
        ]
        db.bulk_save_objects([models.Project(**p) for p in projects])

    if db.query(models.Course).count() == 0:
        courses = [
            dict(title="Programming Foundations", description="Start from zero — variables, logic, and your first working programs.",
                 level="Beginner", duration="4 weeks", icon="🧩", price=10000.0, currency="NGN"),
            dict(title="Applied Data Skills", description="Clean, query, and analyze real data sets using Python.",
                 level="Intermediate", duration="6 weeks", icon="📊", price=15000.0, currency="NGN"),
            dict(title="Building AI-Powered Apps", description="Ship a real AI-backed feature or product from scratch.",
                 level="Advanced", duration="8 weeks", icon="🤖", price=25000.0, currency="NGN"),
            dict(title="1:1 Deep-Dive Tutoring", description="Targeted sessions on exactly the gaps you name.",
                 level="All levels", duration="Ongoing", icon="🎯", price=20000.0, currency="NGN"),
        ]
        db.bulk_save_objects([models.Course(**c) for c in courses])

    db.commit()
