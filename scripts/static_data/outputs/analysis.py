"""Pre-computed analysis data for the Analysis page — ``analysis.json``.

Label normalisation for ``by_commission_division`` (see that function):
- Whitespace runs are collapsed.
- A delegate sentence ("Determination/Decision made by <person> pursuant to
  a delegation...") is canonicalised to "<title> <surname>" (e.g.
  "Commissioner Philip Williams" and "Commissioner Williams" both collapse to
  "Commissioner Williams") so the same delegate isn't split across buckets
  depending on whether their first name happened to be spelled out.
- A "division of the Commission" sentence ("Determination/Decision made by a
  division of the Commission constituted by a direction issued pursuant to
  section <n>...") is canonicalised to "A division of the Commission (s<n>
  direction)", collapsing the "Determination"/"Decision" wording difference
  and the trailing Act-reference wording difference (a Phase 2 Notice cites
  "the Competition and Consumer Act 2010 (Cth)" in full; a determination just
  says "of the Act") — both describe the same kind of body.
- Grouping is case-insensitive (via ``str.casefold``), with the first-seen
  spelling for a group used as its display label.
- A merger with no parsed ``determination_commission_division`` on any
  event, or with a corrupted value, falls back to a Phase 2 Notice's own
  "Decision made by..." sentence (``phase2_notice_commission_division``)
  first: a matter whose assessment is ceased after referral to Phase 2 never
  gets a final determination PDF to parse, but its Phase 2 Notice still says
  who decided the referral.
- A label longer than ``_MAX_DIVISION_LABEL_LENGTH`` is treated as corrupted:
  real division sentences top out around 120 characters, but the
  extractor's "...of the Act" end-of-sentence marker can occasionally be
  missing nearby in a determination PDF (e.g. within a lengthy s87B
  undertaking), causing it to capture the rest of the document instead of
  just the division sentence.
- If still nothing is recoverable, the merger is split between two buckets
  rather than one blanket "Unknown" (see ``_PENDING_STATUSES`` and
  :func:`by_commission_division`): "Not yet determined" for matters still
  under assessment/suspended (there's simply no decision yet), and "Unknown"
  for matters that did reach or abandon an outcome but whose division
  genuinely couldn't be identified — a data gap worth investigating, unlike
  the former.
"""

import re
from collections import defaultdict
from statistics import median as stat_median

from constants import merger_status

from .. import anzsic
from ..business_days import calculate_business_days, calculate_calendar_days
from ..durations import collect_phase_1_durations, phase_1_end_date
from ..filters import filter_notifications, filter_waivers

_MAX_DIVISION_LABEL_LENGTH = 200

# Matches "Determination/Decision made by <person> pursuant to a delegation
# ..." so the delegate's name can be canonicalised to "<title> <surname>",
# collapsing variants that do/don't spell out a first name (e.g.
# "Commissioner Philip Williams" vs "Commissioner Williams").
_DELEGATE_PATTERN = re.compile(
    r'^(?:Determination|Decision) made by (?P<person>.+?) pursuant to a delegation\b',
    re.IGNORECASE,
)

# Matches "Determination/Decision made by a division of the Commission
# constituted by a direction issued pursuant to section <n> ..." so it can be
# canonicalised regardless of the "Determination"/"Decision" wording and the
# trailing Act-reference wording (see module docstring).
_DIVISION_PATTERN = re.compile(
    r'^(?:Determination|Decision) made by a division of the Commission '
    r'constituted by a direction issued pursuant to section (?P<section>\d+)\b',
    re.IGNORECASE,
)

# A Phase 1 window longer than this is an extension (e.g. public benefit
# applications) rather than the standard 30-business-day clock, so it's
# reported separately rather than folded into the "% of 30-day clock" stats.
STANDARD_WINDOW_MAX_BD = 31


def _division_for_code(code: str):
    """The top-level ANZSIC division (letter) node a tagged code rolls up to.

    ``code`` may already be a division, or a subdivision/group/class beneath
    one. Returns ``None`` for codes outside the known ANZSIC tree.
    """
    node = anzsic.get(code)
    if node is None:
        return None
    if node.level == 'division':
        return node
    ancestors = anzsic.ancestors(code)
    return ancestors[0] if ancestors else None


