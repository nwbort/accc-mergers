#!/usr/bin/env python3
"""
Migration script to add phase tracking columns to existing database.
"""

import sqlite3
import re
from database import DATABASE_PATH

# Security: Whitelist of allowed column types to prevent SQL injection
ALLOWED_COLUMN_TYPES = {'TEXT', 'INTEGER', 'REAL', 'BLOB', 'NULL'}

def is_safe_column_name(name):
    """
    Validate column name to prevent SQL injection.
    Only allows alphanumeric characters, underscores, and must not be empty.
    """
    if not name or not isinstance(name, str):
        return False
    # Only allow alphanumeric and underscores, must start with letter or underscore
    return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name))

def is_safe_column_type(col_type):
    """
    Validate column type against whitelist to prevent SQL injection.
    """
    if not col_type or not isinstance(col_type, str):
        return False
    return col_type.upper() in ALLOWED_COLUMN_TYPES

def migrate():
    """Add phase tracking and display_title columns to existing tables."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Check if phase column exists in events table
        cursor.execute("PRAGMA table_info(events)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'phase' not in columns:
            print("Adding phase column to events table...")
            cursor.execute("ALTER TABLE events ADD COLUMN phase TEXT")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_phase ON events(phase)")
            print("✓ Added phase column to events table")
        else:
            print("✓ Phase column already exists in events table")

        # Check if display_title column exists in events table
        if 'display_title' not in columns:
            print("Adding display_title column to events table...")
            cursor.execute("ALTER TABLE events ADD COLUMN display_title TEXT")
            # Set display_title to title for existing events
            cursor.execute("UPDATE events SET display_title = title WHERE display_title IS NULL")
            print("✓ Added display_title column to events table")
        else:
            print("✓ display_title column already exists in events table")

        # Check if phase-specific determination columns exist in mergers table
        cursor.execute("PRAGMA table_info(mergers)")
        merger_columns = [row[1] for row in cursor.fetchall()]

        new_columns = [
            ('url', 'TEXT'),
            ('phase_1_determination', 'TEXT'),
            ('phase_1_determination_date', 'TEXT'),
            ('phase_2_determination', 'TEXT'),
            ('phase_2_determination_date', 'TEXT'),
            ('public_benefits_determination', 'TEXT'),
            ('public_benefits_determination_date', 'TEXT'),
        ]

        for col_name, col_type in new_columns:
            # Security: Validate column name and type before using in SQL
            if not is_safe_column_name(col_name):
                raise ValueError(f"Invalid column name: {col_name}")
            if not is_safe_column_type(col_type):
                raise ValueError(f"Invalid column type: {col_type}")

            if col_name not in merger_columns:
                print(f"Adding {col_name} column to mergers table...")
                # Safe to use f-string here after validation
                cursor.execute(f"ALTER TABLE mergers ADD COLUMN {col_name} {col_type}")
                print(f"✓ Added {col_name} column")
            else:
                print(f"✓ {col_name} column already exists")

        conn.commit()
        print("\n✓ Migration complete!")

    except sqlite3.OperationalError as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
