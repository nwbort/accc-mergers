"""
Shared normalization functions for ACCC merger data processing.

This module contains common data normalization functions used across multiple
scripts in the data processing pipeline to ensure consistent behavior and
avoid code duplication.
"""

import re

from constants import merger_status

# Unicode dash-like characters the ACCC site uses interchangeably for the same
# wording (e.g. an event title scraped with an en dash '–' can reappear later
# with a plain hyphen '-'). Comparisons that need to recognise the "same"
# title across scrapes should normalize through this first.
_DASH_CHARS = "‐‑‒–—―−"


def normalize_dashes(text: str) -> str:
    """Replace en/em dashes and other unicode dash variants with a plain hyphen '-'."""
    if not text:
        return text
    return re.sub(f"[{_DASH_CHARS}]", "-", text)


def normalize_determination(determination: str) -> str | None:
    """
    Normalize determination strings to cleaner, standardized values.

    This function standardizes various ACCC determination formats into consistent
    values used throughout the application. It handles variations in capitalization
    and removes prefixes like "ACCC Determination".

    Args:
        determination: Raw determination string from ACCC data

    Returns:
        Normalized determination string, or None if input is empty

    Examples:
        >>> normalize_determination("ACCC Determination Approved")
        'Approved'
        >>> normalize_determination("Not approved")
        'Not approved'
        >>> normalize_determination("not opposed")
        'Not opposed'

    Note:
        The order of checks is important! "Not approved" must be checked BEFORE
        "Approved" to avoid substring matching bugs where "Not approved" would
        incorrectly match the "Approved" check.
    """
    if not determination:
        return None

    # Remove 'ACCC Determination' prefix (with or without space)
    determination = determination.replace('ACCC Determination', '').strip()

    # Normalize common patterns
    # IMPORTANT: Check for "Not approved" BEFORE "Approved" to avoid substring match
    if merger_status.NOT_APPROVED in determination or 'not approved' in determination:
        return merger_status.NOT_APPROVED
    elif merger_status.APPROVED in determination or 'approved' in determination:
        return merger_status.APPROVED
    elif merger_status.DECLINED in determination or 'declined' in determination:
        return merger_status.DECLINED
    elif merger_status.NOT_OPPOSED in determination or 'not opposed' in determination:
        return merger_status.NOT_OPPOSED

    return determination
