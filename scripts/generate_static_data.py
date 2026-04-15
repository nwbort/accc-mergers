#!/usr/bin/env python3
"""
Generate static JSON data files for Cloudflare Pages deployment.

This script reads mergers.json and generates pre-computed JSON files
that the frontend can consume directly without a backend API.

Output files:
  data/output/ (for offline analysis, not deployed):
  - mergers.json      - All mergers wrapped in {mergers: [...]} (full enriched data)

  merger-tracker/frontend/public/data/ (deployed to Cloudflare Pages):
  - mergers/{id}.json - Individual merger files (one per merger)
  - mergers/list-page-{N}.json - Paginated lightweight merger lists (50/page)
  - mergers/list-meta.json - Pagination metadata for merger list
  - stats.json        - Aggregated statistics
  - timeline-page-{N}.json - Paginated timeline events (100/page)
  - timeline-meta.json - Pagination metadata for timeline
  - industries.json   - ANZSIC codes with merger counts
  - industries/{code}.json - Mergers per industry code
  - upcoming-events.json - Future consultation/determination dates
  - commentary.json   - Mergers with user commentary
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

from cutoff import is_waiver_merger
from date_utils import parse_iso_datetime
from normalization import normalize_determination

# Paths
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
MERGERS_JSON = REPO_ROOT / "data" / "processed" / "mergers.json"
COMMENTARY_JSON = REPO_ROOT / "data" / "processed" / "commentary.json"
HOLIDAYS_JSON = REPO_ROOT / "merger-tracker" / "frontend" / "src" / "data" / "act-public-holidays.json"
OUTPUT_DIR = REPO_ROOT / "merger-tracker" / "frontend" / "public" / "data"
DATA_OUTPUT_DIR = REPO_ROOT / "data" / "output"


def load_public_holidays():
    """Load ACT public holidays from JSON file."""
    with open(HOLIDAYS_JSON, 'r') as f:
        data = json.load(f)
    
    holidays = set()
    for year_data in data['holidays']:
        for holiday in year_data['dates']:
            holidays.add(holiday['date'])
    
    return holidays


PUBLIC_HOLIDAYS = None  # Loaded lazily


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
    global PUBLIC_HOLIDAYS
    if PUBLIC_HOLIDAYS is None:
        PUBLIC_HOLIDAYS = load_public_holidays()
    
    # Saturday (5) or Sunday (6)
    if date.weekday() in (5, 6):
        return False
    
    # Christmas/New Year period
    if is_christmas_new_year_period(date):
        return False
    
    # Public holiday
    date_string = date.strftime('%Y-%m-%d')
    if date_string in PUBLIC_HOLIDAYS:
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

    global PUBLIC_HOLIDAYS
    if PUBLIC_HOLIDAYS is None:
        PUBLIC_HOLIDAYS = load_public_holidays()

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
        for holiday_str in PUBLIC_HOLIDAYS:
            holiday = datetime.strptime(holiday_str, '%Y-%m-%d')
            if start <= holiday <= end:
                if holiday.weekday() < 5 and not is_christmas_new_year_period(holiday):
                    business_days -= 1

        return max(business_days, 0)
    except (ValueError, AttributeError):
        return None


def add_business_days(start_date: datetime, n: int) -> datetime:
    """Return the date that is the nth business day from start_date (counting start_date as day 1)."""
    global PUBLIC_HOLIDAYS
    if PUBLIC_HOLIDAYS is None:
        PUBLIC_HOLIDAYS = load_public_holidays()

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
    global PUBLIC_HOLIDAYS
    if PUBLIC_HOLIDAYS is None:
        PUBLIC_HOLIDAYS = load_public_holidays()

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


def extract_phase_from_event(event_title: str) -> str | None:
    """Extract phase information from event title."""
    if not event_title:
        return None
    if 'Phase 1' in event_title:
        return 'Phase 1'
    elif 'Phase 2' in event_title:
        return 'Phase 2'
    elif 'Public Benefits' in event_title or 'public benefits' in event_title:
        return 'Public Benefits'
    elif 'Waiver' in event_title or 'waiver' in event_title:
        return 'Waiver'
    elif 'notified' in event_title:
        return 'Phase 1'  # Notification always starts Phase 1
    return None


# Mergers that were initially filed as waiver applications but declined, then re-filed
# as formal notifications. Each entry maps both directions (WA->MN and MN->WA).
RELATED_MERGERS = {
    'WA-35003': {'merger_id': 'MN-85007', 'relationship': 'refiled_as'},
    'MN-85007': {'merger_id': 'WA-35003', 'relationship': 'refiled_from'},
    'WA-01087': {'merger_id': 'MN-20013', 'relationship': 'refiled_as'},
    'MN-20013': {'merger_id': 'WA-01087', 'relationship': 'refiled_from'},
    'WA-65003': {'merger_id': 'MN-40005', 'relationship': 'refiled_as'},
    'MN-40005': {'merger_id': 'WA-65003', 'relationship': 'refiled_from'},
    'WA-70003': {'merger_id': 'MN-40008', 'relationship': 'refiled_as'},
    'MN-40008': {'merger_id': 'WA-70003', 'relationship': 'refiled_from'},
}


def load_commentary() -> dict:
    """Load user commentary from commentary.json if it exists."""
    if not COMMENTARY_JSON.exists():
        return {}

    try:
        with open(COMMENTARY_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Filter out metadata keys (starting with _)
        return {k: v for k, v in data.items() if not k.startswith('_')}
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load commentary.json: {e}")
        return {}


def enrich_merger(merger: dict, commentary: dict = None) -> dict:
    """Add computed fields to a merger (phase determinations, etc.)."""
    m = merger.copy()

    # Normalize the determination
    m['accc_determination'] = normalize_determination(m.get('accc_determination'))

    # Add is_waiver flag
    m['is_waiver'] = is_waiver_merger(merger)

    # Add user commentary if available
    merger_id = m.get('merger_id', '')
    if commentary and merger_id in commentary:
        m['comments'] = commentary[merger_id].get('comments', [])

    # Compute phase-specific determinations based on stage and events
    phase_1_det = None
    phase_1_det_date = None
    phase_2_det = None
    phase_2_det_date = None
    pb_det = None
    pb_det_date = None

    # Check events for Phase 2 review decision (indicates Phase 1 completion)
    for event in m.get('events', []):
        title = event.get('title', '')
        if 'subject to Phase 2 review' in title:
            phase_1_det = 'Referred to phase 2'
            phase_1_det_date = event.get('date')
            break

    if m.get('accc_determination') and m.get('determination_publication_date'):
        stage = m.get('stage', 'Phase 1')
        det = m['accc_determination']
        det_date = m['determination_publication_date']

        if 'Phase 1' in stage:
            phase_1_det = det
            phase_1_det_date = det_date
        elif 'Phase 2' in stage:
            phase_2_det = det
            phase_2_det_date = det_date
        elif 'Public' in stage or 'Benefits' in stage:
            pb_det = det
            pb_det_date = det_date
    
    m['phase_1_determination'] = phase_1_det
    m['phase_1_determination_date'] = phase_1_det_date
    m['phase_2_determination'] = phase_2_det
    m['phase_2_determination_date'] = phase_2_det_date
    m['public_benefits_determination'] = pb_det
    m['public_benefits_determination_date'] = pb_det_date
    
    # Compute competition concerns notice date for Phase 2 mergers
    # The notice is due by BD 25 of Phase 2 (Phase 2 BD 1 = end_of_determination_period - 90 BDs)
    stage = m.get('stage', '')
    phase2_end = m.get('end_of_determination_period')
    notice_already_issued = any(
        'competition concern' in event.get('title', '').lower()
        for event in m.get('events', [])
    )
    if stage and 'Phase 2' in stage and phase2_end and not notice_already_issued:
        try:
            phase2_end_date = parse_iso_datetime(phase2_end)
            if phase2_end_date is None:
                raise ValueError("unparseable date")
            phase2_end_date = phase2_end_date.replace(tzinfo=None)
            phase2_start_date = subtract_business_days(phase2_end_date, 90)
            notice_date = add_business_days(phase2_start_date, 25)
            m['competition_concerns_notice_date'] = notice_date.strftime('%Y-%m-%dT12:00:00Z')
        except (ValueError, AttributeError):
            pass

    # Ensure anzsic_codes exists
    if 'anzsic_codes' not in m:
        m['anzsic_codes'] = []

    # Add phase to events
    if 'events' in m:
        for event in m['events']:
            if 'phase' not in event:
                event['phase'] = extract_phase_from_event(event.get('title', ''))
    
    return m


def generate_mergers_json(enriched_mergers: list) -> dict:
    """Generate mergers.json with wrapper format (expects pre-enriched mergers)."""
    return {"mergers": enriched_mergers}


def generate_individual_merger_files(enriched_mergers: list) -> None:
    """Generate individual JSON files for each merger (expects pre-enriched mergers)."""
    mergers_dir = OUTPUT_DIR / "mergers"
    mergers_dir.mkdir(parents=True, exist_ok=True)

    for merger in enriched_mergers:
        merger_id = merger.get('merger_id', '')

        if merger_id:
            output_path = mergers_dir / f"{merger_id}.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(merger, f, indent=2)



def generate_paginated_list(enriched_mergers: list, page_size: int = 50) -> None:
    """Generate paginated merger list files (expects pre-enriched mergers)."""
    mergers_dir = OUTPUT_DIR / "mergers"
    mergers_dir.mkdir(parents=True, exist_ok=True)

    # Generate lightweight merger data
    lightweight_mergers = []
    for m in enriched_mergers:
        lightweight_mergers.append({
            "merger_id": m.get('merger_id'),
            "merger_name": m.get('merger_name'),
            "status": m.get('status'),
            "accc_determination": m.get('accc_determination'),
            "is_waiver": m.get('is_waiver', False),
            "effective_notification_datetime": m.get('effective_notification_datetime'),
            "determination_publication_date": m.get('determination_publication_date'),
            "end_of_determination_period": m.get('end_of_determination_period'),
            "stage": m.get('stage'),
            "acquirers": m.get('acquirers', []),
            "targets": m.get('targets', []),
            "other_parties": m.get('other_parties', []),
            "anzsic_codes": m.get('anzsic_codes') or m.get('anszic_codes', []),
            "url": m.get('url')
        })

    # Sort by notification date ascending (oldest first, newest last).
    # New mergers always append to the last page, so only the last page file
    # changes per scrape run rather than cascading through all pages.
    lightweight_mergers.sort(key=lambda x: x.get('effective_notification_datetime') or '')

    total_mergers = len(lightweight_mergers)
    total_pages = (total_mergers + page_size - 1) // page_size

    # Generate page files
    for page_num in range(1, total_pages + 1):
        start_idx = (page_num - 1) * page_size
        end_idx = min(start_idx + page_size, total_mergers)
        page_data = {
            "mergers": lightweight_mergers[start_idx:end_idx],
            "page": page_num,
            "page_size": page_size,
        }

        output_path = mergers_dir / f"list-page-{page_num}.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(page_data, f, indent=2)

    # Generate metadata file
    meta_data = {
        "total": total_mergers,
        "page_size": page_size,
        "total_pages": total_pages
    }
    meta_path = mergers_dir / "list-meta.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta_data, f, indent=2)

    print(f"✓ Generated {total_pages} paginated list files ({page_size} mergers/page)")


def generate_stats_json(enriched_mergers: list) -> dict:
    """Generate aggregated statistics (expects pre-enriched mergers, excluding waiver mergers)."""
    # Filter out waiver mergers for stats (using pre-enriched is_waiver field)
    notification_mergers = [m for m in enriched_mergers if not m.get('is_waiver', False)]
    waiver_mergers = [m for m in enriched_mergers if m.get('is_waiver', False)]

    total_notifications = len(notification_mergers)
    total_waivers = len(waiver_mergers)

    # By status (notifications only)
    by_status = defaultdict(int)
    for m in notification_mergers:
        status = m.get('status', 'Unknown')
        by_status[status] += 1

    # By Phase 1 determination (notifications only)
    # Use pre-enriched phase_1_determination which correctly identifies "Referred to phase 2"
    by_determination = defaultdict(int)
    for m in notification_mergers:
        det = m.get('phase_1_determination')
        if det:
            by_determination[det] += 1

    # By waiver determination
    by_waiver_determination = defaultdict(int)
    for m in waiver_mergers:
        # Use pre-enriched determination
        det = m.get('accc_determination')
        if det:
            by_waiver_determination[det] += 1
    
    # Phase durations (notifications only)
    durations = []
    business_durations = []

    for m in notification_mergers:
        start = m.get('effective_notification_datetime')
        end = m.get('determination_publication_date')

        if start and end:
            cal_days = calculate_calendar_days(start, end)
            if cal_days is not None:
                durations.append(cal_days)

            bus_days = calculate_business_days(start, end)
            if bus_days is not None:
                business_durations.append(bus_days)

    avg_duration = sum(durations) / len(durations) if durations else None
    median_duration = sorted(durations)[len(durations) // 2] if durations else None

    avg_business = sum(business_durations) / len(business_durations) if business_durations else None
    median_business = sorted(business_durations)[len(business_durations) // 2] if business_durations else None

    # Pre-compute percentile statistics for business days
    total_completed = len(business_durations)
    percentile_stats = None
    if total_completed > 0:
        day15_count = sum(1 for d in business_durations if d <= 15)
        day20_count = sum(1 for d in business_durations if d <= 20)
        day30_count = sum(1 for d in business_durations if d <= 30)

        percentile_stats = {
            "day15": {
                "count": day15_count,
                "percentage": round((day15_count / total_completed) * 100, 1)
            },
            "day20": {
                "count": day20_count,
                "percentage": round((day20_count / total_completed) * 100, 1)
            },
            "day30": {
                "count": day30_count,
                "percentage": round((day30_count / total_completed) * 100, 1)
            }
        }
    
    # Top industries (including waivers)
    industry_counts = defaultdict(int)
    for m in enriched_mergers:
        codes = m.get('anzsic_codes') or m.get('anszic_codes') or []
        for code in codes:
            industry_counts[code.get('name', 'Unknown')] += 1

    top_industries = [
        {"name": name, "count": count}
        for name, count in sorted(industry_counts.items(), key=lambda x: -x[1])[:10]
    ]

    # Recent mergers (include all but mark waivers) - using pre-enriched data
    sorted_mergers = sorted(
        enriched_mergers,
        key=lambda x: x.get('effective_notification_datetime', ''),
        reverse=True
    )
    recent_mergers = [
        {
            "merger_id": m['merger_id'],
            "merger_name": m['merger_name'],
            "status": m.get('status'),
            "accc_determination": m.get('accc_determination'),
            "effective_notification_datetime": m.get('effective_notification_datetime'),
            "is_waiver": m.get('is_waiver', False)
        }
        for m in sorted_mergers[:5]
    ]

    # Recent determinations (approvals, declines, stage transitions) - using pre-enriched data
    determination_events = []

    for m in enriched_mergers:
        merger_id = m['merger_id']
        merger_name = m['merger_name']
        is_waiver = m.get('is_waiver', False)

        # Check for final determination (approved/not approved) - using pre-enriched determination
        det = m.get('accc_determination')
        det_date = m.get('determination_publication_date')
        page_modified = m.get('page_modified_datetime', '')
        if det and det_date:
            determination_events.append({
                "merger_id": merger_id,
                "merger_name": merger_name,
                "determination": det,
                "determination_date": det_date,
                "page_modified_datetime": page_modified,
                "determination_type": "final",
                "is_waiver": is_waiver,
                "stage": m.get('stage')
            })

        # Check for Phase 2 referrals (stage transitions)
        for event in m.get('events', []):
            title = event.get('title', '')
            if 'subject to Phase 2 review' in title:
                determination_events.append({
                    "merger_id": merger_id,
                    "merger_name": merger_name,
                    "determination": "Referred to phase 2",
                    "determination_date": event.get('date'),
                    "page_modified_datetime": page_modified,
                    "determination_type": "phase_transition",
                    "is_waiver": is_waiver,
                    "stage": "Phase 2 - detailed assessment"
                })
                break

    # Sort by determination date descending, then by page modification time descending
    # This ensures determinations on the same day are sorted by the time they were added to the register
    determination_events.sort(
        key=lambda x: (x.get('determination_date', ''), x.get('page_modified_datetime', '')),
        reverse=True
    )
    recent_determinations = determination_events[:6]

    # Build phase_duration object with pre-computed stats
    phase_duration_data = {
        "average_days": avg_duration,
        "median_days": median_duration,
        "average_business_days": avg_business,
        "median_business_days": median_business
    }

    # Add percentile stats if available
    if percentile_stats:
        phase_duration_data["percentiles"] = percentile_stats

    return {
        "total_mergers": total_notifications,
        "total_waivers": total_waivers,
        "by_status": dict(by_status),
        "by_determination": dict(by_determination),
        "by_waiver_determination": dict(by_waiver_determination),
        "phase_duration": phase_duration_data,
        "top_industries": top_industries,
        "recent_mergers": recent_mergers,
        "recent_determinations": recent_determinations
    }



def generate_paginated_timeline(enriched_mergers: list, page_size: int = 100) -> None:
    """Generate paginated timeline files (expects pre-enriched mergers)."""
    events = []

    for m in enriched_mergers:
        merger_id = m['merger_id']
        merger_name = m['merger_name']
        merger_is_waiver = m.get('is_waiver', False)

        for event in m.get('events', []):
            title = event.get('title', '')
            events.append({
                "date": event.get('date'),
                "title": title,
                "display_title": event.get('display_title'),
                "url": event.get('url'),
                "url_gh": event.get('url_gh'),
                "status": event.get('status'),
                "merger_id": merger_id,
                "merger_name": merger_name,
                "phase": event.get('phase') or extract_phase_from_event(title),
                "is_waiver": merger_is_waiver
            })

    # Sort by date ascending (oldest first, newest last).
    # New events always append to the last page, so only the last page file
    # changes per scrape run rather than cascading through all pages.
    events.sort(key=lambda x: x.get('date', ''))

    total_events = len(events)
    total_pages = (total_events + page_size - 1) // page_size

    # Generate page files
    for page_num in range(1, total_pages + 1):
        start_idx = (page_num - 1) * page_size
        end_idx = min(start_idx + page_size, total_events)
        page_data = {
            "events": events[start_idx:end_idx],
            "page": page_num,
            "page_size": page_size,
        }

        output_path = OUTPUT_DIR / f"timeline-page-{page_num}.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(page_data, f, indent=2)

    # Generate metadata file
    meta_data = {
        "total": total_events,
        "page_size": page_size,
        "total_pages": total_pages
    }
    meta_path = OUTPUT_DIR / "timeline-meta.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta_data, f, indent=2)

    print(f"✓ Generated {total_pages} paginated timeline files ({page_size} events/page)")


def generate_industries_json(enriched_mergers: list) -> dict:
    """Generate industry list with merger counts (expects pre-enriched mergers)."""
    # Group by (code, name) to count unique mergers
    industry_mergers = defaultdict(set)

    for m in enriched_mergers:
        merger_id = m['merger_id']
        # Handle both spellings
        codes = m.get('anzsic_codes') or m.get('anszic_codes') or []
        for code in codes:
            key = (code.get('code', ''), code.get('name', ''))
            industry_mergers[key].add(merger_id)

    industries = [
        {
            "code": code,
            "name": name,
            "merger_count": len(merger_ids)
        }
        for (code, name), merger_ids in industry_mergers.items()
    ]

    # Sort by merger count descending
    industries.sort(key=lambda x: -x['merger_count'])

    return {"industries": industries}


def generate_individual_industry_files(enriched_mergers: list) -> None:
    """Generate individual JSON files for each industry code (expects pre-enriched mergers)."""
    industries_dir = OUTPUT_DIR / "industries"
    industries_dir.mkdir(parents=True, exist_ok=True)

    # Group mergers by industry
    industry_mergers_map = defaultdict(list)

    for m in enriched_mergers:
        merger_id = m.get('merger_id')
        merger_name = m.get('merger_name')
        status = m.get('status')
        is_waiver = m.get('is_waiver', False)
        # Get latest date for sorting
        determination_date = m.get('determination_publication_date') or ''
        notification_date = m.get('effective_notification_datetime') or ''

        # Handle both spellings
        codes = m.get('anzsic_codes') or m.get('anszic_codes') or []
        for code_obj in codes:
            code = code_obj.get('code', '')
            name = code_obj.get('name', '')

            if code:  # Only add if code exists
                # Create minimal merger object with only fields needed by frontend
                merger_summary = {
                    "merger_id": merger_id,
                    "merger_name": merger_name,
                    "is_waiver": is_waiver,
                    "status": status,
                    # Internal field for sorting only (not displayed)
                    "_latest_date": max(determination_date, notification_date)
                }

                # Use code as key (name can vary)
                industry_mergers_map[code].append(merger_summary)

    # Generate a file for each industry
    for code, industry_mergers in industry_mergers_map.items():
        # Sort by most recent date (determination or notification)
        industry_mergers.sort(key=lambda x: x.get('_latest_date', ''), reverse=True)

        # Remove internal sorting field before output
        for merger in industry_mergers:
            merger.pop('_latest_date', None)

        output_data = {
            "code": code,
            "mergers": industry_mergers,
            "count": len(industry_mergers)
        }

        # Use code as filename (sanitize for filesystem)
        safe_code = code.replace('/', '-').replace('\\', '-')
        output_path = industries_dir / f"{safe_code}.json"

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

    print(f"✓ Generated {len(industry_mergers_map)} individual industry files in {industries_dir}")


def generate_commentary_json(enriched_mergers: list, commentary: dict) -> dict:
    """Generate commentary.json with all mergers that have commentary (expects pre-enriched mergers)."""
    items = []

    for m in enriched_mergers:
        merger_id = m.get('merger_id', '')
        if merger_id in commentary:
            comm = commentary[merger_id]

            # Find determination event URL
            determination_url = None
            det_date = m.get('determination_publication_date')
            if det_date:
                for event in m.get('events', []):
                    if (event.get('date') == det_date and
                            'determination' in event.get('title', '').lower()):
                        determination_url = event.get('url_gh') or event.get('url')
                        break

            items.append({
                "merger_id": merger_id,
                "merger_name": m.get('merger_name'),
                "status": m.get('status'),
                "accc_determination": m.get('accc_determination'),
                "is_waiver": m.get('is_waiver', False),
                "effective_notification_datetime": m.get('effective_notification_datetime'),
                "determination_publication_date": m.get('determination_publication_date'),
                "determination_url": determination_url,
                "stage": m.get('stage'),
                "acquirers": m.get('acquirers', []),
                "targets": m.get('targets', []),
                "anzsic_codes": m.get('anzsic_codes', []),
                "comments": comm.get('comments', [])
            })

    # Sort by most recent comment date descending
    def get_latest_comment_date(item):
        dates = [c.get('date', '') for c in item.get('comments', []) if c.get('date')]
        return max(dates) if dates else ''

    items.sort(key=get_latest_comment_date, reverse=True)

    return {
        "items": items,
        "count": len(items)
    }


def generate_upcoming_events_json(enriched_mergers: list, days_ahead: int = 60) -> dict:
    """Generate upcoming events (expects pre-enriched mergers)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    future = now + timedelta(days=days_ahead)

    events = []

    for m in enriched_mergers:
        # Skip if already determined
        if m.get('determination_publication_date'):
            continue

        # Skip if assessment is suspended (no active determination period)
        if m.get('status') == 'Assessment suspended':
            continue

        # Skip waiver mergers (they don't have determination periods) - using pre-enriched field
        if m.get('is_waiver', False):
            continue
        
        merger_id = m['merger_id']
        merger_name = m['merger_name']
        status = m.get('status')
        stage = m.get('stage')
        notification_date = m.get('effective_notification_datetime')
        
        # Consultation response due
        consultation_due = m.get('consultation_response_due_date')
        if consultation_due:
            try:
                due_date = parse_iso_datetime(consultation_due)
                if due_date is None:
                    raise ValueError("unparseable date")
                due_date = due_date.replace(tzinfo=None)
                if now <= due_date <= future:
                    events.append({
                        "type": "consultation_due",
                        "event_type_display": "Consultation responses due",
                        "date": consultation_due,
                        "merger_id": merger_id,
                        "merger_name": merger_name,
                        "status": status,
                        "stage": stage,
                        "effective_notification_datetime": notification_date
                    })
            except (ValueError, AttributeError):
                pass

        # Phase 2 - Notice of competition concerns (issued by business day 25 of Phase 2)
        # Phase 2 BD 1 is derived by subtracting 89 BDs from end_of_determination_period
        # (BD 90 of Phase 2), not from the date the referral notice was issued (which may
        # have been issued before Phase 1's determination period fully expired).
        if stage and 'Phase 2' in stage:
            notice_already_issued = any(
                'competition concern' in event.get('title', '').lower()
                for event in m.get('events', [])
            )
            phase2_end = m.get('end_of_determination_period')
            if phase2_end and not notice_already_issued:
                try:
                    phase2_end_date = parse_iso_datetime(phase2_end)
                    if phase2_end_date is None:
                        raise ValueError("unparseable date")
                    phase2_end_date = phase2_end_date.replace(tzinfo=None)
                    phase2_start_date = subtract_business_days(phase2_end_date, 90)  # BD 1 of Phase 2
                    notice_date = add_business_days(phase2_start_date, 25)
                    notice_date_str = notice_date.strftime('%Y-%m-%dT12:00:00Z')
                    if now <= notice_date <= future:
                        events.append({
                            "type": "notice_of_competition_concerns",
                            "event_type_display": "Notice of competition concerns",
                            "date": notice_date_str,
                            "merger_id": merger_id,
                            "merger_name": merger_name,
                            "status": status,
                            "stage": stage,
                            "effective_notification_datetime": notification_date
                        })
                except (ValueError, AttributeError):
                    pass

        # Determination period end
        determination_due = m.get('end_of_determination_period')
        if determination_due:
            try:
                due_date = parse_iso_datetime(determination_due)
                if due_date is None:
                    raise ValueError("unparseable date")
                due_date = due_date.replace(tzinfo=None)
                if now <= due_date <= future:
                    events.append({
                        "type": "determination_due",
                        "event_type_display": "Determination due",
                        "date": determination_due,
                        "merger_id": merger_id,
                        "merger_name": merger_name,
                        "status": status,
                        "stage": stage,
                        "effective_notification_datetime": notification_date
                    })
            except (ValueError, AttributeError):
                pass
    
    # Sort by date
    events.sort(key=lambda x: x['date'])
    
    return {
        "events": events,
        "count": len(events),
        "days_ahead": days_ahead
    }


