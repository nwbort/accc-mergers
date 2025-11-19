"""
Service for generating and sending daily digest emails.
"""

import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Tuple
from database import get_db
import subscription_service
import email_service


def get_recent_mergers(
    conn: sqlite3.Connection, since_date: datetime
) -> List[Dict[str, Any]]:
    """
    Get mergers created since a specific date.

    Args:
        conn: Database connection
        since_date: Get mergers created after this date

    Returns:
        List of merger dictionaries
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT merger_id, merger_name, status, stage, merger_description,
               created_at, effective_notification_datetime
        FROM mergers
        WHERE created_at >= ?
        ORDER BY created_at DESC
        """,
        (since_date.isoformat(),),
    )

    mergers = []
    for row in cursor.fetchall():
        mergers.append({
            "merger_id": row[0],
            "merger_name": row[1],
            "status": row[2],
            "stage": row[3],
            "merger_description": row[4],
            "created_at": row[5],
            "effective_notification_datetime": row[6],
        })

    return mergers


def get_updated_mergers(
    conn: sqlite3.Connection, since_date: datetime
) -> List[Dict[str, Any]]:
    """
    Get mergers that have been updated since a specific date.

    This looks for mergers where updated_at is more recent than created_at,
    indicating the merger data has changed.

    Args:
        conn: Database connection
        since_date: Get mergers updated after this date

    Returns:
        List of merger dictionaries with changes
    """
    cursor = conn.cursor()

    # Get mergers updated recently (where updated_at > created_at and updated_at >= since_date)
    cursor.execute(
        """
        SELECT merger_id, merger_name, status, stage, updated_at, created_at,
               accc_determination, determination_publication_date
        FROM mergers
        WHERE updated_at >= ?
          AND updated_at > created_at
        ORDER BY updated_at DESC
        """,
        (since_date.isoformat(),),
    )

    mergers = []
    for row in cursor.fetchall():
        merger_id = row[0]
        merger_name = row[1]
        status = row[2]
        stage = row[3]
        updated_at = row[4]
        created_at = row[5]
        determination = row[6]
        determination_date = row[7]

        # Build list of changes (basic for now - could be enhanced)
        changes = []

        if status:
            changes.append(f"Status: {status}")
        if stage:
            changes.append(f"Stage: {stage}")
        if determination:
            changes.append(f"Determination: {determination}")
        if determination_date:
            changes.append(f"Determination published: {determination_date}")

        # Get recent events for this merger
        cursor.execute(
            """
            SELECT event_title, event_date, status
            FROM events
            WHERE merger_id = ?
              AND event_date >= ?
            ORDER BY event_date DESC
            LIMIT 3
            """,
            (merger_id, since_date.date().isoformat()),
        )

        for event_row in cursor.fetchall():
            event_title = event_row[0]
            event_date = event_row[1]
            event_status = event_row[2]

            if event_status == "live":
                changes.append(f"New document: {event_title}")

        # Only include if we have specific changes to report
        if changes:
            mergers.append({
                "merger_id": merger_id,
                "merger_name": merger_name,
                "status": status,
                "stage": stage,
                "updated_at": updated_at,
                "changes": changes,
            })

    return mergers


def get_digest_content(
    conn: sqlite3.Connection, digest_date: date
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Get content for daily digest for a specific date.

    Args:
        conn: Database connection
        digest_date: Date to generate digest for (typically yesterday)

    Returns:
        Tuple of (new_mergers, updated_mergers)
    """
    # Get activity for the digest date (full day)
    start_datetime = datetime.combine(digest_date, datetime.min.time())
    end_datetime = datetime.combine(digest_date, datetime.max.time())

    # Get new mergers created on this date
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT merger_id, merger_name, status, stage, merger_description,
               created_at, effective_notification_datetime
        FROM mergers
        WHERE date(created_at) = ?
        ORDER BY created_at DESC
        """,
        (digest_date.isoformat(),),
    )

    new_mergers = []
    for row in cursor.fetchall():
        new_mergers.append({
            "merger_id": row[0],
            "merger_name": row[1],
            "status": row[2],
            "stage": row[3],
            "merger_description": row[4],
            "created_at": row[5],
            "effective_notification_datetime": row[6],
        })

    # Get updated mergers (excluding the ones we just added)
    new_merger_ids = {m["merger_id"] for m in new_mergers}

    cursor.execute(
        """
        SELECT merger_id, merger_name, status, stage, updated_at,
               accc_determination, determination_publication_date
        FROM mergers
        WHERE date(updated_at) = ?
          AND updated_at > created_at
        ORDER BY updated_at DESC
        """,
        (digest_date.isoformat(),),
    )

    updated_mergers = []
    for row in cursor.fetchall():
        merger_id = row[0]

        # Skip if this is a new merger
        if merger_id in new_merger_ids:
            continue

        merger_name = row[1]
        status = row[2]
        stage = row[3]
        updated_at = row[4]
        determination = row[5]
        determination_date = row[6]

        # Build list of changes
        changes = []

        # Check for status/stage/determination updates
        if status:
            changes.append(f"Status updated: {status}")
        if stage:
            changes.append(f"Stage: {stage}")
        if determination:
            changes.append(f"Determination: {determination}")

        # Get new events added on this date
        cursor.execute(
            """
            SELECT event_title, event_date, status
            FROM events
            WHERE merger_id = ?
              AND date(created_at) = ?
              AND status = 'live'
            ORDER BY event_date DESC
            LIMIT 5
            """,
            (merger_id, digest_date.isoformat()),
        )

        for event_row in cursor.fetchall():
            event_title = event_row[0]
            changes.append(f"New: {event_title}")

        # Only include if we have specific changes
        if changes:
            updated_mergers.append({
                "merger_id": merger_id,
                "merger_name": merger_name,
                "status": status,
                "stage": stage,
                "updated_at": updated_at,
                "changes": changes[:5],  # Limit to 5 changes per merger
            })

    return new_mergers, updated_mergers


