"""
Consolidated date parsing utilities for ACCC merger data extraction.

This module provides a single source of truth for all date parsing operations,
replacing multiple scattered parse functions across the codebase.
"""

import re
from datetime import datetime
from typing import Optional


def parse_iso_datetime(date_str: str) -> Optional[datetime]:
    """
    Parse an ISO format date/datetime string to a datetime object.

    Handles multiple ISO format variants:
    - ISO 8601 with timezone: "2025-11-21T12:00:00Z" or "2025-11-21T12:00:00+00:00"
    - Simple date format: "2025-11-21"
    - ISO format without timezone: "2025-11-21T12:00:00"

    Args:
        date_str: ISO format date or datetime string

    Returns:
        Python datetime object, or None if parsing fails

    Examples:
        >>> parse_iso_datetime("2025-11-21T12:00:00Z")
        datetime.datetime(2025, 11, 21, 12, 0, 0, tzinfo=datetime.timezone.utc)

        >>> parse_iso_datetime("2025-11-21")
        datetime.datetime(2025, 11, 21, 0, 0, 0)

        >>> parse_iso_datetime(None)
        None
    """
    if not date_str:
        return None

    try:
        # Handle ISO format with timezone suffix 'Z' (UTC)
        if 'T' in date_str:
            if date_str.endswith('Z'):
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return datetime.fromisoformat(date_str)

        # Handle simple date format (YYYY-MM-DD)
        return datetime.strptime(date_str, '%Y-%m-%d')

    except (ValueError, TypeError, AttributeError):
        return None


def parse_text_to_iso(text: str, include_time: bool = False) -> Optional[str]:
    """
    Extract and parse a human-readable date from text to ISO format.

    Handles date formats like:
    - "21 November 2025"
    - "25 August 2025"
    - "3 Nov 2025" (abbreviated months)

    Args:
        text: Text containing a date string
        include_time: If True, returns ISO datetime with timestamp (YYYY-MM-DDTHH:MM:SSZ)
                     If False, returns ISO date only (YYYY-MM-DD)

    Returns:
        ISO format date string, or None if no date is found or parsing fails

    Examples:
        >>> parse_text_to_iso("Deadline: 25 August 2025")
        "2025-08-25"

        >>> parse_text_to_iso("Due on 21 November 2025", include_time=True)
        "2025-11-21T12:00:00Z"

        >>> parse_text_to_iso("No date here")
        None
    """
    if not text:
        return None

    # Pattern to match dates like "21 November 2025" or "21 Nov 2025"
    # Handles both full month names and abbreviations
    date_pattern = r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})'
    match = re.search(date_pattern, text, re.IGNORECASE)

    if not match:
        return None

    day = match.group(1)
    month = match.group(2)
    year = match.group(3)
    date_str = f"{day} {month} {year}"

    try:
        # Try full month name first
        parsed_date = datetime.strptime(date_str, "%d %B %Y")
    except ValueError:
        # Fall back to abbreviated month format
        try:
            parsed_date = datetime.strptime(date_str, "%d %b %Y")
        except ValueError:
            return None

    # Return in requested format
    if include_time:
        # Return ISO datetime with timezone (assuming midday UTC)
        return parsed_date.strftime("%Y-%m-%dT12:00:00Z")
    else:
        # Return ISO date only
        return parsed_date.strftime("%Y-%m-%d")