def generate_analysis_json(enriched_mergers: list) -> dict:
    """Generate pre-computed analysis data for the Analysis page."""
    from statistics import median as stat_median

    notification_mergers = [m for m in enriched_mergers if not m.get('is_waiver', False)]
    waiver_mergers = [m for m in enriched_mergers if m.get('is_waiver', False)]

    # --- Phase 1 duration analysis (notifications only) ---
    phase1_scatter = []
    phase1_business_days = []

    for m in notification_mergers:
        start = m.get('effective_notification_datetime')
        end = m.get('determination_publication_date')
        phase_1_det = m.get('phase_1_determination')

        if not start:
            continue

        # Include 'Referred to phase 2' mergers using the date the phase 2 notice was issued
        if not end:
            if phase_1_det == 'Referred to phase 2' and m.get('phase_1_determination_date'):
                end = m['phase_1_determination_date']
            else:
                continue

        bus_days = calculate_business_days(start, end)
        cal_days = calculate_calendar_days(start, end)
        if bus_days is None:
            continue

        in_progress = m.get('determination_publication_date') is None
        if not in_progress:
            phase1_business_days.append(bus_days)
        phase1_scatter.append({
            "notification_date": start[:10],
            "business_days": bus_days,
            "calendar_days": cal_days,
            "merger_name": m.get('merger_name'),
            "merger_id": m.get('merger_id'),
            "determination": phase_1_det,
            "in_progress": in_progress,
        })

    # Sort scatter data by date
    phase1_scatter.sort(key=lambda x: x['notification_date'])

    phase1_stats = {}
    if phase1_business_days:
        phase1_stats = {
            "average": round(sum(phase1_business_days) / len(phase1_business_days), 1),
            "median": stat_median(phase1_business_days),
            "min": min(phase1_business_days),
            "max": max(phase1_business_days),
            "count": len(phase1_business_days),
        }

    # --- Waiver duration analysis ---
    waiver_scatter = []
    waiver_business_days = []

    for m in waiver_mergers:
        start = m.get('effective_notification_datetime')
        end = m.get('determination_publication_date')
        if not start or not end:
            continue

        bus_days = calculate_business_days(start, end)
        cal_days = calculate_calendar_days(start, end)
        if bus_days is None:
            continue

        waiver_business_days.append(bus_days)
        waiver_scatter.append({
            "application_date": start[:10],
            "business_days": bus_days,
            "calendar_days": cal_days,
            "merger_name": m.get('merger_name'),
            "merger_id": m.get('merger_id'),
            "determination": m.get('accc_determination'),
        })

    waiver_scatter.sort(key=lambda x: x['application_date'])

    waiver_stats = {}
    if waiver_business_days:
        waiver_stats = {
            "average": round(sum(waiver_business_days) / len(waiver_business_days), 1),
            "median": stat_median(waiver_business_days),
            "min": min(waiver_business_days),
            "max": max(waiver_business_days),
            "count": len(waiver_business_days),
        }

    # --- Monthly notification volume ---
    monthly_counts = defaultdict(lambda: {"notifications": 0, "waivers": 0})
    for m in enriched_mergers:
        start = m.get('effective_notification_datetime')
        if not start:
            continue
        month_key = start[:7]  # YYYY-MM
        if m.get('is_waiver', False):
            monthly_counts[month_key]["waivers"] += 1
        else:
            monthly_counts[month_key]["notifications"] += 1

    sorted_months = sorted(monthly_counts.keys())
    monthly_volume = {
        "labels": sorted_months,
        "notifications": [monthly_counts[m]["notifications"] for m in sorted_months],
        "waivers": [monthly_counts[m]["waivers"] for m in sorted_months],
    }

    return {
        "phase1_duration": {
            "scatter_data": phase1_scatter,
            "stats": phase1_stats,
        },
        "waiver_duration": {
            "scatter_data": waiver_scatter,
            "stats": waiver_stats,
        },
        "monthly_volume": monthly_volume,
    }


