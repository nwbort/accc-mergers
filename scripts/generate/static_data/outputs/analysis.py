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

import calendar
import math
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import median as stat_median
from zoneinfo import ZoneInfo

from scripts.constants import merger_status
from scripts.constants.regime import is_voluntary_period_notification

from .. import anzsic
from ..business_days import calculate_business_days, calculate_calendar_days
from ..durations import collect_phase_1_durations, phase_1_end_date
from ..filters import filter_notifications, filter_waivers, is_waiver

_MAX_DIVISION_LABEL_LENGTH = 200

# The ACCC operates on Australian Eastern time, so "today" for the caseload's
# as-at cutoff must be Sydney's calendar date, not the build server's (the
# static data is generated on GitHub Actions runners, which run in UTC — using
# server-local date.today() would put the cutoff a day off from the ACCC's own
# during the several hours each day Sydney's date has already rolled over but
# UTC's hasn't, or vice versa).
_SYDNEY_TZ = ZoneInfo('Australia/Sydney')

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


def _caseload_span(merger: dict) -> tuple[str, str | None] | None:
    """The ``(opened, closed)`` dates bounding a matter's time before the ACCC.

    ``opened`` is the effective notification date, falling back to the original
    one so a matter whose clock was suspended (and whose effective date is
    therefore cleared) still counts as on the books from when it was first
    filed. ``closed`` is the published determination, or the cessation date for
    a matter abandoned before determination; ``None`` means it is still open.

    Note this deliberately measures the *whole* review, not just phase 1: a
    matter referred to phase 2 is still work in front of the ACCC, so it stays
    in the caseload until its final determination lands.
    """
    opened = merger.get('effective_notification_datetime') or merger.get('original_notification_datetime')
    if not opened:
        return None
    closed = merger.get('determination_publication_date') or merger.get('ceased_date')
    return opened[:10], (closed[:10] if closed else None)


def open_caseload(mergers: list, as_at: date | None = None) -> dict:
    """Live notifications before the ACCC at the end of each month.

    The monthly-volume chart counts *flow* — how many matters arrived in a
    month. This counts *stock*: how many were still open on the ACCC's books at
    each month end, i.e. filed on or before it and not yet determined. The two
    answer different questions, and only the stock shows whether determinations
    are keeping pace with filings.

    Waivers are deliberately excluded. The register only publishes a waiver
    application once it has been determined — every waiver it carries is
    "Assessment completed" — so pending waivers are invisible to us and a
    waiver stock line would collapse to zero at the present edge, reporting an
    artefact of what the ACCC publishes as though it were a real emptying of
    the queue.

    The final point is cut off at ``as_at`` rather than the end of the current
    month, so the series ends at a real observation instead of counting a
    month-end that hasn't happened yet. When not given explicitly, ``as_at``
    defaults to today's date in Sydney (the ACCC's own timezone), not the
    build server's local date.
    """
    as_at = as_at or datetime.now(_SYDNEY_TZ).date()

    spans = []
    for m in filter_notifications(mergers):
        span = _caseload_span(m)
        if span is not None:
            spans.append(span)

    if not spans:
        return {"labels": [], "notifications": [], "as_at": as_at.isoformat()}

    first = min(opened for opened, _ in spans)
    year, month = int(first[:4]), int(first[5:7])

    labels: list[str] = []
    notifications: list[int] = []

    while (year, month) <= (as_at.year, as_at.month):
        month_end = date(year, month, calendar.monthrange(year, month)[1])
        cutoff = min(month_end, as_at).isoformat()

        # Open at the cutoff: filed on or before it, and either still running or
        # closed strictly after it (a matter determined on the cutoff itself is
        # done, so it drops out that day rather than lingering to the month end).
        labels.append(f"{year:04d}-{month:02d}")
        notifications.append(sum(
            1 for opened, closed in spans
            if opened <= cutoff and (closed is None or closed > cutoff)
        ))

        year, month = (year + 1, 1) if month == 12 else (year, month + 1)

    return {
        "labels": labels,
        "notifications": notifications,
        "as_at": as_at.isoformat(),
    }


