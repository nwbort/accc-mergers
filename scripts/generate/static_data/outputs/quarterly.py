"""Quarter-by-quarter report on the merger regime — ``quarterly.json``.

Powers the /quarterly page: one block per calendar quarter since the mandatory
regime began (Q1 2026), so a quarter can be read on its own and against the
one before it. Each block answers the questions a quarterly round-up asks:

- **Volume.** Notifications filed in the quarter, phase 1 reviews concluded in
  it, and waivers decided in it.
- **Outcomes.** How those decisions came out: the clearance rate, waivers
  refused (and how many of those were re-filed as notifications), phase 1
  reviews referred to phase 2.
- **Timing.** Median/average/p90 business days for the quarter's decisions,
  the average split by outcome (a refusal or referral runs longer than a
  clearance), and a bucketed histogram the page draws against the previous
  quarter's.
- **Who and what.** The ANZSIC divisions the quarter's matters sat in, and the
  share of them with an overseas-registered party.
- **Beyond phase 1.** Every phase 2 referral, phase 2 outcome, public benefit
  application, Tribunal application and Federal Court review in the quarter,
  as a dated list of matters.
- **In brief.** ``findings``, a few sentences saying what moved against the
  previous quarter. Written here rather than in the page so the page and the
  PDF report (``generate/quarterly_pdf.py``) say the same thing.

Bucketing follows :func:`analysis.current_status`: a decision counts towards
the quarter it was *made* in, not the quarter the matter was filed in, so a
quarter's timing figures describe what the ACCC turned around in that quarter.
Notification inflow is keyed by filing date. No waiver inflow is published:
a waiver reaches the register only once it has been decided, so "waivers
filed this quarter" would undercount every application still in front of the
ACCC (see ``analysis.current_status`` for the same reasoning). For waivers,
decisions are the only honest count, and the page labels them so.

The current quarter is included and flagged ``complete: false``, so the page
can show it as a quarter to date rather than as a quiet quarter.
"""

import re
from collections import Counter
from datetime import date, datetime
from statistics import median as stat_median
from zoneinfo import ZoneInfo

from scripts.constants import merger_status

from ..business_days import calculate_business_days
from ..durations import phase_1_end_date
from ..enrichment import phase_2_outcome
from ..filters import filter_notifications, filter_waivers
from ..loaders import FORWARD_REFILE_RELATIONSHIPS
from .analysis import _division_for_code, _percentile

_SYDNEY = ZoneInfo("Australia/Sydney")

#: The first quarter of the mandatory regime. Earlier quarters held only a
#: handful of voluntary-period notifications and no waivers at all, so a report
#: for them would compare nothing with nothing.
FIRST_QUARTER = (2026, 1)

#: Upper bounds (inclusive, business days) of the timing histogram's buckets;
#: the last bucket is open-ended. Five-day steps up to the phase 1 clock's 30,
#: then wider ones for the extended reviews and waivers that run long.
DURATION_BUCKETS = [4, 9, 14, 19, 24, 29, 49]

#: How many ANZSIC divisions each quarter lists.
TOP_INDUSTRIES = 5

# A party name that says it is Australian, whatever its identifier field holds:
# trustee companies and the like often carry their ACN in the name instead.
_AUSTRALIAN_NAME = re.compile(r"\b(pty|acn|abn|arsn|arbn)\b", re.IGNORECASE)

# Legal forms that only an overseas entity carries. Deliberately excludes the
# forms Australia shares with other jurisdictions ("Limited", "Ltd", "Trust"),
# so the share this feeds is a lower bound, not an estimate.
_OVERSEAS_LEGAL_FORM = re.compile(
    r"\b(inc|llc|l\.?l\.?c|llp|l\.?p|lp|gmbh|s\.?a\.?s|s\.?p\.?a|s\.?r\.?l|s\.?à\.? ?r\.?l|"
    r"sarl|b\.?v|n\.?v|ag|plc|ulc|oyj?|ab|se|k\.?k|corp|corporation|s\.?a|ltda|bhd|pte|"
    r"anonim şirketi)\.?(?=$|[\s,)])",
    re.IGNORECASE,
)


def _quarter_of(iso: str | None) -> tuple[int, int] | None:
    """``(year, quarter)`` an ISO date or datetime string falls in."""
    if not iso:
        return None
    try:
        year, month = int(iso[:4]), int(iso[5:7])
    except ValueError:
        return None
    return year, (month - 1) // 3 + 1


def _quarter_key(quarter: tuple[int, int]) -> str:
    return f"{quarter[0]}-Q{quarter[1]}"


