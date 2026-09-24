"""
Migration: Add missing columns to users table
Run this after deploying to add password and other missing columns
"""

from sqlalchemy import text
from database import engine

def migrate():
    """Add missing columns to users table"""
    
    with engine.connect() as connection:
        try:
            # Add password column if missing
            print("Adding 'password' column to users table...")
            connection.execute(text("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS password VARCHAR(255) NOT NULL DEFAULT '';
            """))
            print("✅ Added 'password' column")
            
            # Add name column if missing
            print("Adding 'name' column to users table...")
            connection.execute(text("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS name VARCHAR(255) NOT NULL DEFAULT '';
            """))
            print("✅ Added 'name' column")
            
            # Add created_at column if missing
            print("Adding 'created_at' column to users table...")
            connection.execute(text("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
            """))
            print("✅ Added 'created_at' column")
            
            connection.commit()
            print("\n✅ All migrations completed successfully!")
            
        except Exception as e:
            connection.rollback()
            print(f"❌ Migration error: {e}")
            raise

if __name__ == "__main__":
    migrate()