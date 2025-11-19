"""
Email service for sending notifications via Resend.
"""

import os
import secrets
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
import resend


# Get API key from environment
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "ACCC Mergers <notifications@mergers.fyi>")
BASE_URL = os.getenv("BASE_URL", "https://mergers.fyi")

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


def generate_token() -> str:
    """Generate a secure random token for verification/unsubscribe."""
    return secrets.token_urlsafe(32)


def send_verification_email(email: str, verification_token: str) -> Dict[str, Any]:
    """
    Send email verification link to new subscriber.

    Args:
        email: Subscriber's email address
        verification_token: Unique verification token

    Returns:
        Response from Resend API
    """
    verification_url = f"{BASE_URL}/verify?token={verification_token}"

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; border-radius: 8px; padding: 30px; margin-bottom: 20px;">
        <h1 style="color: #2563eb; margin-top: 0; font-size: 24px;">Confirm Your Subscription</h1>
        <p style="font-size: 16px; margin-bottom: 25px;">
            Thanks for subscribing to ACCC Mergers daily digest! Click the button below to confirm your email address.
        </p>
        <a href="{verification_url}" style="display: inline-block; background-color: #2563eb; color: white; text-decoration: none; padding: 12px 30px; border-radius: 6px; font-weight: 600; font-size: 16px;">
            Confirm Subscription
        </a>
        <p style="font-size: 14px; color: #666; margin-top: 25px;">
            Or copy and paste this link into your browser:<br>
            <a href="{verification_url}" style="color: #2563eb; word-break: break-all;">{verification_url}</a>
        </p>
    </div>
    <div style="font-size: 12px; color: #999; text-align: center;">
        <p>You're receiving this because you (or someone) subscribed to ACCC Mergers notifications at {BASE_URL}</p>
        <p>If you didn't request this, you can safely ignore this email.</p>
    </div>
</body>
</html>
"""

    plain_text = f"""
Confirm Your Subscription to ACCC Mergers Daily Digest

Thanks for subscribing! Click the link below to confirm your email address:

{verification_url}

If you didn't request this, you can safely ignore this email.

---
ACCC Mergers Tracker
{BASE_URL}
"""

    try:
        response = resend.Emails.send({
            "from": FROM_EMAIL,
            "to": email,
            "subject": "Confirm your ACCC Mergers subscription",
            "html": html_content,
            "text": plain_text,
        })
        return {"success": True, "email_id": response.get("id")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_daily_digest(
    email: str,
    unsubscribe_token: str,
    digest_date: date,
    new_mergers: List[Dict[str, Any]],
    updated_mergers: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Send daily digest email with merger updates.

    Args:
        email: Subscriber's email
        unsubscribe_token: Token for unsubscribe link
        digest_date: Date this digest covers
        new_mergers: List of new mergers added
        updated_mergers: List of mergers with updates

    Returns:
        Response from Resend API
    """
    unsubscribe_url = f"{BASE_URL}/unsubscribe?token={unsubscribe_token}"
    date_str = digest_date.strftime("%B %d, %Y")

    # Build HTML content
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 650px; margin: 0 auto; padding: 20px; background-color: #f8f9fa;">
    <div style="background-color: white; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <h1 style="color: #2563eb; margin-top: 0; font-size: 28px; border-bottom: 3px solid #2563eb; padding-bottom: 15px;">
            ACCC Mergers Daily Digest
        </h1>
        <p style="font-size: 14px; color: #666; margin-bottom: 30px;">
            {date_str}
        </p>
"""

    # Add new mergers section
    if new_mergers:
        html_content += f"""
        <h2 style="color: #16a34a; font-size: 20px; margin-top: 30px; margin-bottom: 15px;">
            🆕 New Mergers ({len(new_mergers)})
        </h2>
"""
        for merger in new_mergers:
            merger_url = f"{BASE_URL}/mergers/{merger['merger_id']}"
            html_content += f"""
        <div style="background-color: #f0fdf4; border-left: 4px solid #16a34a; padding: 15px; margin-bottom: 15px; border-radius: 4px;">
            <h3 style="margin: 0 0 8px 0; font-size: 18px;">
                <a href="{merger_url}" style="color: #15803d; text-decoration: none;">
                    {merger['merger_name']}
                </a>
            </h3>
            <p style="margin: 5px 0; font-size: 14px; color: #666;">
                <strong>ID:</strong> {merger['merger_id']} |
                <strong>Status:</strong> {merger.get('status', 'N/A')}
            </p>
            {f"<p style='margin: 10px 0 0 0; font-size: 14px;'>{merger.get('merger_description', '')[:200]}...</p>" if merger.get('merger_description') else ''}
        </div>