def _quarter_bounds(quarter: tuple[int, int]) -> tuple[date, date]:
    year, q = quarter
    start = date(year, 3 * q - 2, 1)
    end = date(year + 1, 1, 1) if q == 4 else date(year, 3 * q + 1, 1)
    return start, date.fromordinal(end.toordinal() - 1)


def _quarters_between(first: tuple[int, int], last: tuple[int, int]) -> list[tuple[int, int]]:
    quarters = []
    year, q = first
    while (year, q) <= last:
        quarters.append((year, q))
        year, q = (year + 1, 1) if q == 4 else (year, q + 1)
    return quarters


def is_overseas_party(party: dict) -> bool:
    """True when a party's register entry marks it as registered outside Australia.

    The register records an ABN or ACN for an Australian entity. An overseas
    one has neither: it carries its home registry's number instead (a VAT
    number, an EIN, a Delaware file number) or nothing at all. So a party with
    no ABN/ACN counts as overseas when it gives some other registration number,
    or, giving none, when its name carries a legal form only an overseas
    entity has (Inc, GmbH, S.p.A., ...). A name that itself cites an ACN or
    says "Pty" is Australian whatever the identifier field holds.

    Individuals, trusts and Limited companies with no number given are left
    out, which is why the share this feeds is a floor.
    """
    if party.get("identifier_type"):
        return False
    name = party.get("name") or ""
    if _AUSTRALIAN_NAME.search(name):
        return False
    if (party.get("identifier") or "").strip():
        return True
    return bool(_OVERSEAS_LEGAL_FORM.search(name))


def has_overseas_party(merger: dict) -> bool:
    """True when any acquirer or target is overseas-registered (see above)."""
    parties = (merger.get("acquirers") or []) + (merger.get("targets") or [])
    return any(is_overseas_party(p) for p in parties)


def _bucket_label(index: int) -> str:
    low = 0 if index == 0 else DURATION_BUCKETS[index - 1] + 1
    if index == len(DURATION_BUCKETS):
        return f"{low}+"
    return f"{low}–{DURATION_BUCKETS[index]}"


def _bucketed(business_days: list[int]) -> list[int]:
    """Counts per :data:`DURATION_BUCKETS` bucket, the last open-ended."""
    counts = [0] * (len(DURATION_BUCKETS) + 1)
    for bus in business_days:
        index = next((i for i, upper in enumerate(DURATION_BUCKETS) if bus <= upper), len(DURATION_BUCKETS))
        counts[index] += 1
    return counts


def _average(values: list[int]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _timing(business_days: list[int]) -> dict:
    ordered = sorted(business_days)
    return {
        "count": len(ordered),
        "median": stat_median(ordered) if ordered else None,
        "average": _average(ordered),
        "p90": _percentile(ordered, 0.9),
        "buckets": _bucketed(ordered),
    }


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _matter_ref(merger: dict, kind: str, on: str, detail: str | None = None) -> dict:
    entry = {
        "merger_id": merger.get("merger_id"),
        "merger_name": merger.get("merger_name"),
        "kind": kind,
        "date": on[:10],
    }
    if detail:
        entry["detail"] = detail
    return entry


def _phase_2_outcome_label(merger: dict, determination: str) -> str:
    if determination == merger_status.APPROVED and merger.get("has_conditions"):
        return merger_status.APPROVED_WITH_CONDITIONS
    return determination


def _milestones(mergers: list) -> list[dict]:
    """Every post-phase-1 milestone on the register, each dated.

    Kinds: ``referred`` (phase 1 → phase 2), ``phase_2_outcome`` (determination
    or cessation; ``detail`` names which), ``public_benefit_application``,
    ``tribunal_application`` (one per Tribunal matter, ``detail`` the
    applicant), ``judicial_review`` and ``ceased`` (a phase 1 review the
    parties dropped). A refused notification at phase 1 is ``phase_1_refused``.
    """
    events = []
    for m in filter_notifications(mergers):
        p1 = m.get("phase_1_determination")
        p1_date = m.get("phase_1_determination_date")
        if p1 == merger_status.REFERRED_TO_PHASE_2 and p1_date:
            events.append(_matter_ref(m, "referred", p1_date))
        elif p1 in merger_status.BLOCKED_DETERMINATIONS and p1_date:
            events.append(_matter_ref(m, "phase_1_refused", p1_date, p1))

        if p1 == merger_status.REFERRED_TO_PHASE_2 or m.get("phase_2_determination"):
            determination, determined_on = phase_2_outcome(m)
            if determination and determined_on:
                events.append(_matter_ref(
                    m, "phase_2_outcome", determined_on, _phase_2_outcome_label(m, determination),
                ))
        elif m.get("status") == merger_status.ASSESSMENT_CEASED and m.get("ceased_date"):
            events.append(_matter_ref(m, "ceased", m["ceased_date"]))

        if m.get("public_benefit_application_date"):
            events.append(_matter_ref(m, "public_benefit_application", m["public_benefit_application_date"]))
        if m.get("public_benefits_determination") and m.get("public_benefits_determination_date"):
            events.append(_matter_ref(
                m, "public_benefit_outcome", m["public_benefits_determination_date"],
                m["public_benefits_determination"],
            ))
        for appeal in m.get("appeals") or []:
            if appeal.get("filed_date"):
                events.append(_matter_ref(m, "tribunal_application", appeal["filed_date"], appeal.get("appellant")))
        review = m.get("judicial_review") or {}
        if review.get("filed_date"):
            events.append(_matter_ref(m, "judicial_review", review["filed_date"], review.get("applicant")))

    events.sort(key=lambda e: (e["date"], e["merger_id"] or "", e["kind"]))
    return events


def _industries(mergers: list) -> list[dict]:
    """Top ANZSIC divisions among ``mergers``, each matter counted once per division."""
    counts: Counter = Counter()
    names = {}
    for m in mergers:
        seen = set()
        for code_obj in m.get("anzsic_codes") or []:
            division = _division_for_code(code_obj.get("code", ""))
            if division is not None and division.code not in seen:
                seen.add(division.code)
                names[division.code] = division.name
                counts[division.code] += 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_INDUSTRIES]
    return [{"code": code, "name": names[code], "count": n} for code, n in ranked]


