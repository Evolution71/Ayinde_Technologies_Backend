"""
Read-only check: compares the live database with the SQLAlchemy models.

It reports:
  - columns NOT NULL in the database that the model allows to be empty (these cause insert errors)
  - model columns missing from the database
  - database columns the model does not know about

Run from the backend folder with the same DATABASE_URL the API uses:
    python check_schema_drift.py
Nothing is changed.
"""

from sqlalchemy import inspect

from database import Base, engine
import models  # noqa: F401  (registers every table on Base.metadata)


def main():
    insp = inspect(engine)
    db_tables = set(insp.get_table_names())
    problems = 0

    for table in Base.metadata.sorted_tables:
        if table.name not in db_tables:
            print(f"[missing table] {table.name}")
            problems += 1
            continue

        db_cols = {c["name"]: c for c in insp.get_columns(table.name)}
        model_cols = {c.name: c for c in table.columns}

        for name, col in model_cols.items():
            if name not in db_cols:
                print(f"[missing column] {table.name}.{name}")
                problems += 1
                continue
            db_not_null = not db_cols[name]["nullable"]
            db_default = db_cols[name].get("default")
            if db_not_null and col.nullable and db_default is None:
                print(f"[NOT NULL in DB, nullable in model] {table.name}.{name}")
                problems += 1

        for name in db_cols:
            if name not in model_cols:
                print(f"[unknown column in DB] {table.name}.{name}")
                problems += 1

    print(f"\nDone. {problems} difference(s) found.")


if __name__ == "__main__":
    main()