"""

    # Add updated mergers section
    if updated_mergers:
        html_content += f"""
        <h2 style="color: #ea580c; font-size: 20px; margin-top: 30px; margin-bottom: 15px;">
            📝 Recent Updates ({len(updated_mergers)})
        </h2>
"""
        for merger in updated_mergers:
            merger_url = f"{BASE_URL}/mergers/{merger['merger_id']}"
            changes = merger.get("changes", [])
            html_content += f"""
        <div style="background-color: #fff7ed; border-left: 4px solid #ea580c; padding: 15px; margin-bottom: 15px; border-radius: 4px;">
            <h3 style="margin: 0 0 8px 0; font-size: 18px;">
                <a href="{merger_url}" style="color: #c2410c; text-decoration: none;">
                    {merger['merger_name']}
                </a>
            </h3>
            <p style="margin: 5px 0; font-size: 14px; color: #666;">
                <strong>ID:</strong> {merger['merger_id']}
            </p>
            <ul style="margin: 10px 0 0 0; padding-left: 20px; font-size: 14px;">
"""
            for change in changes:
                html_content += f"                <li>{change}</li>\n"
            html_content += """
            </ul>
        </div>
"""

    # No activity message
    if not new_mergers and not updated_mergers:
        html_content += """
        <div style="background-color: #f1f5f9; padding: 30px; text-align: center; border-radius: 8px; margin: 20px 0;">
            <p style="font-size: 16px; color: #64748b; margin: 0;">
                No new mergers or updates today.
            </p>
        </div>
"""

    # Footer
    html_content += f"""
        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center;">
            <p style="font-size: 14px; margin-bottom: 15px;">
                <a href="{BASE_URL}" style="color: #2563eb; text-decoration: none; font-weight: 600;">
                    View All Mergers
                </a>
            </p>
            <p style="font-size: 12px; color: #999;">
                You're receiving this daily digest because you subscribed at {BASE_URL}<br>
                <a href="{unsubscribe_url}" style="color: #999; text-decoration: underline;">Unsubscribe</a>
            </p>
        </div>
    </div>
</body>
</html>
"""

    # Build plain text version
    plain_text = f"""
ACCC MERGERS DAILY DIGEST
{date_str}
{'=' * 50}

"""

    if new_mergers:
        plain_text += f"NEW MERGERS ({len(new_mergers)})\n{'-' * 50}\n\n"
        for merger in new_mergers:
            merger_url = f"{BASE_URL}/mergers/{merger['merger_id']}"
            plain_text += f"{merger['merger_name']}\n"
            plain_text += f"ID: {merger['merger_id']} | Status: {merger.get('status', 'N/A')}\n"
            plain_text += f"View: {merger_url}\n\n"

    if updated_mergers:
        plain_text += f"\nRECENT UPDATES ({len(updated_mergers)})\n{'-' * 50}\n\n"
        for merger in updated_mergers:
            merger_url = f"{BASE_URL}/mergers/{merger['merger_id']}"
            plain_text += f"{merger['merger_name']}\n"
            plain_text += f"ID: {merger['merger_id']}\n"
            changes = merger.get("changes", [])
            for change in changes:
                plain_text += f"  - {change}\n"
            plain_text += f"View: {merger_url}\n\n"

    if not new_mergers and not updated_mergers:
        plain_text += "No new mergers or updates today.\n\n"

    plain_text += f"""
{'=' * 50}
View all mergers: {BASE_URL}

You're receiving this daily digest because you subscribed at {BASE_URL}
To unsubscribe: {unsubscribe_url}
"""

    subject = f"ACCC Mergers Daily Digest - {date_str}"
    if new_mergers and updated_mergers:
        subject += f" ({len(new_mergers)} new, {len(updated_mergers)} updates)"
    elif new_mergers:
        subject += f" ({len(new_mergers)} new)"
    elif updated_mergers:
        subject += f" ({len(updated_mergers)} updates)"

    try:
        response = resend.Emails.send({
            "from": FROM_EMAIL,
            "to": email,
            "subject": subject,
            "html": html_content,
            "text": plain_text,
        })
        return {"success": True, "email_id": response.get("id")}
    except Exception as e:
        return {"success": False, "error": str(e)}
