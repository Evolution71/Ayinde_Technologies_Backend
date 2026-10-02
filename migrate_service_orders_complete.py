"""
Migration: Add all missing columns to service_orders table
Run this to add all missing columns that the ServiceOrder model expects
"""

from sqlalchemy import text
from database import engine

def migrate():
    """Add all missing columns to service_orders table"""

    with engine.connect() as connection:
        try:
            print("Adding missing columns to service_orders table...\n")

            # Add order_metadata column if missing
            print("1. Adding 'order_metadata' column (JSON)...")
            connection.execute(text("""
                ALTER TABLE service_orders
                ADD COLUMN IF NOT EXISTS order_metadata JSONB DEFAULT '{}'::jsonb;
            """))
            print("   ✅ Added 'order_metadata' column")

            # Add cancelled_at column if missing
            print("2. Adding 'cancelled_at' column (DateTime)...")
            connection.execute(text("""
                ALTER TABLE service_orders
                ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP;
            """))
            print("   ✅ Added 'cancelled_at' column")

            # Add payment_completed_at column if missing
            print("3. Adding 'payment_completed_at' column (DateTime)...")
            connection.execute(text("""
                ALTER TABLE service_orders
                ADD COLUMN IF NOT EXISTS payment_completed_at TIMESTAMP;
            """))
            print("   ✅ Added 'payment_completed_at' column")

            # Add service_starts_at column if missing
            print("4. Adding 'service_starts_at' column (DateTime)...")
            connection.execute(text("""
                ALTER TABLE service_orders
                ADD COLUMN IF NOT EXISTS service_starts_at TIMESTAMP;
            """))
            print("   ✅ Added 'service_starts_at' column")

            # Add service_ends_at column if missing
            print("5. Adding 'service_ends_at' column (DateTime)...")
            connection.execute(text("""
                ALTER TABLE service_orders
                ADD COLUMN IF NOT EXISTS service_ends_at TIMESTAMP;
            """))
            print("   ✅ Added 'service_ends_at' column")

            connection.commit()
            print("\n✅ All migrations completed successfully!")
            print("\nYour service_orders table now has all required columns:")
            print("  - service_type")
            print("  - order_metadata (JSON)")
            print("  - cancelled_at")
            print("  - payment_completed_at")
            print("  - service_starts_at")
            print("  - service_ends_at")

        except Exception as e:
            connection.rollback()
            print(f"❌ Migration error: {e}")
            raise

if __name__ == "__main__":
    migrate()