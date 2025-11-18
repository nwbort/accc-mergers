from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from typing import List, Optional, Dict, Any
from datetime import datetime
from database import get_db, calculate_phase_duration, init_database
import json
import os
from pathlib import Path

app = FastAPI(title="ACCC Merger Tracker API", version="1.0.0")


@app.on_event("startup")
async def startup_event():
    """Initialize database, cache, and sync data on startup."""
    print("Initializing in-memory cache...")
    FastAPICache.init(InMemoryBackend())
    print("✓ Cache initialized")

    print("Initializing database...")
    init_database()
    print("✓ Database initialized")

    # Sync data from mergers.json if it exists
    json_path = Path(__file__).parent.parent.parent / "mergers.json"
    if json_path.exists():
        print(f"Syncing data from {json_path}...")
        try:
            # Import sync function here to avoid circular imports
            from sync_data import sync_from_json
            sync_from_json(str(json_path))
            print("✓ Data synced successfully")
        except Exception as e:
            print(f"Warning: Failed to sync data: {e}")
            print("Database will be empty until data is synced manually")
    else:
        print(f"Warning: {json_path} not found. Database will be empty until data is synced.")

    print("✓ Application startup complete")

# CORS middleware for frontend access
# Allow production domain, Cloudflare preview branches, and localhost for development
allowed_origins = [
    "https://mergers.fyi",
    "https://www.mergers.fyi",
    "http://localhost:5173",
    "http://localhost:3000",
]

# Add custom origins from environment variable if provided
env_origins = os.getenv("ALLOWED_ORIGINS", "")
if env_origins:
    allowed_origins.extend([origin.strip() for origin in env_origins.split(",")])

# Regex pattern to match all Cloudflare Pages preview deployments
# Matches: https://*.mergers-fyi.pages.dev and https://mergers.fyi
allow_origin_regex = r"https://([a-z0-9-]+\.)?mergers-fyi(\.pages\.dev)?"

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "ACCC Merger Tracker API", "version": "1.0.0"}


@app.get("/api/mergers")
@cache(expire=1800)  # Cache for 30 minutes
def get_mergers(
    response: Response,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None
):
    """Get all mergers with optional filtering."""
    response.headers["Cache-Control"] = "public, max-age=1800"
    with get_db() as conn:
        cursor = conn.cursor()

        query = "SELECT * FROM mergers WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if search:
            query += " AND (merger_name LIKE ? OR merger_description LIKE ?)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param])

        query += " ORDER BY effective_notification_datetime DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor.execute(query, params)
        mergers = [dict(row) for row in cursor.fetchall()]

        # Enrich with related data
        for merger in mergers:
            merger_id = merger['merger_id']

            # Get acquirers
            cursor.execute(
                "SELECT * FROM parties WHERE merger_id = ? AND party_type = 'acquirer'",
                (merger_id,)
            )
            merger['acquirers'] = [dict(row) for row in cursor.fetchall()]

            # Get targets
            cursor.execute(
                "SELECT * FROM parties WHERE merger_id = ? AND party_type = 'target'",
                (merger_id,)
            )
            merger['targets'] = [dict(row) for row in cursor.fetchall()]

            # Get ANZSIC codes
            cursor.execute(
                "SELECT * FROM anzsic_codes WHERE merger_id = ?",
                (merger_id,)
            )
            merger['anzsic_codes'] = [dict(row) for row in cursor.fetchall()]

            # Get events
            cursor.execute(
                "SELECT * FROM events WHERE merger_id = ? ORDER BY date DESC",
                (merger_id,)
            )
            merger['events'] = [dict(row) for row in cursor.fetchall()]

        return {"mergers": mergers, "count": len(mergers)}


@app.get("/api/mergers/{merger_id}")
@cache(expire=1800)  # Cache for 30 minutes
def get_merger(merger_id: str, response: Response):
    """Get detailed information about a specific merger."""
    response.headers["Cache-Control"] = "public, max-age=1800"
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM mergers WHERE merger_id = ?", (merger_id,))
        merger = cursor.fetchone()

        if not merger:
            raise HTTPException(status_code=404, detail="Merger not found")

        merger = dict(merger)

        # Get acquirers
        cursor.execute(
            "SELECT * FROM parties WHERE merger_id = ? AND party_type = 'acquirer'",
            (merger_id,)
        )
        merger['acquirers'] = [dict(row) for row in cursor.fetchall()]

        # Get targets
        cursor.execute(
            "SELECT * FROM parties WHERE merger_id = ? AND party_type = 'target'",
            (merger_id,)
        )
        merger['targets'] = [dict(row) for row in cursor.fetchall()]

        # Get ANZSIC codes
        cursor.execute(
            "SELECT * FROM anzsic_codes WHERE merger_id = ?",
            (merger_id,)
        )
        merger['anzsic_codes'] = [dict(row) for row in cursor.fetchall()]

        # Get events
        cursor.execute(
            "SELECT * FROM events WHERE merger_id = ? ORDER BY date ASC",
            (merger_id,)
        )
        merger['events'] = [dict(row) for row in cursor.fetchall()]

        return merger


