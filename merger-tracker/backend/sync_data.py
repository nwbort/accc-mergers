#!/usr/bin/env python3
"""
Script to sync data from mergers.json into the SQLite database.
Run this periodically to keep the database updated with latest merger data.
"""

import json
import sqlite3
from pathlib import Path
from database import init_database, DATABASE_PATH, get_db


def normalize_determination(determination: str) -> str:
    """Normalize determination strings to cleaner values."""
    if not determination:
        return determination

    # Normalize common patterns
    if 'Approved' in determination:
        return 'Approved'
    elif 'Declined' in determination:
        return 'Declined'

    return determination


def sync_from_json(json_path: str):
    """Sync data from mergers.json into the database."""

    # Initialize database if needed
    init_database()

    # Load JSON data
    with open(json_path, 'r', encoding='utf-8') as f:
        mergers = json.load(f)

    print(f"Loading {len(mergers)} mergers from {json_path}")

    with get_db() as conn:
        cursor = conn.cursor()

        for merger_data in mergers:
            merger_id = merger_data['merger_id']

            # Insert or update merger
            cursor.execute("""
                INSERT INTO mergers (
                    merger_id, merger_name, status, stage,
                    effective_notification_datetime,
                    end_of_determination_period,
                    determination_publication_date,
                    accc_determination,
                    merger_description,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(merger_id) DO UPDATE SET
                    merger_name = excluded.merger_name,
                    status = excluded.status,
                    stage = excluded.stage,
                    effective_notification_datetime = excluded.effective_notification_datetime,
                    end_of_determination_period = excluded.end_of_determination_period,
                    determination_publication_date = excluded.determination_publication_date,
                    accc_determination = excluded.accc_determination,
                    merger_description = excluded.merger_description,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                merger_id,
                merger_data['merger_name'],
                merger_data['status'],
                merger_data.get('stage'),
                merger_data.get('effective_notification_datetime'),
                merger_data.get('end_of_determination_period'),
                merger_data.get('determination_publication_date'),
                normalize_determination(merger_data.get('accc_determination')),
                merger_data.get('merger_description')
            ))

            # Delete existing related data to refresh
            cursor.execute("DELETE FROM parties WHERE merger_id = ?", (merger_id,))
            cursor.execute("DELETE FROM anzsic_codes WHERE merger_id = ?", (merger_id,))
            cursor.execute("DELETE FROM events WHERE merger_id = ?", (merger_id,))

            # Insert acquirers
            for acquirer in merger_data.get('acquirers', []):
                cursor.execute("""
                    INSERT INTO parties (merger_id, party_type, name, identifier_type, identifier)
                    VALUES (?, 'acquirer', ?, ?, ?)
                """, (
                    merger_id,
                    acquirer['name'],
                    acquirer.get('identifier_type'),
                    acquirer.get('identifier')
                ))

            # Insert targets
            for target in merger_data.get('targets', []):
                cursor.execute("""
                    INSERT INTO parties (merger_id, party_type, name, identifier_type, identifier)
                    VALUES (?, 'target', ?, ?, ?)
                """, (
                    merger_id,
                    target['name'],
                    target.get('identifier_type'),
                    target.get('identifier')
                ))

            # Insert ANZSIC codes
            for anzsic in merger_data.get('anszic_codes', []):
                cursor.execute("""
                    INSERT INTO anzsic_codes (merger_id, code, name)
                    VALUES (?, ?, ?)
                """, (
                    merger_id,
                    anzsic['code'],
                    anzsic['name']
                ))

            # Insert events
            for event in merger_data.get('events', []):
                cursor.execute("""
                    INSERT INTO events (merger_id, date, title, url, url_gh, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    merger_id,
                    event['date'],
                    event['title'],
                    event.get('url'),
                    event.get('url_gh'),
                    event.get('status')
                ))

        conn.commit()

        # Print summary
        cursor.execute("SELECT COUNT(*) as count FROM mergers")
        merger_count = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM events")
        event_count = cursor.fetchone()['count']

        print(f"\n✓ Sync complete!")
        print(f"  - {merger_count} mergers in database")
        print(f"  - {event_count} events tracked")


if __name__ == "__main__":
    # Path to mergers.json (adjust if running from different location)
    json_path = Path(__file__).parent.parent.parent / "mergers.json"

    if not json_path.exists():
        print(f"Error: {json_path} not found")
        print("Please run this script from the merger-tracker/backend directory")
        print("or adjust the json_path variable")
        exit(1)

    sync_from_json(str(json_path))