def industry_phase1_duration(mergers: list) -> list[dict]:
    """Phase 1 duration stats per top-level ANZSIC division, for comparison.

    Each merger is attributed to every division its tagged codes roll up to
    (deduped, so a merger tagged twice within a division isn't double-counted).
    Divisions with no completed Phase 1 reviews are omitted.
    """
    division_mergers = defaultdict(list)
    for m in mergers:
        codes = m.get('anzsic_codes') or []
        divisions = {}
        for code_obj in codes:
            division = _division_for_code(code_obj.get('code', ''))
            if division is not None:
                divisions[division.code] = division
        for division in divisions.values():
            division_mergers[division.code].append((division.name, m))

    results = []
    for division_code, entries in division_mergers.items():
        division_name = entries[0][0]
        cal_days, bus_days = collect_phase_1_durations([m for _, m in entries])
        if not bus_days:
            continue
        results.append({
            "code": division_code,
            "name": division_name,
            "average_business_days": round(sum(bus_days) / len(bus_days), 1),
            "median_business_days": stat_median(bus_days),
            "average_calendar_days": round(sum(cal_days) / len(cal_days), 1) if cal_days else None,
            "median_calendar_days": stat_median(cal_days) if cal_days else None,
            "count": len(bus_days),
        })

    results.sort(key=lambda x: -x['average_business_days'])
    return results


def _normalise_division(raw: str | None) -> str | None:
    """Collapse whitespace in a raw division sentence; ``None`` if unusable.

    Returns ``None`` (rather than "Unknown" directly) so callers can still
    distinguish "no value parsed" from "value parsed but corrupted" if
    needed; both fold into "Unknown" in :func:`by_commission_division`.
    """
    if not raw:
        return None
    label = re.sub(r'\s+', ' ', raw).strip()
    if not label or len(label) > _MAX_DIVISION_LABEL_LENGTH:
        return None

    match = _DELEGATE_PATTERN.match(label)
    if match:
        words = match.group('person').split()
        if len(words) >= 2:
            return f'{words[0]} {words[-1]}'
        return match.group('person')

    match = _DIVISION_PATTERN.match(label)
    if match:
        return f"A division of the Commission (s{match.group('section')} direction)"

    return label


def _commission_division_for(merger: dict) -> str | None:
    """The normalised commission-division label for ``merger``.

    Prefers ``determination_commission_division`` — parsed onto whichever
    event carries the determination PDF, at most one event per merger — over
    ``phase2_notice_commission_division``, used as a fallback only when no
    determination was ever reached (e.g. assessment ceased after a Phase 2
    referral), since the final determination's attribution should win when
    both exist.
    """
    events = merger.get('events') or []

    for event in events:
        raw = event.get('determination_commission_division')
        if raw is not None:
            return _normalise_division(raw)

    for event in events:
        raw = event.get('phase2_notice_commission_division')
        if raw is not None:
            return _normalise_division(raw)

    return None


# Statuses that mean a merger hasn't reached (and may never reach, if
# suspended pending information) a determination yet, as opposed to one that
# has but whose division couldn't be identified. See by_commission_division.
_PENDING_STATUSES = {merger_status.UNDER_ASSESSMENT, merger_status.ASSESSMENT_SUSPENDED}


def by_commission_division(mergers: list) -> list[dict]:
    """Determination counts, outcome mix, and Phase 1 duration per commission division.

    See the module docstring for the label normalisation rules. Divisions are
    sorted by determination count, descending. Mergers with no recoverable
    division are split into two buckets rather than one blanket "Unknown":
    "Not yet determined" for those still under assessment (or suspended) —
    there's simply no decision yet to attribute — and "Unknown" for those
    that reached (or abandoned) an outcome but whose division genuinely
    couldn't be identified (a data gap worth investigating, not an absence
    of data).
    """
    groups: dict[str, dict] = {}
    pending = []
    unknown = []
    for m in mergers:
        label = _commission_division_for(m)
        if label is None:
            if m.get('status') in _PENDING_STATUSES:
                pending.append(m)
            else:
                unknown.append(m)
            continue
        bucket = groups.setdefault(label.casefold(), {"label": label, "mergers": []})
        bucket["mergers"].append(m)

    buckets = list(groups.values())
    if pending:
        buckets.append({"label": "Not yet determined", "mergers": pending})
    if unknown:
        buckets.append({"label": "Unknown", "mergers": unknown})

    results = []
    for bucket in buckets:
        group = bucket["mergers"]
        outcome_mix = defaultdict(int)
        for m in group:
            outcome_mix[m.get('accc_determination') or 'Unknown'] += 1
        _, business_days = collect_phase_1_durations(group)
        results.append({
            "division": bucket["label"],
            "count": len(group),
            "outcome_mix": dict(outcome_mix),
            "median_phase_1_business_days": stat_median(business_days) if business_days else None,
        })

    results.sort(key=lambda x: -x['count'])
    return results


