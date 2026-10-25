"""
Migration for the admin console (run once against production, then safe to re-run).

What it does:
1. Creates the console tables (console_clients, console_services, console_transactions,
   console_messages, console_files, newsletter_subscribers, console_broadcasts).
   create_all() only creates missing tables, so this is safe on an existing database.
2. Adds the columns that the contact form and the console need to the existing
   contact_messages table (phone, company, ip_address, is_read). create_all() does
   NOT add columns to tables that already exist, so this is done with ALTER TABLE.

Usage (PowerShell, same window):
    $env:DATABASE_URL = 'postgresql://postgres.<project-ref>:<password>@aws-1-eu-west-1.pooler.supabase.com:5432/postgres'
    python migrate_console.py

Read-only check: pass --check to list what is missing without changing anything.
"""

import sys

from sqlalchemy import inspect, text

from database import engine, Base
import console_models  # noqa: F401  (registers the console tables on Base)
import models  # noqa: F401  (registers contact_messages)

CONTACT_COLUMNS = {
    "phone": "VARCHAR(50)",
    "company": "VARCHAR(255)",
    "ip_address": "VARCHAR(64)",
}


def main(check_only: bool = False) -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    expected_tables = set(Base.metadata.tables.keys())
    console_tables = {
        "console_clients", "console_services", "console_transactions", "console_messages",
        "console_files", "newsletter_subscribers", "console_broadcasts",
    }
    missing_tables = sorted(console_tables - existing_tables)
    print(f"Console tables missing: {missing_tables or 'none'}")

    if "contact_messages" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("contact_messages")}
    else:
        existing_cols = set()
    missing_cols = [c for c in CONTACT_COLUMNS if c not in existing_cols]
    needs_is_read = "is_read" not in existing_cols
    print(f"contact_messages missing columns: {missing_cols + (['is_read'] if needs_is_read else []) or 'none'}")

    if check_only:
        print("Check only: nothing changed.")
        return

    # 1. Create missing tables (idempotent)
    Base.metadata.create_all(bind=engine)
    print(f"create_all done. Tables known to Base: {len(expected_tables)}")

    # 2. Add missing contact_messages columns (idempotent, one transaction)
    with engine.begin() as conn:
        for col, sql_type in CONTACT_COLUMNS.items():
            conn.execute(text(f"ALTER TABLE contact_messages ADD COLUMN IF NOT EXISTS {col} {sql_type}"))
        conn.execute(text(
            "ALTER TABLE contact_messages ADD COLUMN IF NOT EXISTS is_read BOOLEAN NOT NULL DEFAULT FALSE"
        ))
    print("contact_messages columns ensured.")
    print("Migration complete.")


if __name__ == "__main__":
    main(check_only="--check" in sys.argv)