def _quarter_block(quarter, notifications, waivers, milestones, as_at: date) -> dict:
    key = _quarter_key(quarter)
    start, end = _quarter_bounds(quarter)

    filed = [m for m in notifications if _quarter_of(m.get("effective_notification_datetime")) == quarter]

    # Phase 1 reviews concluded this quarter, by how they concluded.
    p1_cleared, p1_referred, p1_refused = [], [], []
    for m in notifications:
        end_date = phase_1_end_date(m)
        if _quarter_of(end_date) != quarter:
            continue
        bus = calculate_business_days(m.get("effective_notification_datetime"), end_date)
        if bus is None:
            continue
        outcome = m.get("phase_1_determination")
        if outcome == merger_status.REFERRED_TO_PHASE_2:
            p1_referred.append(bus)
        elif outcome in merger_status.BLOCKED_DETERMINATIONS:
            p1_refused.append(bus)
        else:
            p1_cleared.append(bus)
    p1_ceased = sum(
        1 for m in notifications
        if m.get("status") == merger_status.ASSESSMENT_CEASED
        and not phase_1_end_date(m)
        and _quarter_of(m.get("ceased_date")) == quarter
    )

    # Waivers decided this quarter, by outcome.
    w_granted, w_refused = [], []
    refused_refiled = 0
    decided_waivers = []
    for m in waivers:
        decided_on = m.get("determination_publication_date")
        if _quarter_of(decided_on) != quarter:
            continue
        bus = calculate_business_days(m.get("effective_notification_datetime"), decided_on)
        if bus is None:
            continue
        decided_waivers.append(m)
        if m.get("accc_determination") in merger_status.BLOCKED_DETERMINATIONS:
            w_refused.append(bus)
            if (m.get("related_merger") or {}).get("relationship") in FORWARD_REFILE_RELATIONSHIPS:
                refused_refiled += 1
        else:
            w_granted.append(bus)

    p1_decided = len(p1_cleared) + len(p1_referred) + len(p1_refused)
    w_decided = len(w_granted) + len(w_refused)

    # The quarter's caseload for the "who and what" figures: notifications
    # filed in it plus waivers decided in it — the closest thing to "matters
    # that reached the ACCC this quarter" the register can say for both.
    arrivals = filed + decided_waivers

    return {
        "quarter": key,
        "label": f"Q{quarter[1]} {quarter[0]}",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "complete": end < as_at,
        "notifications": {
            "filed": len(filed),
            "phase_1_decided": p1_decided,
            "cleared": len(p1_cleared),
            "referred_to_phase_2": len(p1_referred),
            "refused": len(p1_refused),
            "ceased": p1_ceased,
            "clearance_rate": _rate(len(p1_cleared), p1_decided),
            "timing": _timing(p1_cleared + p1_referred + p1_refused),
            "average_cleared": _average(p1_cleared),
            "average_referred": _average(p1_referred + p1_refused),
        },
        "waivers": {
            "decided": w_decided,
            "granted": len(w_granted),
            "refused": len(w_refused),
            "refused_refiled": refused_refiled,
            "clearance_rate": _rate(len(w_granted), w_decided),
            "timing": _timing(w_granted + w_refused),
            "average_granted": _average(w_granted),
            "average_refused": _average(w_refused),
        },
        "matters": len(arrivals),
        "overseas_party": sum(1 for m in arrivals if has_overseas_party(m)),
        "industries": _industries(arrivals),
        "milestones": [e for e in milestones if _quarter_of(e["date"]) == quarter],
    }


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def format_rate(rate: float | None) -> str:
    """A 0–1 rate as a whole percentage ("96%"), or an en dash."""
    return "\u2013" if rate is None else f"{round(rate * 100)}%"