# Rolling windows (in calendar days back from the as-at date) used by
# state_of_play. 30 days answers the "how is the ACCC tracking right now"
# question directly; 90 smooths out a quiet fortnight without reaching so far
# back that it re-describes the all-time figure. Both are comfortably powered
# at current volumes (~45 phase 1 determinations and ~70 waivers a month).
TURNAROUND_WINDOWS = (30, 90)

# A month with fewer than this many decisions gets a null median in the monthly
# trend: with a handful of matters the "median" is one or two deals' durations,
# and plotting it invites reading a swing that isn't there. Five is set from the
# register's own opening months, where three-decision months produced a 30 BD
# spike off a single slow matter — a point an adviser could easily have quoted
# as a trend. The count is still published, so a consumer can show the gap
# honestly rather than silently dropping the month.
MIN_MONTHLY_TURNAROUND_SAMPLE = 5


def _percentile(sorted_values: list[int], fraction: float) -> int | None:
    """Nearest-rank percentile of an already-sorted, non-empty list.

    Nearest-rank (rather than an interpolating definition) is used so the
    result is always an observed duration: "9 in 10 matters were decided
    within N business days" has to name a real N to be quotable in advice.
    """
    if not sorted_values:
        return None
    rank = max(1, math.ceil(fraction * len(sorted_values)))
    return sorted_values[min(rank, len(sorted_values)) - 1]


def _turnaround_stats(business_days: list[int]) -> dict:
    """Median/average/spread of a set of decided-matter durations.

    ``p90`` is carried alongside the median because the median alone
    understates what an adviser has to promise a client: the tail is what
    turns a 13-day expectation into a 17-day one.
    """
    if not business_days:
        return {"median": None, "average": None, "p90": None, "min": None, "max": None, "count": 0}
    ordered = sorted(business_days)
    return {
        "median": stat_median(ordered),
        "average": round(sum(ordered) / len(ordered), 1),
        "p90": _percentile(ordered, 0.9),
        "min": ordered[0],
        "max": ordered[-1],
        "count": len(ordered),
    }


def _decided_durations(mergers: list) -> list[tuple[str, int]]:
    """``(decision_date, business_days)`` for every matter that has been decided.

    The decision date is what a matter is bucketed by here — not its filing
    date. That is the whole point of this series: to answer "what is the ACCC
    turning around *now*", a matter has to count towards the period it was
    decided in, not the period it was filed in. Bucketing by filing date would
    also make the recent months structurally incomplete, since the matters
    filed in them that are still open have no duration yet.

    Notifications are measured to the end of phase 1 (:func:`phase_1_end_date`
    — the referral date for a matter sent to phase 2, so the phase 2 clock
    never inflates the figure), waivers end-to-end to their determination,
    matching every other duration figure on the site.
    """
    durations = []
    for m in mergers:
        if is_waiver(m):
            end = m.get('determination_publication_date')
        else:
            end = phase_1_end_date(m)
        start = m.get('effective_notification_datetime')
        if not (start and end):
            continue
        bus_days = calculate_business_days(start, end)
        if bus_days is None:
            continue
        durations.append((end[:10], bus_days))
    return durations


def _pre_notification_durations(notification_mergers: list) -> list[tuple[str, int]]:
    """``(filed_date, estimated_days)`` for notifications with a usable estimate.

    Pre-notification — the stretch of ACCC engagement before a notification is
    formally filed — never appears on the register; the pipeline infers it from
    the order case numbers were issued in (see
    :mod:`static_data.prenotification`). The population mirrors the frontend's
    ``getPreNotificationEstimate``, so the aggregate here and the per-merger
    figure on a detail page are drawn from the same records: notifications
    only (a waiver has no drafting stage — the case is opened by lodging it),
    excluding voluntary-period matters, which predate the waiver applications
    that date the counter.

    A zero-day estimate is kept rather than dropped: it dates the case number
    to the filing day itself, which is a matter that really had no
    pre-notification stage, not a missing measurement.

    Durations are **calendar** days, unlike everything else on this page —
    pre-notification is not a statutory clock, so there is no business-day
    count to give.

    Matters are keyed by their filing date, the event that ends this stage,
    for the same reason :func:`_decided_durations` keys by decision date: it is
    the completion event, and the only matters we can measure are those that
    reached it. Ones still in pre-notification today have not been filed, so
    they are not on the register at all — the figure describes what completed,
    and cannot see a period still running.
    """
    durations = []
    for m in notification_mergers:
        estimate = m.get('pre_notification') or {}
        days = estimate.get('estimated_days')
        filed = m.get('original_notification_datetime') or m.get('effective_notification_datetime')
        if days is None or not filed or is_voluntary_period_notification(m):
            continue
        durations.append((filed[:10], days))
    return durations


