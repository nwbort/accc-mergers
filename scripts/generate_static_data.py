#!/usr/bin/env python3
"""
Generate static JSON data files for Cloudflare Pages deployment.

This script reads mergers.json and generates pre-computed JSON files
that the frontend can consume directly without a backend API.

Output files (to merger-tracker/frontend/public/data/):
- mergers.json      - All mergers wrapped in {mergers: [...]} (legacy, full data)
- mergers/list.json - Lightweight merger list (no events/descriptions)
- mergers/{id}.json - Individual merger files (one per merger)
- stats.json        - Aggregated statistics
- timeline.json     - All events sorted by date
- industries.json   - ANZSIC codes with merger counts
- upcoming-events.json - Future consultation/determination dates
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

from normalization import normalize_determination

# Paths
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
MERGERS_JSON = REPO_ROOT / "data" / "processed" / "mergers.json"
COMMENTARY_JSON = REPO_ROOT / "data" / "processed" / "commentary.json"
HOLIDAYS_JSON = REPO_ROOT / "merger-tracker" / "frontend" / "src" / "data" / "act-public-holidays.json"
OUTPUT_DIR = REPO_ROOT / "merger-tracker" / "frontend" / "public" / "data"


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


def calculate_business_days(start_date_str: str, end_date_str: str) -> int | None:
    """Calculate business days between two ISO date strings (inclusive of start)."""
    if not start_date_str or not end_date_str:
        return None
    
    try:
        start = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        start = start.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        end = end.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        
        business_days = 0
        current = start
        
        while current <= end:
            if is_business_day(current):
                business_days += 1
            current += timedelta(days=1)
        
        return business_days
    except (ValueError, AttributeError):
        return None


def calculate_calendar_days(start_date_str: str, end_date_str: str) -> int | None:
    """Calculate calendar days between two ISO date strings."""
    if not start_date_str or not end_date_str:
        return None
    
    try:
        start = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
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


def is_waiver_merger(merger: dict) -> bool:
    """Check if a merger is a waiver application (not a full notification)."""
    merger_id = merger.get('merger_id', '')
    stage = merger.get('stage', '')

    return merger_id.startswith('WA-') or 'Waiver' in stage


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
        m['commentary'] = commentary[merger_id]
    
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
    
    # Ensure anzsic_codes exists
    if 'anzsic_codes' not in m:
        m['anzsic_codes'] = []
    
    # Add phase to events
    if 'events' in m:
        for event in m['events']:
            if 'phase' not in event:
                event['phase'] = extract_phase_from_event(event.get('title', ''))
    
    return m


def generate_mergers_json(mergers: list, commentary: dict = None) -> dict:
    """Generate mergers.json with wrapper format and enriched fields."""
    enriched = [enrich_merger(m, commentary) for m in mergers]
    return {"mergers": enriched}


def generate_individual_merger_files(mergers: list, commentary: dict = None) -> None:
    """Generate individual JSON files for each merger."""
    mergers_dir = OUTPUT_DIR / "mergers"
    mergers_dir.mkdir(parents=True, exist_ok=True)

    for merger in mergers:
        enriched = enrich_merger(merger, commentary)
        merger_id = enriched.get('merger_id', '')

        if merger_id:
            output_path = mergers_dir / f"{merger_id}.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(enriched, f, indent=2)


def generate_mergers_list_json(mergers: list) -> dict:
    """Generate lightweight list of mergers with only essential fields for listing pages."""
    lightweight_mergers = []

    for m in mergers:
        # Only include fields needed for list view (no events, no large descriptions)
        lightweight_mergers.append({
            "merger_id": m.get('merger_id'),
            "merger_name": m.get('merger_name'),
            "status": m.get('status'),
            "accc_determination": normalize_determination(m.get('accc_determination')),
            "is_waiver": is_waiver_merger(m),
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

    return {"mergers": lightweight_mergers}


def generate_stats_json(mergers: list) -> dict:
    """Generate aggregated statistics (excluding waiver mergers)."""
    # Filter out waiver mergers for stats
    notification_mergers = [m for m in mergers if not is_waiver_merger(m)]
    waiver_mergers = [m for m in mergers if is_waiver_merger(m)]
    
    total_notifications = len(notification_mergers)
    total_waivers = len(waiver_mergers)
    
    # By status (notifications only)
    by_status = defaultdict(int)
    for m in notification_mergers:
        status = m.get('status', 'Unknown')
        by_status[status] += 1
    
    # By determination (notifications only, normalized)
    by_determination = defaultdict(int)
    for m in notification_mergers:
        det = normalize_determination(m.get('accc_determination'))
        if det:
            by_determination[det] += 1
    
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
    
    # Top industries (including waivers)
    industry_counts = defaultdict(int)
    for m in mergers:
        codes = m.get('anzsic_codes') or m.get('anszic_codes') or []
        for code in codes:
            industry_counts[code.get('name', 'Unknown')] += 1
    
    top_industries = [
        {"name": name, "count": count}
        for name, count in sorted(industry_counts.items(), key=lambda x: -x[1])[:10]
    ]
    
    # Recent mergers (include all but mark waivers)
    sorted_mergers = sorted(
        mergers,
        key=lambda x: x.get('effective_notification_datetime', ''),
        reverse=True
    )
    recent_mergers = [
        {
            "merger_id": m['merger_id'],
            "merger_name": m['merger_name'],
            "status": m.get('status'),
            "accc_determination": normalize_determination(m.get('accc_determination')),
            "effective_notification_datetime": m.get('effective_notification_datetime'),
            "is_waiver": is_waiver_merger(m)
        }
        for m in sorted_mergers[:5]
    ]
    
    return {
        "total_mergers": total_notifications,
        "total_waivers": total_waivers,
        "by_status": dict(by_status),
        "by_determination": dict(by_determination),
        "phase_duration": {
            "average_days": avg_duration,
            "median_days": median_duration,
            "all_durations": durations,
            "average_business_days": avg_business,
            "median_business_days": median_business,
            "all_business_durations": business_durations
        },
        "top_industries": top_industries,
        "recent_mergers": recent_mergers
    }


def generate_timeline_json(mergers: list) -> dict:
    """Generate timeline of all events."""
    events = []
    
    for m in mergers:
        merger_id = m['merger_id']
        merger_name = m['merger_name']
        merger_is_waiver = is_waiver_merger(m)
        
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
    
    # Sort by date descending
    events.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    return {
        "events": events,
        "total": len(events)
    }


def generate_industries_json(mergers: list) -> dict:
    """Generate industry list with merger counts."""
    # Group by (code, name) to count unique mergers
    industry_mergers = defaultdict(set)
    
    for m in mergers:
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


def generate_upcoming_events_json(mergers: list, days_ahead: int = 60) -> dict:
    """Generate upcoming events (consultation due, determination due)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    future = now + timedelta(days=days_ahead)
    
    events = []
    
    for m in mergers:
        # Skip if already determined
        if m.get('determination_publication_date'):
            continue
        
        # Skip waiver mergers (they don't have determination periods)
        if is_waiver_merger(m):
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
                due_date = datetime.fromisoformat(consultation_due.replace('Z', '+00:00')).replace(tzinfo=None)
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
        
        # Determination period end
        determination_due = m.get('end_of_determination_period')
        if determination_due:
            try:
                due_date = datetime.fromisoformat(determination_due.replace('Z', '+00:00')).replace(tzinfo=None)
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

    # Count waivers vs notifications
    waiver_count = sum(1 for m in mergers if is_waiver_merger(m))
    notification_count = len(mergers) - waiver_count
    print(f"Loaded {len(mergers)} mergers ({notification_count} notifications, {waiver_count} waivers)")

    # Load user commentary
    print("Loading commentary.json...")
    commentary = load_commentary()
    if commentary:
        print(f"Loaded commentary for {len(commentary)} merger(s)")
    else:
        print("No commentary found")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate each file
    outputs = [
        ("mergers.json", generate_mergers_json(mergers, commentary)),
        ("stats.json", generate_stats_json(mergers)),
        ("timeline.json", generate_timeline_json(mergers)),
        ("industries.json", generate_industries_json(mergers)),
        ("upcoming-events.json", generate_upcoming_events_json(mergers)),
    ]

    for filename, data in outputs:
        output_path = OUTPUT_DIR / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"✓ Generated {output_path}")

    # Generate individual merger files
    print("\nGenerating individual merger files...")
    generate_individual_merger_files(mergers, commentary)
    print(f"✓ Generated {len(mergers)} individual merger files in {OUTPUT_DIR / 'mergers'}")

    # Generate lightweight list.json
    list_data = generate_mergers_list_json(mergers)
    list_path = OUTPUT_DIR / "mergers" / "list.json"
    with open(list_path, 'w', encoding='utf-8') as f:
        json.dump(list_data, f, indent=2)
    print(f"✓ Generated {list_path}")

    print("\nDone!")


if __name__ == "__main__":
    main()