def percent_change(after: int | None, before: int | None) -> int | None:
    """Whole-percent change from ``before`` to ``after``; None without a base."""
    if after is None or not before:
        return None
    return round((after - before) / before * 100)


def _volume_clause(after: int, before: int, previous_label: str) -> str:
    change = percent_change(after, before)
    if change is None:
        return ""
    if change == 0:
        return f", level with {previous_label}"
    return f", {'up' if change > 0 else 'down'} {abs(change)}% on {previous_label}"


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def _timing_clause(after, before, previous_label: str) -> str:
    if after is None or before is None:
        return ""
    delta = round(after - before, 1)
    if delta == 0:
        return f", the same as {previous_label}"
    unit = "day" if abs(delta) == 1 else "days"
    return f", {_number(abs(delta))} {unit} {'slower' if delta > 0 else 'faster'} than {previous_label}"


_OUTCOME_KINDS = {"phase_2_outcome", "public_benefit_outcome"}


def findings(block: dict, previous: dict | None) -> list[str]:
    """What moved this quarter, as a short list of sentences.

    Volume comparisons are left off for a quarter still in progress — a few
    weeks of filings against a full quarter would always read as a fall — but
    its timing still compares, since a median doesn't scale with time.
    """
    prev_label = previous["label"] if previous else ""
    compare_volume = previous is not None and block["complete"]
    n, w = block["notifications"], block["waivers"]
    out = [
        f"{_plural(n['filed'], 'notification')} filed"
        f"{_volume_clause(n['filed'], previous['notifications']['filed'], prev_label) if compare_volume else ''}"
        f", and {_plural(w['decided'], 'waiver application')} decided"
        f"{_volume_clause(w['decided'], previous['waivers']['decided'], prev_label) if compare_volume else ''}."
    ]

    if n["timing"]["median"] is not None:
        p1 = _timing_clause(n["timing"]["median"], previous["notifications"]["timing"]["median"], prev_label) if previous else ""
        wv = _timing_clause(w["timing"]["median"], previous["waivers"]["timing"]["median"], prev_label) if previous else ""
        waiver_median = "\u2013" if w["timing"]["median"] is None else _number(w["timing"]["median"])
        out.append(
            f"Phase 1 reviews concluded in a median {_number(n['timing']['median'])} business days{p1}; "
            f"waivers in {waiver_median}{wv}."
        )

    if n["phase_1_decided"] or w["decided"]:
        out.append(
            f"{format_rate(w['clearance_rate'])} of waivers were granted and "
            f"{format_rate(n['clearance_rate'])} of phase 1 reviews ended in approval."
        )

    referred = n["referred_to_phase_2"]
    outcomes = [m for m in block["milestones"] if m["kind"] in _OUTCOME_KINDS]
    if referred or outcomes:
        parts = []
        if referred:
            parts.append(f"{_plural(referred, 'matter')} referred to phase 2")
        if outcomes:
            counts = Counter(m.get("detail") for m in outcomes)
            detail = ", ".join(f"{count} {str(label).lower()}" for label, count in counts.items())
            parts.append(f"{_plural(len(outcomes), 'phase 2 review')} concluded ({detail})")
        joined = "; ".join(parts)
        out.append(f"{joined[0].upper()}{joined[1:]}.")

    return out


def generate(mergers: list, as_at: date | None = None) -> dict:
    """Return the quarterly.json payload for pre-enriched mergers.

    ``as_at`` defaults to today in Sydney, as for ``analysis.current_status``:
    it decides which quarter is the current, incomplete one.
    """
    if as_at is None:
        as_at = datetime.now(_SYDNEY).date()
    notifications = filter_notifications(mergers)
    waivers = filter_waivers(mergers)
    milestones = _milestones(mergers)

    last = max(FIRST_QUARTER, _quarter_of(as_at.isoformat()))
    quarters = [
        _quarter_block(q, notifications, waivers, milestones, as_at)
        for q in _quarters_between(FIRST_QUARTER, last)
    ]
    for previous, block in zip([None] + quarters, quarters):
        block["findings"] = findings(block, previous)
    return {
        "as_at": as_at.isoformat(),
        "duration_buckets": [_bucket_label(i) for i in range(len(DURATION_BUCKETS) + 1)],
        "quarters": quarters,
    }
