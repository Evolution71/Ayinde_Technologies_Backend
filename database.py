"""
Database connection setup.

Uses SQLite by default (ayinde.db, created automatically on first run) so
the project works with zero configuration locally. Set DATABASE_URL to a
Postgres connection string (e.g. what Railway gives you) to switch — no
code changes needed anywhere else.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ayinde.db")

# Railway/Heroku-style hosts sometimes hand out "postgres://" — SQLAlchemy
# 2.x wants "postgresql://".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
