#!/usr/bin/env python3
"""
Database migration runner for email notification system.

Usage: python run_migration.py
"""

import sqlite3
from pathlib import Path
from datetime import datetime


def run_migration(db_path: str, migration_file: str):
    """Run a SQL migration file against the database."""
    print(f"Running migration: {migration_file}")

    # Read migration SQL
    migration_path = Path(__file__).parent / "migrations" / migration_file
    if not migration_path.exists():
        raise FileNotFoundError(f"Migration file not found: {migration_path}")

    with open(migration_path, "r") as f:
        migration_sql = f.read()

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Execute migration (split by semicolons to handle multiple statements)
        for statement in migration_sql.split(";"):
            statement = statement.strip()
            if statement and not statement.startswith("--"):
                cursor.execute(statement)

        conn.commit()
        print(f"✓ Migration completed successfully")

        # Show new tables
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Database tables: {', '.join(tables)}")

    except Exception as e:
        conn.rollback()
        print(f"✗ Migration failed: {e}")
        raise
    finally:
        conn.close()


def main():
    # Get database path (same location as main application)
    db_path = Path(__file__).parent.parent.parent / "mergers.db"

    print(f"Database path: {db_path}")
    print(f"Database exists: {db_path.exists()}")

    if not db_path.exists():
        print("Warning: Database does not exist. It will be created.")

    # Run notification system migration
    run_migration(str(db_path), "001_add_notifications.sql")

    print("\n✓ All migrations completed")


if __name__ == "__main__":
    main()