def state_of_play(mergers: list, as_at: date | None = None) -> dict:
    """How the ACCC's review is running *now*, against its all-time baseline.

    Powers the /state-of-play page. The duration figures on the analysis page
    pool every matter ever decided. That is the right baseline, but it is not
    the number to quote a client at filing time: the register opened in 2026
    and the ACCC's throughput has moved as the regime bedded in, so the
    all-time median lags what a matter filed today should actually expect.
    This block re-cuts the same durations against that baseline:

    - ``windows`` — median/average/p90 over matters *decided* in the last 30
      and 90 days, each paired with the all-time figure and the delta between
      them, for notifications and waivers separately. Each window also carries
      ``notifications_filed``, the inflow over the same period, so the page can
      show what is arriving beside what is being cleared.
    - ``all_time`` — the same statistics over every decided matter, the
      baseline every window is compared against.
    - ``monthly`` — the same medians per decision-month, aligned index-for-index
      with the open notification caseload at each of those month ends, so the
      turnaround line can be read directly against the queue it came out of.

    Only notification inflow is published. Waiver applications reach the
    register only once they have been decided, so a "waivers filed in the last
    30 days" count would be missing every application still in front of the
    ACCC — understated by roughly the length of a waiver review, and worst at
    exactly the recent edge the page is about. (This is the same publication
    artefact that keeps waivers out of :func:`open_caseload`.)

    ``as_at`` defaults to today in Sydney (the ACCC's own timezone) rather than
    the build server's UTC date, for the same reason :func:`open_caseload`
    does. The final monthly point is a part-month reading, exactly as the
    caseload series' is.

    No correlation coefficient is published against the caseload deliberately:
    both series trend over the register's short life, so any r would mostly be
    measuring that shared trend rather than a caseload effect on turnaround.
    The paired axes let a reader judge it without a number that would carry
    more authority than ~a dozen monthly points can support.

    Nor is a baseline published for the inflow figure, though one is for
    turnaround. Notification volume stepped up when the regime became
    mandatory on 1 January 2026 rather than drifting, so an all-time average
    would mostly measure the pre-mandatory ramp-up and read as a throughput
    surge that is really a change in what has to be filed. Turnaround has no
    equivalent step, which is why the median there is a fair comparator.
    """
    as_at = as_at or datetime.now(_SYDNEY_TZ).date()

    notifications = filter_notifications(mergers)
    notification_durations = _decided_durations(notifications)
    waiver_durations = _decided_durations(filter_waivers(mergers))

    filing_dates = [
        m['effective_notification_datetime'][:10]
        for m in notifications
        if m.get('effective_notification_datetime')
    ]

    def _window(durations: list[tuple[str, int]], days: int) -> dict:
        cutoff = (as_at - timedelta(days=days)).isoformat()
        as_at_iso = as_at.isoformat()
        return _turnaround_stats(
            [bd for decided, bd in durations if cutoff < decided <= as_at_iso]
        )

    all_time = {
        "notifications": _turnaround_stats([bd for _, bd in notification_durations]),
        "waivers": _turnaround_stats([bd for _, bd in waiver_durations]),
    }

    windows = []
    for days in TURNAROUND_WINDOWS:
        cutoff = (as_at - timedelta(days=days)).isoformat()
        entry = {
            "days": days,
            "notifications_filed": sum(
                1 for filed in filing_dates if cutoff < filed <= as_at.isoformat()
            ),
        }
        for key, durations in (("notifications", notification_durations), ("waivers", waiver_durations)):
            stats = _window(durations, days)
            baseline = all_time[key]["median"]
            # The delta is the headline: "waivers are running 4 business days
            # longer than the all-time median" is the sentence this whole block
            # exists to support.
            stats["median_delta"] = (
                stats["median"] - baseline
                if stats["median"] is not None and baseline is not None
                else None
            )
            entry[key] = stats
        windows.append(entry)

    # Pre-notification is keyed by filing date, so it needs its own window cut
    # rather than riding on the decision-date windows above.
    pre_durations = _pre_notification_durations(notifications)
    pre_all_time = _turnaround_stats([days for _, days in pre_durations])
    pre_windows = []
    for days in TURNAROUND_WINDOWS:
        cutoff = (as_at - timedelta(days=days)).isoformat()
        stats = _turnaround_stats(
            [d for filed, d in pre_durations if cutoff < filed <= as_at.isoformat()]
        )
        stats["days"] = days
        stats["median_delta"] = (
            stats["median"] - pre_all_time["median"]
            if stats["median"] is not None and pre_all_time["median"] is not None
            else None
        )
        pre_windows.append(stats)

    caseload = open_caseload(mergers, as_at=as_at)

    def _monthly(durations: list[tuple[str, int]]) -> list[dict]:
        by_month = defaultdict(list)
        for decided, bus_days in durations:
            by_month[decided[:7]].append(bus_days)
        series = []
        for label in caseload["labels"]:
            values = by_month.get(label, [])
            if len(values) < MIN_MONTHLY_TURNAROUND_SAMPLE:
                series.append({"median": None, "average": None, "count": len(values)})
                continue
            series.append({
                "median": stat_median(values),
                "average": round(sum(values) / len(values), 1),
                "count": len(values),
            })
        return series

    return {
        "as_at": as_at.isoformat(),
        "windows": windows,
        "all_time": all_time,
        "pre_notification": {
            "windows": pre_windows,
            "all_time": pre_all_time,
        },
        "monthly": {
            "labels": caseload["labels"],
            "notifications": _monthly(notification_durations),
            "waivers": _monthly(waiver_durations),
            # Carried alongside rather than left to the caller to re-join:
            # the alignment is the point of the series, and open_caseload's
            # labels are what both are indexed by.
            "open_caseload": caseload["notifications"],
        },
    }


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


