"""
Migration: Stripe saved cards and trial auto-charge log.

- Adds users.stripe_customer_id (VARCHAR 255, indexed) if missing.
- Creates the subscription_charges table if missing.

Idempotent. Run from the backend folder with the same DATABASE_URL the API uses:
    python migrate_stripe.py
"""

from sqlalchemy import inspect, text

from database import Base, engine
from models import SubscriptionCharge  # noqa: F401  (registers the table)


def migrate():
    insp = inspect(engine)

    user_cols = {c["name"] for c in insp.get_columns("users")}
    with engine.connect() as connection:
        try:
            if "stripe_customer_id" not in user_cols:
                print("Adding users.stripe_customer_id ...")
                connection.execute(text("ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR(255)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_users_stripe_customer_id ON users (stripe_customer_id)"))
            else:
                print("users.stripe_customer_id already exists.")
            connection.commit()
        except Exception as exc:
            connection.rollback()
            print(f"Migration error on users: {exc}")
            raise

    if "subscription_charges" not in insp.get_table_names():
        print("Creating subscription_charges ...")
        SubscriptionCharge.__table__.create(bind=engine)
    else:
        print("subscription_charges already exists.")

    print("Migration completed.")


if __name__ == "__main__":
    migrate()
