import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

DATABASE_PATH = "mergers.db"


def init_database():
    """Initialize the database schema."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Mergers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mergers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merger_id TEXT UNIQUE NOT NULL,
            merger_name TEXT NOT NULL,
            status TEXT NOT NULL,
            stage TEXT,
            effective_notification_datetime TEXT,
            end_of_determination_period TEXT,
            determination_publication_date TEXT,
            accc_determination TEXT,
            consultation_response_due_date TEXT,
            merger_description TEXT,
            phase_1_determination TEXT,
            phase_1_determination_date TEXT,
            phase_2_determination TEXT,
            phase_2_determination_date TEXT,
            public_benefits_determination TEXT,
            public_benefits_determination_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Parties table (acquirers, targets, and other parties)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merger_id TEXT NOT NULL,
            party_type TEXT NOT NULL, -- 'acquirer', 'target', or 'other'
            name TEXT NOT NULL,
            identifier_type TEXT,
            identifier TEXT,
            FOREIGN KEY (merger_id) REFERENCES mergers(merger_id)
        )
    """)

    # ANZSIC codes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anzsic_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merger_id TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (merger_id) REFERENCES mergers(merger_id)
        )
    """)

    # Events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merger_id TEXT NOT NULL,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            display_title TEXT,
            url TEXT,
            url_gh TEXT,
            status TEXT,
            phase TEXT,
            FOREIGN KEY (merger_id) REFERENCES mergers(merger_id)
        )
    """)

    # Create indexes for better query performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_parties_merger_id ON parties(merger_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_anzsic_merger_id ON anzsic_codes(merger_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_merger_id ON events(merger_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_date ON events(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_phase ON events(phase)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mergers_status ON mergers(status)")

    conn.commit()
    conn.close()


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def calculate_phase_duration(start_date: Optional[str], end_date: Optional[str]) -> Optional[int]:
    """Calculate duration in days between two dates."""
    if not start_date or not end_date:
        return None

    try:
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        return (end - start).days
    except (ValueError, AttributeError):
        return None
