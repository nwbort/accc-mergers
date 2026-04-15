"""Business-day and calendar-day arithmetic against ACT public holidays.

The ACCC Act defines "business day" as a weekday that is not a public holiday
and is not within the Christmas/New Year shutdown (23 Dec - 10 Jan inclusive).
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from date_utils import parse_iso_datetime

SCRIPT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPT_DIR.parent
HOLIDAYS_JSON = REPO_ROOT / "merger-tracker" / "frontend" / "src" / "data" / "act-public-holidays.json"

PUBLIC_HOLIDAYS = None  # Loaded lazily


def load_public_holidays() -> set:
    """Load ACT public holidays from JSON file."""
    with open(HOLIDAYS_JSON, 'r') as f:
        data = json.load(f)

    holidays = set()
    for year_data in data['holidays']:
        for holiday in year_data['dates']:
            holidays.add(holiday['date'])

    return holidays


def _ensure_holidays_loaded() -> set:
    global PUBLIC_HOLIDAYS
    if PUBLIC_HOLIDAYS is None:
        PUBLIC_HOLIDAYS = load_public_holidays()
    return PUBLIC_HOLIDAYS


def is_christmas_new_year_period(date: datetime) -> bool:
    """Check if date falls in Christmas/New Year period (23 Dec - 10 Jan)."""
    month = date.month
    day = date.day

    if month == 12 and day >= 23:
        return True
    if month == 1 and day <= 10:
        return True

    return False


def is_business_day(date: datetime) -> bool:
    """Check if a date is a business day according to ACCC Act."""
    holidays = _ensure_holidays_loaded()

    # Saturday (5) or Sunday (6)
    if date.weekday() in (5, 6):
        return False

    # Christmas/New Year period
    if is_christmas_new_year_period(date):
        return False

    # Public holiday
    date_string = date.strftime('%Y-%m-%d')
    if date_string in holidays:
        return False

    return True


def _count_weekdays_in_range(start: datetime, end: datetime) -> int:
    """Count weekdays (Mon-Fri) from start to end inclusive using arithmetic."""
    if start > end:
        return 0
    total_days = (end - start).days + 1
    full_weeks, remainder = divmod(total_days, 7)
    weekdays = full_weeks * 5
    start_weekday = start.weekday()  # 0=Mon, 6=Sun
    for i in range(remainder):
        if (start_weekday + i) % 7 < 5:
            weekdays += 1
    return weekdays


def calculate_business_days(start_date_str: str, end_date_str: str) -> int | None:
    """Calculate business days between two ISO date strings (exclusive of start, inclusive of end).

    The start date (notification date) is day 0; counting begins the following day,
    matching the ACCC convention where BD 1 is the day after notification.

    Uses arithmetic weekday counting and subtracts holidays/Christmas periods
    instead of iterating day-by-day.
    """
    if not start_date_str or not end_date_str:
        return None

    holidays = _ensure_holidays_loaded()

    try:
        start = parse_iso_datetime(start_date_str)
        end = parse_iso_datetime(end_date_str)
        if start is None or end is None:
            return None

        start = start.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        end = end.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)

        # BD 1 is the day after notification, so exclude the start date itself
        start += timedelta(days=1)

        if start > end:
            return 0

        # Step 1: Count all weekdays (Mon-Fri) arithmetically
        business_days = _count_weekdays_in_range(start, end)

        # Step 2: Subtract weekdays that fall in Christmas/New Year periods (Dec 23 - Jan 10)
        # Enumerate all Christmas/New Year periods that could overlap [start, end]
        for year in range(start.year - 1, end.year + 1):
            # Each period runs from Dec 23 of year to Jan 10 of year+1
            xmas_start = datetime(year, 12, 23)
            xmas_end = datetime(year + 1, 1, 10)

            # Clamp to [start, end]
            overlap_start = max(xmas_start, start)
            overlap_end = min(xmas_end, end)

            if overlap_start <= overlap_end:
                business_days -= _count_weekdays_in_range(overlap_start, overlap_end)

        # Step 3: Subtract public holidays that fall on weekdays outside Christmas/New Year
        for holiday_str in holidays:
            holiday = datetime.strptime(holiday_str, '%Y-%m-%d')
            if start <= holiday <= end:
                if holiday.weekday() < 5 and not is_christmas_new_year_period(holiday):
                    business_days -= 1

        return max(business_days, 0)
    except (ValueError, AttributeError):
        return None


def add_business_days(start_date: datetime, n: int) -> datetime:
    """Return the date that is the nth business day from start_date (counting start_date as day 1)."""
    _ensure_holidays_loaded()

    current = start_date
    count = 0
    while True:
        if is_business_day(current):
            count += 1
        if count == n:
            return current
        current += timedelta(days=1)


def subtract_business_days(end_date: datetime, n: int) -> datetime:
    """Return the date that is the nth business day counting backward from end_date (counting end_date as day 1)."""
    _ensure_holidays_loaded()

    current = end_date
    count = 0
    while True:
        if is_business_day(current):
            count += 1
        if count == n:
            return current
        current -= timedelta(days=1)


def calculate_calendar_days(start_date_str: str, end_date_str: str) -> int | None:
    """Calculate calendar days between two ISO date strings."""
    if not start_date_str or not end_date_str:
        return None

    try:
        start = parse_iso_datetime(start_date_str)
        end = parse_iso_datetime(end_date_str)
        if start is None or end is None:
            return None
        return (end - start).days
    except (ValueError, AttributeError):
        return None
