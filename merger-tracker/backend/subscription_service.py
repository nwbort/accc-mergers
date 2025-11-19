"""
Subscription management service for email notifications.
"""

import sqlite3
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from email_service import generate_token


def get_subscriber_by_email(conn: sqlite3.Connection, email: str) -> Optional[Dict[str, Any]]:
    """Get subscriber by email address."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, email, verification_token, verified, unsubscribe_token,
               unsubscribed, receive_daily_digest, created_at, last_digest_sent_at
        FROM subscribers
        WHERE email = ?
        """,
        (email,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    return {
        "id": row[0],
        "email": row[1],
        "verification_token": row[2],
        "verified": bool(row[3]),
        "unsubscribe_token": row[4],
        "unsubscribed": bool(row[5]),
        "receive_daily_digest": bool(row[6]),
        "created_at": row[7],
        "last_digest_sent_at": row[8],
    }


def get_subscriber_by_verification_token(
    conn: sqlite3.Connection, token: str
) -> Optional[Dict[str, Any]]:
    """Get subscriber by verification token."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, email, verification_token, verified, unsubscribe_token,
               unsubscribed, receive_daily_digest
        FROM subscribers
        WHERE verification_token = ?
        """,
        (token,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    return {
        "id": row[0],
        "email": row[1],
        "verification_token": row[2],
        "verified": bool(row[3]),
        "unsubscribe_token": row[4],
        "unsubscribed": bool(row[5]),
        "receive_daily_digest": bool(row[6]),
    }


def get_subscriber_by_unsubscribe_token(
    conn: sqlite3.Connection, token: str
) -> Optional[Dict[str, Any]]:
    """Get subscriber by unsubscribe token."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, email, unsubscribe_token, unsubscribed
        FROM subscribers
        WHERE unsubscribe_token = ?
        """,
        (token,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    return {
        "id": row[0],
        "email": row[1],
        "unsubscribe_token": row[2],
        "unsubscribed": bool(row[3]),
    }


def create_subscriber(
    conn: sqlite3.Connection,
    email: str,
    subscription_source: str = "web",
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new subscriber.

    Returns:
        Dictionary with subscriber info including tokens
    """
    verification_token = generate_token()
    unsubscribe_token = generate_token()

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO subscribers
        (email, verification_token, unsubscribe_token, subscription_source, user_agent, ip_address)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (email, verification_token, unsubscribe_token, subscription_source, user_agent, ip_address),
    )
    conn.commit()

    subscriber_id = cursor.lastrowid

    return {
        "id": subscriber_id,
        "email": email,
        "verification_token": verification_token,
        "unsubscribe_token": unsubscribe_token,
        "verified": False,
        "created_at": datetime.now().isoformat(),
    }


def verify_subscriber(conn: sqlite3.Connection, verification_token: str) -> bool:
    """
    Verify a subscriber's email address.

    Returns:
        True if verification successful, False otherwise
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE subscribers
        SET verified = 1, verified_at = CURRENT_TIMESTAMP
        WHERE verification_token = ? AND verified = 0
        """,
        (verification_token,),
    )
    conn.commit()
    return cursor.rowcount > 0


def unsubscribe(conn: sqlite3.Connection, unsubscribe_token: str) -> bool:
    """
    Unsubscribe a user.

    Returns:
        True if unsubscribe successful, False otherwise
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE subscribers
        SET unsubscribed = 1, unsubscribed_at = CURRENT_TIMESTAMP, receive_daily_digest = 0
        WHERE unsubscribe_token = ? AND unsubscribed = 0
        """,
        (unsubscribe_token,),
    )
    conn.commit()
    return cursor.rowcount > 0


def get_active_digest_subscribers(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Get all subscribers who should receive the daily digest.

    Returns:
        List of subscriber dictionaries
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, email, unsubscribe_token, last_digest_sent_at
        FROM subscribers
        WHERE verified = 1
          AND unsubscribed = 0
          AND receive_daily_digest = 1
        ORDER BY id
        """
    )

    subscribers = []
    for row in cursor.fetchall():
        subscribers.append({
            "id": row[0],
            "email": row[1],
            "unsubscribe_token": row[2],
            "last_digest_sent_at": row[3],
        })

    return subscribers


def update_last_digest_sent(conn: sqlite3.Connection, subscriber_id: int) -> None:
    """Update the last_digest_sent_at timestamp for a subscriber."""
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE subscribers
        SET last_digest_sent_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (subscriber_id,),
    )
    conn.commit()


def log_notification(
    conn: sqlite3.Connection,
    subscriber_id: int,
    notification_type: str,
    digest_date: Optional[date] = None,
    merger_count: Optional[int] = None,
    status: str = "sent",
    error_message: Optional[str] = None,
    email_subject: Optional[str] = None,
    resend_email_id: Optional[str] = None,
) -> int:
    """
    Log a sent notification.

    Returns:
        ID of the created log entry
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO notification_log
        (subscriber_id, notification_type, digest_date, merger_count, status,
         error_message, email_subject, resend_email_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            subscriber_id,
            notification_type,
            digest_date.isoformat() if digest_date else None,
            merger_count,
            status,
            error_message,
            email_subject,
            resend_email_id,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_subscriber_stats(conn: sqlite3.Connection) -> Dict[str, int]:
    """Get subscriber statistics."""
    cursor = conn.cursor()

    # Total subscribers
    cursor.execute("SELECT COUNT(*) FROM subscribers")
    total = cursor.fetchone()[0]

    # Verified subscribers
    cursor.execute("SELECT COUNT(*) FROM subscribers WHERE verified = 1")
    verified = cursor.fetchone()[0]

    # Active subscribers (verified and not unsubscribed)
    cursor.execute(
        "SELECT COUNT(*) FROM subscribers WHERE verified = 1 AND unsubscribed = 0"
    )
    active = cursor.fetchone()[0]

    # Unsubscribed
    cursor.execute("SELECT COUNT(*) FROM subscribers WHERE unsubscribed = 1")
    unsubscribed = cursor.fetchone()[0]

    # Pending verification
    cursor.execute("SELECT COUNT(*) FROM subscribers WHERE verified = 0 AND unsubscribed = 0")
    pending = cursor.fetchone()[0]

    return {
        "total": total,
        "verified": verified,
        "active": active,
        "unsubscribed": unsubscribed,
        "pending_verification": pending,
    }
