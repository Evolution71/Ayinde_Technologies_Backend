"""
Migration: Add service_type column to service_orders table
Run this to add the missing service_type column that the ServiceOrder model expects
"""

from sqlalchemy import text
from database import engine

def migrate():
    """Add missing service_type column to service_orders table"""

    with engine.connect() as connection:
        try:
            # Add service_type column if missing
            print("Adding 'service_type' column to service_orders table...")
            connection.execute(text("""
                ALTER TABLE service_orders
                ADD COLUMN IF NOT EXISTS service_type VARCHAR(255) DEFAULT 'website';
            """))
            print("✅ Added 'service_type' column")

            connection.commit()
            print("\n✅ Migration completed successfully!")
            print("Note: All existing orders now have service_type='website' as default")

        except Exception as e:
            connection.rollback()
            print(f"❌ Migration error: {e}")
            raise

if __name__ == "__main__":
    migrate()