def main():
    """Generate all static data files."""
    print("Loading mergers.json...")
    with open(MERGERS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Handle both formats: raw list or {mergers: [...]} wrapper
    if isinstance(data, list):
        mergers = data
    elif isinstance(data, dict) and 'mergers' in data:
        mergers = data['mergers']
    else:
        raise ValueError("Unexpected mergers.json format")

    print(f"Loaded {len(mergers)} mergers")

    # Load user commentary
    print("Loading commentary.json...")
    commentary = load_commentary()
    if commentary:
        print(f"Loaded commentary for {len(commentary)} merger(s)")
    else:
        print("No commentary found")

    # Enrich all mergers once (add computed fields, phase determinations, etc.)
    print("Enriching mergers...")
    enriched_mergers = [enrich_merger(m, commentary) for m in mergers]

    # Link related mergers (waiver <-> notification pairs) with resolved names
    merger_name_lookup = {m['merger_id']: m['merger_name'] for m in enriched_mergers if m.get('merger_id')}
    linked_count = 0
    for m in enriched_mergers:
        mid = m.get('merger_id', '')
        if mid in RELATED_MERGERS:
            related = RELATED_MERGERS[mid]
            m['related_merger'] = {
                'merger_id': related['merger_id'],
                'relationship': related['relationship'],
                'merger_name': merger_name_lookup.get(related['merger_id'], ''),
            }
            linked_count += 1
    if linked_count:
        print(f"  Linked {linked_count} related merger pairs")

    print(f"✓ Enriched {len(enriched_mergers)} mergers")

    # Create output directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Write full enriched mergers.json to data/output/ (for offline analysis, not deployed)
    mergers_json_path = DATA_OUTPUT_DIR / "mergers.json"
    with open(mergers_json_path, 'w', encoding='utf-8') as f:
        json.dump(generate_mergers_json(enriched_mergers), f, indent=2)
    print(f"✓ Generated {mergers_json_path}")

    # Generate each deployed file (all functions receive pre-enriched mergers)
    outputs = [
        ("stats.json", generate_stats_json(enriched_mergers)),
        ("industries.json", generate_industries_json(enriched_mergers)),
        ("upcoming-events.json", generate_upcoming_events_json(enriched_mergers)),
        ("commentary.json", generate_commentary_json(enriched_mergers, commentary)),
        ("analysis.json", generate_analysis_json(enriched_mergers)),
    ]

    for filename, data in outputs:
        output_path = OUTPUT_DIR / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"✓ Generated {output_path}")

    # Generate individual merger files
    print("\nGenerating individual merger files...")
    generate_individual_merger_files(enriched_mergers)
    print(f"✓ Generated {len(enriched_mergers)} individual merger files in {OUTPUT_DIR / 'mergers'}")

    # Generate paginated list files
    print("\nGenerating paginated list files...")
    generate_paginated_list(enriched_mergers, page_size=50)

    # Generate paginated timeline files
    print("\nGenerating paginated timeline files...")
    generate_paginated_timeline(enriched_mergers, page_size=100)

    # Generate individual industry files
    print("\nGenerating individual industry files...")
    generate_individual_industry_files(enriched_mergers)

    print("\nDone!")


if __name__ == "__main__":
    main()
