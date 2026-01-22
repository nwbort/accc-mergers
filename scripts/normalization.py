"""
Shared normalization functions for ACCC merger data processing.

This module contains common data normalization functions used across multiple
scripts in the data processing pipeline to ensure consistent behavior and
avoid code duplication.
"""


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
    if 'Not approved' in determination or 'not approved' in determination:
        return 'Not approved'
    elif 'Approved' in determination or 'approved' in determination:
        return 'Approved'
    elif 'Declined' in determination or 'declined' in determination:
        return 'Declined'
    elif 'Not opposed' in determination or 'not opposed' in determination:
        return 'Not opposed'

    return determination