def deadline_utilisation(mergers: list) -> dict:
    """How much of the Phase 1 statutory clock the ACCC uses.

    For every completed (non-referred) Phase 1 notification, measures
    ``used_bd`` = business days from notification to the Phase 1 determination,
    and, where ``end_of_determination_period`` is known, ``slack_bd`` = business
    days remaining before the statutory deadline when the determination was
    made. Matters whose window exceeds :data:`STANDARD_WINDOW_MAX_BD` (an
    extension) are excluded from the histogram and stats and only counted via
    ``extended_count``, since folding them in would distort the "% of 30-day
    clock" framing.
    """
    used_days = []
    slack_days = []  # only for standard-window matters with a known deadline
    extended_count = 0

    for m in filter_notifications(mergers):
        det = m.get('phase_1_determination')
        det_date = m.get('phase_1_determination_date')
        start = m.get('effective_notification_datetime')
        if not det or det == merger_status.REFERRED_TO_PHASE_2 or not det_date:
            continue

        used_bd = calculate_business_days(start, det_date)
        if used_bd is None:
            continue

        deadline = m.get('end_of_determination_period')
        window_bd = calculate_business_days(start, deadline) if deadline else None

        if window_bd is not None and window_bd > STANDARD_WINDOW_MAX_BD:
            extended_count += 1
            continue

        used_days.append(used_bd)
        if window_bd is not None:
            slack_days.append(window_bd - used_bd)

    histogram = defaultdict(int)
    for bd in used_days:
        histogram[str(bd) if bd <= 30 else '30+'] += 1
    histogram_sorted = dict(sorted(
        histogram.items(),
        key=lambda kv: 31 if kv[0] == '30+' else int(kv[0]),
    ))

    # Last 5 BDs before the deadline, keyed by BDs of slack remaining (0 = the
    # determination landed on the deadline itself, up to 4 = five BDs early).
    last_5_bd = defaultdict(int)
    for slack in slack_days:
        if 0 <= slack <= 4:
            last_5_bd[str(slack)] += 1
    last_5_bd_sorted = dict(sorted(last_5_bd.items(), key=lambda kv: int(kv[0])))

    stats = {}
    if used_days:
        final_3_count = sum(1 for slack in slack_days if 0 <= slack <= 2)
        stats = {
            "mean_used_bd": round(sum(used_days) / len(used_days), 1),
            "median_used_bd": stat_median(used_days),
            "pct_decided_final_3_bd": (
                round(final_3_count / len(slack_days) * 100, 1) if slack_days else None
            ),
            "count": len(used_days),
        }

    return {
        "histogram": histogram_sorted,
        "last_5_bd_counts": last_5_bd_sorted,
        "stats": stats,
        "extended_count": extended_count,
    }


def notification_restarts(mergers: list) -> list[dict]:
    """Notifications whose clock restarted: original vs effective notification date.

    ``effective_notification_datetime`` moves forward when the ACCC treats a
    notification as amended/restarted; ``original_notification_datetime``
    stays fixed at first filing. Waivers have no such clock, so only
    notifications are considered. Sorted by delta (days) descending.
    """
    restarts = []
    for m in filter_notifications(mergers):
        original = m.get('original_notification_datetime')
        effective = m.get('effective_notification_datetime')
        if not original or not effective or original == effective:
            continue
        delta = calculate_calendar_days(original, effective)
        if delta is None:
            continue
        restarts.append({
            "merger_id": m.get('merger_id'),
            "merger_name": m.get('merger_name'),
            "original_date": original[:10],
            "effective_date": effective[:10],
            "delta_calendar_days": delta,
        })

    restarts.sort(key=lambda x: -x['delta_calendar_days'])
    return restarts


def outcomes_by_division(notification_mergers: list) -> list[dict]:
    """Phase 1 outcome mix per top-level ANZSIC division.

    Each merger is attributed to every division its tagged codes roll up to
    (deduped), exactly as :func:`industry_phase1_duration` does. Counts
    approved / not-approved / referred-to-Phase-2 / in-progress outcomes and
    the resulting Phase 2 referral rate (referred over completed+referred).
    """
    division_mergers = defaultdict(list)
    for m in notification_mergers:
        codes = m.get('anzsic_codes') or []
        divisions = {}
        for code_obj in codes:
            division = _division_for_code(code_obj.get('code', ''))
            if division is not None:
                divisions[division.code] = division
        for division in divisions.values():
            division_mergers[division.code].append((division.name, m))

    results = []
    for division_code, entries in division_mergers.items():
        division_name = entries[0][0]
        approved = not_approved = referred = in_progress = 0
        for _, m in entries:
            det = m.get('phase_1_determination')
            if det is None:
                in_progress += 1
            elif det == merger_status.REFERRED_TO_PHASE_2:
                referred += 1
            elif det == merger_status.APPROVED:
                approved += 1
            else:
                not_approved += 1

        completed_and_referred = approved + not_approved + referred
        phase2_referral_rate = (
            round(referred / completed_and_referred, 3) if completed_and_referred else None
        )

        results.append({
            "code": division_code,
            "name": division_name,
            "approved": approved,
            "not_approved": not_approved,
            "referred": referred,
            "in_progress": in_progress,
            "phase2_referral_rate": phase2_referral_rate,
        })

    results.sort(key=lambda x: (x['phase2_referral_rate'] is None, -(x['phase2_referral_rate'] or 0)))
    return results