def send_daily_digest(digest_date: date = None, dry_run: bool = False) -> Dict[str, Any]:
    """
    Generate and send daily digest emails to all active subscribers.

    Args:
        digest_date: Date to generate digest for (defaults to yesterday)
        dry_run: If True, don't actually send emails, just return what would be sent

    Returns:
        Dictionary with results (sent_count, failed_count, etc.)
    """
    if digest_date is None:
        # Default to yesterday
        digest_date = date.today() - timedelta(days=1)

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Generating daily digest for {digest_date}")

    conn = get_db()

    try:
        # Get digest content
        new_mergers, updated_mergers = get_digest_content(conn, digest_date)

        print(f"Found {len(new_mergers)} new mergers and {len(updated_mergers)} updated mergers")

        # Get active subscribers
        subscribers = subscription_service.get_active_digest_subscribers(conn)
        print(f"Sending to {len(subscribers)} active subscribers")

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "digest_date": digest_date.isoformat(),
                "subscriber_count": len(subscribers),
                "new_mergers_count": len(new_mergers),
                "updated_mergers_count": len(updated_mergers),
                "new_mergers": new_mergers,
                "updated_mergers": updated_mergers,
            }

        # Send emails
        sent_count = 0
        failed_count = 0
        errors = []

        for subscriber in subscribers:
            try:
                # Send digest email
                result = email_service.send_daily_digest(
                    email=subscriber["email"],
                    unsubscribe_token=subscriber["unsubscribe_token"],
                    digest_date=digest_date,
                    new_mergers=new_mergers,
                    updated_mergers=updated_mergers,
                )

                if result["success"]:
                    sent_count += 1

                    # Update last_digest_sent_at
                    subscription_service.update_last_digest_sent(conn, subscriber["id"])

                    # Log notification
                    subscription_service.log_notification(
                        conn,
                        subscriber["id"],
                        "daily_digest",
                        digest_date=digest_date,
                        merger_count=len(new_mergers) + len(updated_mergers),
                        status="sent",
                        resend_email_id=result.get("email_id"),
                        email_subject=f"ACCC Mergers Daily Digest - {digest_date.strftime('%B %d, %Y')}",
                    )

                    print(f"  ✓ Sent to {subscriber['email']}")
                else:
                    failed_count += 1
                    error_msg = result.get("error", "Unknown error")
                    errors.append({"email": subscriber["email"], "error": error_msg})

                    # Log failed notification
                    subscription_service.log_notification(
                        conn,
                        subscriber["id"],
                        "daily_digest",
                        digest_date=digest_date,
                        merger_count=len(new_mergers) + len(updated_mergers),
                        status="failed",
                        error_message=error_msg,
                    )

                    print(f"  ✗ Failed to send to {subscriber['email']}: {error_msg}")

            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                errors.append({"email": subscriber["email"], "error": error_msg})
                print(f"  ✗ Error sending to {subscriber['email']}: {error_msg}")

        print(f"\nDigest sending complete: {sent_count} sent, {failed_count} failed")

        return {
            "success": True,
            "digest_date": digest_date.isoformat(),
            "subscriber_count": len(subscribers),
            "sent_count": sent_count,
            "failed_count": failed_count,
            "new_mergers_count": len(new_mergers),
            "updated_mergers_count": len(updated_mergers),
            "errors": errors if errors else None,
        }

    finally:
        conn.close()


def send_test_digest(email: str, digest_date: date = None) -> Dict[str, Any]:
    """
    Send a test digest email to a specific address (for testing).

    Args:
        email: Email address to send test to
        digest_date: Date to generate digest for (defaults to yesterday)

    Returns:
        Result dictionary
    """
    if digest_date is None:
        digest_date = date.today() - timedelta(days=1)

    conn = get_db()

    try:
        # Get digest content
        new_mergers, updated_mergers = get_digest_content(conn, digest_date)

        # Send test email (use fake unsubscribe token)
        result = email_service.send_daily_digest(
            email=email,
            unsubscribe_token="test-token-not-real",
            digest_date=digest_date,
            new_mergers=new_mergers,
            updated_mergers=updated_mergers,
        )

        return {
            "success": result["success"],
            "email": email,
            "digest_date": digest_date.isoformat(),
            "new_mergers_count": len(new_mergers),
            "updated_mergers_count": len(updated_mergers),
            "error": result.get("error"),
        }

    finally:
        conn.close()
