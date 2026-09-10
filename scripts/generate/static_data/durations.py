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

from scripts.constants import merger_status

from .business_days import calculate_business_days, calculate_calendar_days
from .filters import filter_notifications, filter_waivers

# Ceiling for referral_probability_by_day: the estimate never claims certainty,
# so the tail (where the raw share hits 1.0 off a few long referred matters)
# is clamped to 0.99.
_MAX_REFERRAL_PROBABILITY = 0.99


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
    in a referral. Day 0 is the at-notification baseline (the overall referral
    rate); the curve then trends up as the quick clearances drop out of the pool.

    Returns ``{"probabilities": [...]}`` — one probability per business day,
    positional so the business day *is* the list index (index 0 = day 0, the
    baseline), running from day 0 up to the longest completed review::

        {"probabilities": [0.05, 0.05, 0.05, ...]}

    Storing it positionally (rather than as ``{business_day, probability}``
    objects) drops the repeated keys and makes the future per-merger lookup a
    plain ``probabilities[elapsed_business_days]``.

    Each probability is the raw share passed through a running maximum, so the
    series is **weakly monotonic** (non-decreasing): the thinning sample can
    make the raw share dip when a late clearance is still in the pool after a
    referral has dropped out, but a live merger's referral risk should only
    ratchet up the longer it sits undecided. Values are capped at
    :data:`_MAX_REFERRAL_PROBABILITY` (0.99) so the tail — where a handful of
    long referred matters push the raw share to 1.0 — never reads as certainty.

    Probabilities are rounded to 2 decimal places: the only consumer renders
    them as a whole-number percentage, so finer precision would just bloat the
    published file. Rounding after the running maximum keeps the series weakly
    monotonic.

    The result is published to ``referral-probability-by-day.json`` and read by
    the frontend's per-merger "predicted Phase 2 risk" reveal, which indexes
    this curve by an open matter's elapsed business days
    (``probabilities[elapsed_business_days]``).

    Measured over completed reviews only, since a still-open matter has no known
    outcome yet. Accepts the full merger list (waivers and in-progress matters
    are filtered out) or an already-filtered notification list.

    Why elapsed day is the only predictor
    -------------------------------------
    The curve is deliberately univariate. Two filing-time covariates were tested
    as additions and neither earned a place, though for opposite reasons.

    **Questionnaire size is a real signal, but the clock already carries it.**
    Split at the ACCC's boilerplate three questions, matters whose questionnaire
    asks more are referred 10.4% of the time (7 of 67) against 1.3% (2 of 155)
    below it — an 8x relative risk, Fisher two-sided p = 0.004, AUC 0.764
    (permutation p = 0.0009), and not the artefact of any one matter: refitting
    with each of the nine referrals dropped in turn leaves p at 0.0098 or
    better. The cut at 3 is also the best available — >4 scores the same and
    every coarser cut is weaker — and it is the same boundary
    :mod:`static_data.phase1_estimate` pools on, from the same cause: the
    questionnaire reveals the ACCC's opening read on complexity.

    That signal is almost entirely *front-loaded*, because question count
    correlates with phase-1 duration (Spearman rho = +0.44) and this curve
    conditions on duration already. Among matters still undecided at business
    day 20 the questionnaire AUC has fallen to 0.626 (p = 0.21), and by day 25
    the stratified curves have converged on the pooled one (0.20 and 0.27
    against 0.25, identical from day 30). All of its unique information sits in
    the window where this curve is flat: through day 15 the pooled curve reads
    0.04 for every matter, where stratifying reads 0.01 below the cut and 0.10
    above.

    Whether that is worth publishing is a genuinely close call, and it was
    resolved — for now — against changing the curve. Leave-one-merger-out CV
    over the risk-set expansion (each merger contributing one row per business
    day it ran undecided, which is the estimand this curve publishes) scores the
    pooled curve at log loss 0.2454 / Brier 0.0670. Stratifying it on the same
    cut for the whole of its length lowers log loss to 0.2430 but raises Brier
    to 0.0695 — the late-day strata, built on a handful of matters each, are
    what cost it. Confining the stratification to the early window fixes that:
    stratify below a cut-off day and pool at and after it, and both metrics
    improve at every cut-off from day 10 to day 30, best around day 20 at
    0.2340 / 0.0663.

    That is a consistent 4.6% relative improvement in log loss, in the right
    direction on every variant tested — and still not significant. Bootstrapped
    over mergers, the day-20 gain is +0.0114 log loss (95% CI [-0.014, +0.035])
    and +0.00063 Brier (95% CI [-0.0015, +0.0031]); both intervals comfortably
    contain zero, as does every other cut-off's. On nine referrals the
    stratification cannot be shown to beat the pooled curve, so the extra
    parameter is not yet paid for — but unlike ANZSIC in
    :mod:`static_data.phase1_estimate`, this is a promising result short of
    proof rather than a rejected one, and it should be retested as referrals
    accumulate.

    **Pre-notification duration predicts nothing.** The
    :mod:`static_data.prenotification` estimate scores AUC 0.548 (p = 0.63)
    against referral, its proven floor ``min_days`` 0.542 (p = 0.67), and it
    stays flat inside both questionnaire strata (0.363 and 0.513). Added to any
    model above, it made held-out loss worse. Its ceiling ``max_days`` does test
    significant (AUC 0.819, p = 0.024) — but only over the 191 matters that have
    one, and the 33 without include five of the nine referrals, so that slice is
    selected by where a matter sits on its ID counter rather than by anything
    about the matter. Treat it as an artefact, not a finding.

    **What would change the answer.** Power, not method: 9 referrals in 224
    completed reviews. Recent cohorts also read artificially clean, because
    referrals take much longer to surface than clearances (median 46 business
    days against 17), so a cohort's referrals are the last of it to complete —
    the two longest-running matters open today, at 58 and 51 business days, both
    sit above the questionnaire cut. Re-run this comparison once the register
    carries roughly twice the referrals and the early-window stratification may
    well clear the bar.
    """
    referred_days, cleared_days = _completed_phase1_outcomes(mergers)
    all_days = referred_days + cleared_days

    # Every day from 0 to the longest review has at least that review still
    # open, so still_open is never 0 in range and the index stays == the day.
    probabilities = []
    running_max = 0.0
    for day in range(0, (max(all_days) if all_days else -1) + 1):
        still_open = sum(1 for d in all_days if d >= day)
        referred = sum(1 for d in referred_days if d >= day)
        running_max = max(running_max, referred / still_open)
        probabilities.append(min(round(running_max, 2), _MAX_REFERRAL_PROBABILITY))

    return {"probabilities": probabilities}
