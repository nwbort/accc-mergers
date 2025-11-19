"""
API routes for email subscription management.
"""

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from typing import Optional
import sqlite3
from database import get_db
import subscription_service
import email_service
import re


router = APIRouter(prefix="/api/subscribe", tags=["subscriptions"])


class SubscribeRequest(BaseModel):
    email: EmailStr


class VerifyRequest(BaseModel):
    token: str


class UnsubscribeRequest(BaseModel):
    token: str


def is_valid_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


@router.post("/")
async def subscribe(request: Request, body: SubscribeRequest):
    """
    Subscribe to daily digest emails.

    This will:
    1. Create a subscriber record (or return existing if already subscribed)
    2. Send a verification email

    Returns:
        Success message with next steps
    """
    email = body.email.lower().strip()

    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email address")

    # Get metadata for logging
    user_agent = request.headers.get("user-agent")
    # In production, use X-Forwarded-For if behind proxy
    ip_address = request.client.host if request.client else None

    conn = get_db()

    try:
        # Check if subscriber already exists
        existing = subscription_service.get_subscriber_by_email(conn, email)

        if existing:
            # Already subscribed
            if existing["verified"] and not existing["unsubscribed"]:
                return {
                    "success": True,
                    "message": "You're already subscribed to the daily digest!",
                    "already_subscribed": True,
                }

            # Previously unsubscribed - allow resubscription
            if existing["unsubscribed"]:
                # Re-activate their subscription
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE subscribers
                    SET unsubscribed = 0, unsubscribed_at = NULL, receive_daily_digest = 1
                    WHERE email = ?
                    """,
                    (email,),
                )
                conn.commit()

                # Send verification email again if not verified
                if not existing["verified"]:
                    result = email_service.send_verification_email(
                        email, existing["verification_token"]
                    )

                    if not result["success"]:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Failed to send verification email: {result.get('error')}",
                        )

                return {
                    "success": True,
                    "message": "Welcome back! Please check your email to verify your subscription."
                    if not existing["verified"]
                    else "You've been resubscribed to the daily digest!",
                    "requires_verification": not existing["verified"],
                }

            # Not verified yet - resend verification
            if not existing["verified"]:
                result = email_service.send_verification_email(
                    email, existing["verification_token"]
                )

                if not result["success"]:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to send verification email: {result.get('error')}",
                    )

                return {
                    "success": True,
                    "message": "Verification email resent! Please check your inbox.",
                    "requires_verification": True,
                }

        # Create new subscriber
        subscriber = subscription_service.create_subscriber(
            conn, email, subscription_source="web", user_agent=user_agent, ip_address=ip_address
        )

        # Send verification email
        result = email_service.send_verification_email(email, subscriber["verification_token"])

        if not result["success"]:
            # Log the error but don't expose details to user
            print(f"Failed to send verification email to {email}: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail="Failed to send verification email. Please try again later.",
            )

        # Log the notification
        subscription_service.log_notification(
            conn,
            subscriber["id"],
            "verification",
            status="sent",
            resend_email_id=result.get("email_id"),
        )

        return {
            "success": True,
            "message": "Please check your email to confirm your subscription!",
            "requires_verification": True,
        }

    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=400, detail="Email already subscribed")
    except Exception as e:
        print(f"Subscription error: {e}")
        raise HTTPException(status_code=500, detail="An error occurred during subscription")
    finally:
        conn.close()


@router.post("/verify")
async def verify(body: VerifyRequest):
    """
    Verify email address using token from verification email.

    Returns:
        Success message
    """
    token = body.token.strip()

    if not token:
        raise HTTPException(status_code=400, detail="Verification token required")

    conn = get_db()

    try:
        # Get subscriber by token
        subscriber = subscription_service.get_subscriber_by_verification_token(conn, token)

        if not subscriber:
            raise HTTPException(status_code=404, detail="Invalid verification token")

        if subscriber["verified"]:
            return {
                "success": True,
                "message": "Your email is already verified!",
                "already_verified": True,
            }

        # Verify the subscriber
        success = subscription_service.verify_subscriber(conn, token)

        if not success:
            raise HTTPException(status_code=500, detail="Verification failed")

        return {
            "success": True,
            "message": "Email verified! You'll start receiving daily digests.",
            "verified": True,
        }

    finally:
        conn.close()


@router.post("/unsubscribe")
async def unsubscribe(body: UnsubscribeRequest):
    """
    Unsubscribe from all emails.

    Returns:
        Success message
    """
    token = body.token.strip()

    if not token:
        raise HTTPException(status_code=400, detail="Unsubscribe token required")

    conn = get_db()

    try:
        # Get subscriber by token
        subscriber = subscription_service.get_subscriber_by_unsubscribe_token(conn, token)

        if not subscriber:
            raise HTTPException(status_code=404, detail="Invalid unsubscribe token")

        if subscriber["unsubscribed"]:
            return {
                "success": True,
                "message": "You're already unsubscribed.",
                "already_unsubscribed": True,
            }

        # Unsubscribe
        success = subscription_service.unsubscribe(conn, token)

        if not success:
            raise HTTPException(status_code=500, detail="Unsubscribe failed")

        return {
            "success": True,
            "message": "You've been unsubscribed. Sorry to see you go!",
            "unsubscribed": True,
        }

    finally:
        conn.close()


@router.get("/stats")
async def get_stats():
    """
    Get subscription statistics (for admin use).

    Returns:
        Subscriber counts and stats
    """
    conn = get_db()

    try:
        stats = subscription_service.get_subscriber_stats(conn)
        return {
            "success": True,
            "stats": stats,
        }
    finally:
        conn.close()


# Admin/Testing Endpoints

@router.post("/admin/send-digest")
async def admin_send_digest(
    digest_date: Optional[str] = None,
    dry_run: bool = False
):
    """
    Manually trigger daily digest email send (for testing/admin use).

    Args:
        digest_date: Date in YYYY-MM-DD format (defaults to yesterday)
        dry_run: If true, don't send emails, just return what would be sent

    Returns:
        Digest send results
    """
    from datetime import date, timedelta

    # Parse date if provided
    if digest_date:
        try:
            target_date = date.fromisoformat(digest_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
    else:
        target_date = None  # Will default to yesterday in send_daily_digest

    try:
        result = digest_service.send_daily_digest(
            digest_date=target_date,
            dry_run=dry_run
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send digest: {str(e)}"
        )


@router.post("/admin/send-test-digest")
async def admin_send_test_digest(
    email: str,
    digest_date: Optional[str] = None
):
    """
    Send a test digest to a specific email address (for testing).

    Args:
        email: Email address to send test to
        digest_date: Date in YYYY-MM-DD format (defaults to yesterday)

    Returns:
        Test send result
    """
    from datetime import date

    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email address")

    # Parse date if provided
    if digest_date:
        try:
            target_date = date.fromisoformat(digest_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
    else:
        target_date = None  # Will default to yesterday

    try:
        result = digest_service.send_test_digest(
            email=email,
            digest_date=target_date
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send test digest: {str(e)}"
        )