def referrals_by_quarter(notification_mergers: list) -> list[dict]:
    """Notification volume and subsequent Phase 2 referrals, per calendar quarter.

    Quarter is derived from the notification date (``effective_notification_datetime``),
    not the (potentially much later) referral date.
    """
    quarter_counts = defaultdict(lambda: {"notifications": 0, "referred": 0})
    for m in notification_mergers:
        start = m.get('effective_notification_datetime')
        if not start:
            continue
        year = start[:4]
        month = int(start[5:7])
        quarter = (month - 1) // 3 + 1
        quarter_key = f"{year}-Q{quarter}"

        quarter_counts[quarter_key]["notifications"] += 1
        if m.get('phase_1_determination') == merger_status.REFERRED_TO_PHASE_2:
            quarter_counts[quarter_key]["referred"] += 1

    return [
        {
            "quarter": quarter_key,
            "notifications": counts["notifications"],
            "referred": counts["referred"],
        }
        for quarter_key, counts in sorted(quarter_counts.items())
    ]


# Business-day cut points for the "outcome by review length" analysis, keyed to
# the 30-business-day Phase 1 statutory clock: comfortably inside the clock, its
# back half, its final stretch, and beyond the standard window (an extended
# clock). ``max`` of ``None`` is the open-ended top bucket.
CLEARANCE_DURATION_BUCKETS = [
    {"label": "≤20 BD", "min": 0, "max": 20},
    {"label": "21–25 BD", "min": 21, "max": 25},
    {"label": "26–30 BD", "min": 26, "max": 30},
    {"label": ">30 BD", "min": 31, "max": None},
]


def clearance_by_duration(notification_mergers: list) -> dict:
    """Phase 1 clearance vs Phase 2 referral, grouped by how long the review ran.

    For every completed Phase 1 notification — one that reached a Phase 1
    outcome — measures the business days from notification to the Phase 1 end
    (:func:`phase_1_end_date`: the referral date for referred matters, the
    determination date for cleared ones) and drops it into a duration bucket.
    Within each bucket the split between matters cleared in Phase 1 and matters
    referred to Phase 2 gives the conditional referral rate by review length —
    the answer to "how likely is a Phase 1 to be cleared, given how long it is
    taking".

    Matters still in Phase 1 (no outcome yet) are excluded. So are the rare
    outcomes that are neither a clearance nor a referral (Phase 1 does not block
    a merger — a block only follows a Phase 2 referral), so ``cleared`` and
    ``referred`` are the only two categories and together make each bucket
    total. Referrals are measured to the referral date and so are never inflated
    by the Phase 2 clock.
    """
    buckets = [
        {"label": b["label"], "min": b["min"], "max": b["max"], "cleared": 0, "referred": 0}
        for b in CLEARANCE_DURATION_BUCKETS
    ]
    cleared_days = []
    referred_days = []

    for m in notification_mergers:
        det = m.get('phase_1_determination')
        start = m.get('effective_notification_datetime')
        end = phase_1_end_date(m)
        if not det or not start or not end:
            continue
        is_referred = det == merger_status.REFERRED_TO_PHASE_2
        if not is_referred and det not in merger_status.CLEARED_DETERMINATIONS:
            continue
        bus_days = calculate_business_days(start, end)
        if bus_days is None:
            continue

        for bucket in buckets:
            if bus_days >= bucket["min"] and (bucket["max"] is None or bus_days <= bucket["max"]):
                bucket["referred" if is_referred else "cleared"] += 1
                break
        (referred_days if is_referred else cleared_days).append(bus_days)

    bucket_rows = []
    for bucket in buckets:
        total = bucket["cleared"] + bucket["referred"]
        bucket_rows.append({
            "label": bucket["label"],
            "cleared": bucket["cleared"],
            "referred": bucket["referred"],
            "total": total,
            "referral_rate": round(bucket["referred"] / total, 3) if total else None,
        })

    total_completed = len(cleared_days) + len(referred_days)
    return {
        "buckets": bucket_rows,
        "cleared": {
            "count": len(cleared_days),
            "median_business_days": stat_median(cleared_days) if cleared_days else None,
        },
        "referred": {
            "count": len(referred_days),
            "median_business_days": stat_median(referred_days) if referred_days else None,
        },
        "total_completed": total_completed,
        "overall_referral_rate": (
            round(len(referred_days) / total_completed, 3) if total_completed else None
        ),
    }