@app.get("/api/stats")
@cache(expire=3600)  # Cache for 1 hour (data syncs every 6 hours)
def get_statistics(response: Response):
    """Get aggregated statistics about mergers."""
    response.headers["Cache-Control"] = "public, max-age=3600"
    with get_db() as conn:
        cursor = conn.cursor()

        # Total mergers
        cursor.execute("SELECT COUNT(*) as count FROM mergers")
        total_mergers = cursor.fetchone()['count']

        # By status
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM mergers
            GROUP BY status
        """)
        by_status = {row['status']: row['count'] for row in cursor.fetchall()}

        # By determination
        cursor.execute("""
            SELECT accc_determination, COUNT(*) as count
            FROM mergers
            WHERE accc_determination IS NOT NULL
            GROUP BY accc_determination
        """)
        by_determination = {row['accc_determination']: row['count'] for row in cursor.fetchall()}

        # Calculate phase durations
        cursor.execute("""
            SELECT
                effective_notification_datetime,
                determination_publication_date
            FROM mergers
            WHERE determination_publication_date IS NOT NULL
        """)

        durations = []
        for row in cursor.fetchall():
            duration = calculate_phase_duration(
                row['effective_notification_datetime'],
                row['determination_publication_date']
            )
            if duration is not None:
                durations.append(duration)

        avg_duration = sum(durations) / len(durations) if durations else None
        median_duration = sorted(durations)[len(durations) // 2] if durations else None

        # Top industries
        cursor.execute("""
            SELECT name, COUNT(*) as count
            FROM anzsic_codes
            GROUP BY name
            ORDER BY count DESC
            LIMIT 10
        """)
        top_industries = [dict(row) for row in cursor.fetchall()]

        # Recent mergers
        cursor.execute("""
            SELECT merger_id, merger_name, status, effective_notification_datetime
            FROM mergers
            ORDER BY effective_notification_datetime DESC
            LIMIT 5
        """)
        recent_mergers = [dict(row) for row in cursor.fetchall()]

        return {
            "total_mergers": total_mergers,
            "by_status": by_status,
            "by_determination": by_determination,
            "phase_duration": {
                "average_days": avg_duration,
                "median_days": median_duration,
                "all_durations": durations
            },
            "top_industries": top_industries,
            "recent_mergers": recent_mergers
        }


@app.get("/api/timeline")
@cache(expire=1800)  # Cache for 30 minutes
def get_timeline(response: Response, limit: int = 15, offset: int = 0):
    """Get paginated timeline of all events across all mergers."""
    response.headers["Cache-Control"] = "public, max-age=1800"
    with get_db() as conn:
        cursor = conn.cursor()

        # Get total count of events
        cursor.execute("SELECT COUNT(*) as total FROM events")
        total = cursor.fetchone()['total']

        # Get paginated events with merger info
        cursor.execute("""
            SELECT
                e.date,
                e.title,
                e.display_title,
                e.url,
                e.url_gh,
                e.status,
                e.merger_id,
                m.merger_name
            FROM events e
            JOIN mergers m ON e.merger_id = m.merger_id
            ORDER BY e.date DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        events = [dict(row) for row in cursor.fetchall()]

        return {
            "events": events,
            "total": total,
            "limit": limit,
            "offset": offset
        }


@app.get("/api/industries")
@cache(expire=3600)  # Cache for 1 hour
def get_industries(response: Response):
    """Get all industries with merger counts."""
    response.headers["Cache-Control"] = "public, max-age=3600"
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                code,
                name,
                COUNT(DISTINCT merger_id) as merger_count
            FROM anzsic_codes
            GROUP BY code, name
            ORDER BY merger_count DESC
        """)

        industries = [dict(row) for row in cursor.fetchall()]

        return {"industries": industries}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