def generate(mergers: list) -> dict:
    """Return the analysis.json payload for pre-enriched mergers."""
    notification_mergers = filter_notifications(mergers)
    waiver_mergers = filter_waivers(mergers)

    # --- Phase 1 duration analysis (notifications only) ---
    # Overall figures are collected via the shared helper so they match
    # stats.json and the per-industry bars (industry_phase1_duration) exactly —
    # all three now cover the same population of completed Phase 1 reviews.
    #
    # A completed Phase 1 review is any notification whose Phase 1 has concluded
    # (see phase_1_end_date). Crucially that includes matters referred to Phase
    # 2: their Phase 1 was concluded *by* the referral, so they are counted even
    # while their Phase 2 review — and thus their final determination — is still
    # open. Gating on determination_publication_date (as this block used to)
    # wrongly dropped those referred-but-Phase-2-pending matters, leaving the
    # overall bar computed over a smaller population than every other Phase 1
    # duration figure on the site.
    phase1_calendar_days, phase1_business_days = collect_phase_1_durations(notification_mergers)

    phase1_durations = []
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

        phase1_durations.append({
            "business_days": bus_days,
            "calendar_days": cal_days,
            # Every retained entry is a completed Phase 1 review — matters still
            # in Phase 1 have no phase_1_end_date and are skipped above — so none
            # are in progress. Kept for the ECDF's expected schema.
            "in_progress": False,
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
        "open_caseload": open_caseload(mergers),
        "state_of_play": state_of_play(mergers),
        "industry_phase1_duration": industry_phase1_duration(mergers),
        "by_commission_division": by_commission_division(mergers),
        "deadline_utilisation": deadline_utilisation(mergers),
        "notification_restarts": restarts,
        "restart_rate": restart_rate,
        "outcomes_by_division": outcomes_by_division(notification_mergers),
        "referrals_by_quarter": referrals_by_quarter(notification_mergers),
    }
