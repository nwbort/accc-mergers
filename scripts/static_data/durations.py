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

from .business_days import calculate_business_days, calculate_calendar_days
from .filters import filter_notifications


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
