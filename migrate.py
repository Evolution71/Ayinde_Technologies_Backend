"""
A minimal auto-migration step — not a replacement for a real migration
tool like Alembic, but enough to keep a small app's schema in sync without
adding that dependency under time pressure.

Base.metadata.create_all() (in main.py) only creates tables that don't
exist yet — it never alters a table that's already there, even if the
model gained new columns since that table was created. That's exactly
what caused the `column team_members.email does not exist` error: the
table existed from an earlier deploy, so create_all() silently skipped it.

This function runs after create_all() and adds any columns the models
define but the live database doesn't have yet, using each column's real
type compiled for whatever database you're on (Postgres locally, SQLite
in dev, etc.) — so it works the same way on both.
"""

from sqlalchemy import inspect, text


def run_lightweight_migrations(engine, Base):
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                continue  # brand new table — create_all() already made it in full

            existing_columns = {col["name"] for col in inspector.get_columns(table_name)}

            for column in table.columns:
                if column.name in existing_columns:
                    continue
                try:
                    col_type = column.type.compile(dialect=engine.dialect)
                    conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}'))
                    print(f"[migrate] added missing column: {table_name}.{column.name}")
                except Exception as e:
                    # Don't let one column's failure stop the app from
                    # starting entirely — log it clearly and move on.
                    print(f"[migrate] WARNING: could not add {table_name}.{column.name}: {e}")
