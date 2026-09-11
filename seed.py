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
            dict(name="Albert Cabrera", role="Founder & CEO",
                 bio="Founder and CEO of Ayinde Technologies, leading strategy and client partnerships.",
                 image="👨‍💼", expertise="Strategic Planning,Business Development,Client Partnerships",
                 email="support@ayindetechnologies.com", phone="949-520-8178"),
            dict(name="Ezuma Festus", role="Tech Lead",
                 bio="Tech Lead at Ayinde Technologies, overseeing build quality and implementation.",
                 image="👨‍💻", expertise="Backend Development,System Architecture,AI Implementation,MlOps",
                 email="support@ayindetechnologies.com", phone=None),
            dict(name="Onyekalamba Miriam", role="Email Marketer",
                 bio="Email Marketer at Ayinde Technologies, handling outreach and client communications.",
                 image="👩‍💼", expertise="Email Marketing,Client Communications,Campaign Strategy",
                 email="support@ayindetechnologies.com", phone=None),
        ]
        db.bulk_save_objects([models.TeamMember(**t) for t in team])

    if db.query(models.Project).count() == 0:
        projects = [
            dict(title="AI-Powered Business Dashboard", client="Example project", category="AI Application",
                 description="An example of the kind of AI dashboard we build — combining live business data with predictive analytics so teams can act on what's happening now, not last month's report.",
                 image="📊", technologies="Python,FastAPI,React,TensorFlow",
                 results="Built to surface insights in real time,Designed to cut down manual reporting work",
                 app_url=None),
            dict(title="E-Commerce Platform", client="Example project", category="Web Development",
                 description="An example e-commerce build — a full storefront with AI-driven product recommendations, built for conversion and easy day-to-day management.",
                 image="🛍️", technologies="React,Node.js,MongoDB,Stripe,AWS",
                 results="Built for fast checkout and mobile-first browsing,Includes AI-driven product recommendations",
                 app_url=None),
            dict(title="Business Intelligence System", client="Example project", category="Consulting & Implementation",
                 description="An example of our BI and consulting work — implementing dashboards and AI analytics that give leadership a clear, current view of the business.",
                 image="📈", technologies="Python,Power BI,SQL,AWS",
                 results="Built for real-time business insight,Designed to streamline day-to-day operations",
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
