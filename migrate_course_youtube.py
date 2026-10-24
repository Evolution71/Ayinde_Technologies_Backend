"""
Migration: add YouTube tutorial fields to the courses table.

Idempotent: only missing columns are added, so it is safe to run more than once.
Run from the backend folder with the same DATABASE_URL the API uses:
    python migrate_course_youtube.py
"""

from sqlalchemy import inspect, text
from database import engine

NEW_COLUMNS = {
    "show_on_youtube": "BOOLEAN NOT NULL DEFAULT FALSE",
    "youtube_url": "VARCHAR(512)",
    "youtube_live_url": "VARCHAR(512)",
    "practical_code_url": "VARCHAR(512)",
    "course_notes": "TEXT",
}


def migrate():
    existing = {col["name"] for col in inspect(engine).get_columns("courses")}
    missing = {name: ddl for name, ddl in NEW_COLUMNS.items() if name not in existing}

    if not missing:
        print("Nothing to do: all YouTube columns already exist.")
        return

    with engine.connect() as connection:
        try:
            for name, ddl in missing.items():
                print(f"Adding courses.{name} ...")
                connection.execute(text(f"ALTER TABLE courses ADD COLUMN {name} {ddl}"))
            connection.commit()
            print(f"Migration completed: added {len(missing)} column(s).")
        except Exception as exc:
            connection.rollback()
            print(f"Migration error: {exc}")
            raise


if __name__ == "__main__":
    migrate()
