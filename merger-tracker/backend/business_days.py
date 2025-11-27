"""
Business day calculations according to ACCC Act.

For the purposes of this Part, a business day is a day that is not:
(a) a Saturday; or
(b) a Sunday; or
(c) a public holiday in the Australian Capital Territory; or
(d) a day occurring between:
    (i) 23 December in any year; and
    (ii) the following 10 January.
"""

from datetime import datetime, timedelta
from typing import Optional
import json
import os

# Load ACT public holidays from JSON file
def load_public_holidays():
    """Load ACT public holidays from JSON file."""
    json_path = os.path.join(
        os.path.dirname(__file__),
        '../frontend/src/data/act-public-holidays.json'
    )

    with open(json_path, 'r') as f:
        data = json.load(f)

    # Build a set of holiday dates for fast lookup
    holidays = set()
    for year_data in data['holidays']:
        for holiday in year_data['dates']:
            holidays.add(holiday['date'])

    return holidays

# Cache the public holidays
PUBLIC_HOLIDAYS = load_public_holidays()


def is_christmas_new_year_period(date: datetime) -> bool:
    """
    Check if a date falls in the Christmas/New Year period (23 Dec - 10 Jan).
    As per ACCC Act: days occurring between 23 December and 10 January are not business days.
    """
    month = date.month
    day = date.day

    # December 23-31
    if month == 12 and day >= 23:
        return True

    # January 1-10
    if month == 1 and day <= 10:
        return True

    return False


def is_business_day(date: datetime) -> bool:
    """
    Check if a date is a business day according to ACCC Act.

    Business day excludes:
    - Saturdays (weekday 5)
    - Sundays (weekday 6)
    - ACT public holidays
    - Days between 23 December and 10 January (inclusive)
    """
    # Saturday (5) or Sunday (6)
    if date.weekday() in (5, 6):
        return False

    # Christmas/New Year period (23 Dec - 10 Jan)
    if is_christmas_new_year_period(date):
        return False

    # Check if it's a public holiday
    date_string = date.strftime('%Y-%m-%d')
    if date_string in PUBLIC_HOLIDAYS:
        return False

    return True


def calculate_business_days(start_date: Optional[str], end_date: Optional[str]) -> Optional[int]:
    """
    Calculate the number of business days between two dates (inclusive of start date).

    Args:
        start_date: Start date in ISO format
        end_date: End date in ISO format

    Returns:
        Number of business days, or None if dates are invalid
    """
    if not start_date or not end_date:
        return None

    try:
        # Parse ISO format dates (with or without timezone)
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))

        # Strip time component for date comparison
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = end.replace(hour=0, minute=0, second=0, microsecond=0)

        business_days = 0
        current_date = start

        # Include the start date in the calculation
        while current_date <= end:
            if is_business_day(current_date):
                business_days += 1
            current_date += timedelta(days=1)

        return business_days
    except (ValueError, AttributeError) as e:
        print(f"Error calculating business days: {e}")
        return None
