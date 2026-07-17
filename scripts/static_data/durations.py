"""Phase 1 review duration helpers shared across the static-data outputs.

Phase 1 duration measures the time from notification to the *Phase 1* outcome.
The subtlety is mergers that get referred to Phase 2: their published
``determination_publication_date`` is the eventual Phase 2 determination, weeks
or months later. Measuring to that date would fold the Phase 2 clock into the
Phase 1 figure and badly inflate it (e.g. an industry average jumping to ~84
business days off a single referred matter).

Enrichment already records when Phase 1 actually concluded in
``phase_1_determination_date`` — the referral date for referred matters, the
determination date for matters resolved within Phase 1 — so every duration
output measures to that field via :func:`phase_1_end_date`.
"""

from statistics import median

from constants import merger_status

from .business_days import calculate_business_days, calculate_calendar_days
from .filters import filter_notifications, filter_waivers


def median_or_none(values: list):
    """True median of ``values`` (``statistics.median``), or ``None`` if empty.

    Every duration output must use this rather than ``sorted(v)[len(v) // 2]``:
    the upper-middle shortcut is biased high for even-length samples, and the
    per-subject figures (industry/party/refiled) are charted directly against
    the stats.json baselines, so the two conventions must not mix. See the
    stats-vs-analysis regression test in test_static_data_outputs.py.
    """
    return median(values) if values else None


def phase_1_end_date(m: dict) -> str | None:
    """ISO date Phase 1 concluded for ``m``, or ``None`` if it hasn't.

    For matters referred to Phase 2 this is the referral date (so the Phase 2
    clock never inflates Phase 1 durations); for matters resolved within Phase
    1 it is the determination publication date. Returns ``None`` while Phase 1
    is still open.
    """
    return m.get('phase_1_determination_date')


def collect_phase_1_durations(mergers: list) -> tuple[list, list]:
    """Return ``(calendar_days, business_days)`` for completed Phase 1 reviews.

    Only notification (non-waiver) mergers whose Phase 1 has concluded are
    counted, measuring notification → Phase 1 end (see :func:`phase_1_end_date`).
    """
    calendar_days = []
    business_days = []

    for m in filter_notifications(mergers):
        start = m.get('effective_notification_datetime')
        end = phase_1_end_date(m)
        if not (start and end):
            continue
        cal_days = calculate_calendar_days(start, end)
        if cal_days is not None:
            calendar_days.append(cal_days)
        bus_days = calculate_business_days(start, end)
        if bus_days is not None:
            business_days.append(bus_days)

    return calendar_days, business_days


def collect_waiver_durations(mergers: list) -> tuple[list, list]:
    """Return ``(calendar_days, business_days)`` for completed waiver reviews.

    Only waiver mergers with a published determination are counted, measuring
    notification → determination publication. Waivers have no Phase 1 clock, so
    they are measured end-to-end rather than to :func:`phase_1_end_date`.
    """
    calendar_days = []
    business_days = []

    for m in filter_waivers(mergers):
        start = m.get('effective_notification_datetime')
        end = m.get('determination_publication_date')
        if not (start and end):
            continue
        cal_days = calculate_calendar_days(start, end)
        if cal_days is not None:
            calendar_days.append(cal_days)
        bus_days = calculate_business_days(start, end)
        if bus_days is not None:
            business_days.append(bus_days)

    return calendar_days, business_days


def _completed_phase1_outcomes(mergers: list) -> tuple[list[int], list[int]]:
    """``(referred_business_days, cleared_business_days)`` for completed reviews.

    A completed Phase 1 review is a notification that reached a Phase 1 outcome.
    Each is measured (in business days) from notification to the Phase 1 end
    (:func:`phase_1_end_date`: the referral date for referred matters, the
    determination date for cleared ones — so the Phase 2 clock never inflates a
    referred matter's duration) and sorted into the referred or cleared list.
    Matters still in Phase 1 (no outcome yet) are skipped, as are the rare
    outcomes that are neither a clearance nor a referral (Phase 1 does not block
    a merger — a block only follows a Phase 2 referral). Waivers are excluded.
    """
    referred_days: list[int] = []
    cleared_days: list[int] = []
    for m in filter_notifications(mergers):
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
        (referred_days if is_referred else cleared_days).append(bus_days)
    return referred_days, cleared_days


def referral_probability_by_day(mergers: list) -> dict:
    """P(referred to Phase 2 | still undecided at business day N), for each N.

    A "survival"-style read of Phase 1 outcomes answering: as a review's clock
    runs on without a decision, how likely is it to end in a Phase 2 referral
    rather than a Phase 1 clearance? For each business day N, among the
    completed reviews still undecided going into day N — those whose Phase 1 ran
    at least N business days — the raw referral share is the fraction that ended
    in a referral. It starts at the overall referral rate on day 1 and trends up
    as the quick clearances drop out of the pool.

    The exposed ``referral_probability`` is that raw share passed through a
    running maximum, so it is **weakly monotonic** (non-decreasing) in the day:
    the thinning sample can make the raw share dip when a late clearance is still
    in the pool after a referral has dropped out, but a live merger's referral
    risk should only ratchet up the longer it sits undecided. The raw pool
    counts (``still_open``, ``referred``) travel with each point so the estimate
    stays auditable and its thinning sample is visible.

    Nothing here is written to the published data files — it is kept as a
    building block for a future per-merger "predicted Phase 2 risk" feature,
    which would index this curve by an open matter's elapsed business days.

    Measured over completed reviews only, since a still-open matter has no known
    outcome yet. Accepts the full merger list (waivers and in-progress matters
    are filtered out) or an already-filtered notification list.
    """
    referred_days, cleared_days = _completed_phase1_outcomes(mergers)
    all_days = referred_days + cleared_days

    points = []
    running_max = 0.0
    for day in range(1, (max(all_days) if all_days else 0) + 1):
        still_open = sum(1 for d in all_days if d >= day)
        if still_open == 0:
            continue
        referred = sum(1 for d in referred_days if d >= day)
        running_max = max(running_max, referred / still_open)
        points.append({
            "business_day": day,
            "still_open": still_open,
            "referred": referred,
            "referral_probability": round(running_max, 3),
        })

    return {
        "points": points,
        "total_completed": len(all_days),
        "total_referred": len(referred_days),
    }