def generate(mergers: list) -> dict:
    """Return the analysis.json payload for pre-enriched mergers."""
    notification_mergers = filter_notifications(mergers)
    waiver_mergers = filter_waivers(mergers)

    # --- Phase 1 duration analysis (notifications only) ---
    phase1_durations = []
    phase1_business_days = []
    phase1_calendar_days = []

    for m in notification_mergers:
        start = m.get('effective_notification_datetime')
        # Measure to the Phase 1 end. For matters referred to Phase 2 this is the
        # referral date — never the later Phase 2 determination — so referred
        # matters (whether still in Phase 2 or since concluded) don't inflate the
        # Phase 1 figures.
        end = phase_1_end_date(m)

        if not start or not end:
            continue

        bus_days = calculate_business_days(start, end)
        cal_days = calculate_calendar_days(start, end)
        if bus_days is None:
            continue

        in_progress = m.get('determination_publication_date') is None
        if not in_progress:
            phase1_business_days.append(bus_days)
            if cal_days is not None:
                phase1_calendar_days.append(cal_days)
        phase1_durations.append({
            "business_days": bus_days,
            "calendar_days": cal_days,
            "in_progress": in_progress,
        })

    phase1_stats = {}
    if phase1_business_days:
        phase1_stats = {
            "average": round(sum(phase1_business_days) / len(phase1_business_days), 1),
            "median": stat_median(phase1_business_days),
            "min": min(phase1_business_days),
            "max": max(phase1_business_days),
            "count": len(phase1_business_days),
        }

    phase1_calendar_stats = {}
    if phase1_calendar_days:
        phase1_calendar_stats = {
            "average": round(sum(phase1_calendar_days) / len(phase1_calendar_days), 1),
            "median": stat_median(phase1_calendar_days),
            "min": min(phase1_calendar_days),
            "max": max(phase1_calendar_days),
            "count": len(phase1_calendar_days),
        }

    # --- Waiver duration analysis ---
    waiver_durations = []
    waiver_business_days = []
    waiver_calendar_days = []

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
        if cal_days is not None:
            waiver_calendar_days.append(cal_days)
        waiver_durations.append({
            "business_days": bus_days,
            "calendar_days": cal_days,
        })

    waiver_stats = {}
    if waiver_business_days:
        waiver_stats = {
            "average": round(sum(waiver_business_days) / len(waiver_business_days), 1),
            "median": stat_median(waiver_business_days),
            "min": min(waiver_business_days),
            "max": max(waiver_business_days),
            "count": len(waiver_business_days),
        }

    waiver_calendar_stats = {}
    if waiver_calendar_days:
        waiver_calendar_stats = {
            "average": round(sum(waiver_calendar_days) / len(waiver_calendar_days), 1),
            "median": stat_median(waiver_calendar_days),
            "min": min(waiver_calendar_days),
            "max": max(waiver_calendar_days),
            "count": len(waiver_calendar_days),
        }

    # --- Monthly notification volume ---
    monthly_counts = defaultdict(lambda: {"notifications": 0, "waivers": 0})
    for m in mergers:
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

    restarts = notification_restarts(mergers)
    total_notifications = len(notification_mergers)
    restart_rate = round(len(restarts) / total_notifications, 4) if total_notifications else None

    return {
        "phase1_duration": {
            "durations": phase1_durations,
            "stats": phase1_stats,
            "calendar_stats": phase1_calendar_stats,
        },
        "waiver_duration": {
            "durations": waiver_durations,
            "stats": waiver_stats,
            "calendar_stats": waiver_calendar_stats,
        },
        "monthly_volume": monthly_volume,
        "industry_phase1_duration": industry_phase1_duration(mergers),
        "by_commission_division": by_commission_division(mergers),
        "deadline_utilisation": deadline_utilisation(mergers),
        "notification_restarts": restarts,
        "restart_rate": restart_rate,
        "outcomes_by_division": outcomes_by_division(notification_mergers),
        "referrals_by_quarter": referrals_by_quarter(notification_mergers),
        "clearance_by_duration": clearance_by_duration(notification_mergers),
    }
