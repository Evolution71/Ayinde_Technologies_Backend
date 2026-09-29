"""
Migration script to fix orphaned user records without hashed_password.

Run this ONCE to clean up existing data:
    python fix_orphaned_users.py
"""

from database import SessionLocal
from models import User
from auth import hash_password
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fix_orphaned_users():
    """
    Find and fix users without hashed_password field.

    Options:
    1. Delete them (recommended for dev/test data)
    2. Assign a temporary password (for real users)
    """
    db = SessionLocal()

    try:
        # Find users with NULL or missing hashed_password
        orphaned_users = db.query(User).filter(
            (User.hashed_password == None) | (User.hashed_password == "")
        ).all()

        logger.info(f"Found {len(orphaned_users)} orphaned user(s)")

        if len(orphaned_users) == 0:
            logger.info("✅ No orphaned users found. Database is clean!")
            return

        # Option 1: DELETE orphaned records (recommended for test data)
        for user in orphaned_users:
            logger.warning(f"⚠️  Deleting orphaned user: {user.email} (ID: {user.id})")
            db.delete(user)

        db.commit()
        logger.info(f"✅ Successfully deleted {len(orphaned_users)} orphaned user(s)")

        # Alternative Option 2: Assign temporary password
        # Uncomment below if you want to keep the users with a temp password
        #
        # for user in orphaned_users:
        #     temp_password = f"temp_password_{user.id}"
        #     user.hashed_password = hash_password(temp_password)
        #     logger.info(f"🔐 Assigned temp password to: {user.email}")
        #
        # db.commit()
        # logger.info(f"✅ Successfully fixed {len(orphaned_users)} user(s)")

    except Exception as err:
        logger.error(f"❌ Error during migration: {str(err)}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("🔍 Starting user database cleanup...")
    fix_orphaned_users()
    logger.info("✅ Migration complete!")