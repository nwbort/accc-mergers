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
- **Pre-notification.** How long the quarter's notifications are estimated
  to have spent working with the ACCC before they were filed, inferred from
  the order case numbers were issued in (see :mod:`static_data.prenotification`)
  and measured in business days exactly as /current-status measures it. Keyed
  by filing date, since filing is what ends the stage.
- **Who and what.** The ANZSIC divisions the quarter's matters sat in.
- **Tribunal reviews.** Every Australian Competition Tribunal application live
  at some point in the quarter — lodged before it ended and not concluded
  before it began — with what happened to it in the quarter, its hearing and
  its outcome, plus how many were lodged, concluded and still open at the end.
- **Beyond phase 1.** Every phase 2 referral, phase 2 outcome, public benefit
  application, Tribunal application and Federal Court review in the quarter,
  as a dated list of matters.
- **In brief.** ``findings``, a few sentences saying what moved against the
  previous quarter. Written here rather than in the page so the page and the
  PDF report (``generate/quarterly_pdf.py``) say the same thing.
- **Commentary.** ``commentary``, hand-written points for the quarter from
  ``data/processed/quarterly_commentary.json``, shown in the brief beside the
  generated findings.

Each quarter is keyed ``2026-Q3`` in ``quarter`` and carries ``url_key``
(``26Q3``), the short form the page's ``?q=`` and the commentary file use.

Bucketing follows :func:`analysis.current_status`: a decision counts towards
the quarter it was *made* in, not the quarter the matter was filed in, so a
quarter's timing figures describe what the ACCC turned around in that quarter.
Notification inflow is keyed by filing date. No waiver inflow is published:
a waiver reaches the register only once it has been decided, so "waivers
filed this quarter" would undercount every application still in front of the
ACCC (see ``analysis.current_status`` for the same reasoning). For waivers,
decisions are the only honest count, and the page labels them so.

Only complete quarters are published. The quarter in progress is a few weeks of
filings, and every figure in it would read as a collapse against the quarter
before, so it appears once it has ended.
"""

import re
from collections import Counter
from datetime import date, datetime
from statistics import median as stat_median
from zoneinfo import ZoneInfo

from scripts.constants import merger_status, tribunal

from ..business_days import calculate_business_days
from ..durations import phase_1_end_date
from ..enrichment import phase_2_outcome
from ..filters import filter_notifications, filter_waivers
from ..loaders import FORWARD_REFILE_RELATIONSHIPS
from .analysis import _division_for_code, _percentile, _pre_notification_durations

_SYDNEY = ZoneInfo("Australia/Sydney")

#: The first quarter of the mandatory regime. Earlier quarters held only a
#: handful of voluntary-period notifications and no waivers at all, so a report
#: for them would compare nothing with nothing.
FIRST_QUARTER = (2026, 1)

#: Upper bounds (inclusive, business days) of the timing histogram's buckets;
#: the last bucket is open-ended. Five-day steps up to the phase 1 clock's 30,
#: then wider ones for the extended reviews and waivers that run long.
DURATION_BUCKETS = [4, 9, 14, 19, 24, 29, 49]

#: Bucket bounds for pre-notification, in business days. Wider than the review
#: buckets: the stage has no statutory clock and runs from nothing (a matter
#: filed the day its case was opened) to several months.
PRE_NOTIFICATION_BUCKETS = [0, 10, 20, 40, 60]

#: How many ANZSIC divisions each quarter lists.
TOP_INDUSTRIES = 5

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


def report_filename(quarter: tuple[int, int]) -> str:
    """``(2026, 3)`` → ``mergers-fyi-quarterly-merger-report-2026Q3.pdf``.

    The quarter's PDF, drawn by ``generate/quarterly_pdf.py`` and published on
    each block as ``report_pdf`` so the page links to exactly the name the PDF
    was saved under. Named for whoever downloads it: it says what it is and
    where it came from once it's sitting in a downloads folder.
    """
    return f"mergers-fyi-quarterly-merger-report-{quarter[0]}Q{quarter[1]}.pdf"


def url_key(quarter: tuple[int, int]) -> str:
    """``(2026, 3)`` → ``26Q3``: the quarter as the page URL and commentary name it."""
    return f"{quarter[0] % 100:02d}Q{quarter[1]}"


_QUARTER_KEY = re.compile(r"^(?:(\d{2})|(\d{4}))-?Q([1-4])$", re.IGNORECASE)


def normalise_quarter_key(key: str) -> tuple[int, int] | None:
    """``26Q3``, ``26q3``, ``2026Q3`` or ``2026-Q3`` → ``(2026, 3)``; None otherwise."""
    match = _QUARTER_KEY.match(key.strip())
    if not match:
        return None
    short, full, q = match.groups()
    return (2000 + int(short) if short else int(full)), int(q)


def _commentary_by_quarter(commentary: dict | None) -> dict[tuple[int, int], list[dict]]:
    """Hand-written commentary, keyed by quarter, each entry cleaned to
    ``{commentary, author?, date?}``. Blank entries are dropped; a key that
    names no quarter is reported and skipped rather than failing the run."""
    out: dict[tuple[int, int], list[dict]] = {}
    for key, entries in (commentary or {}).items():
        quarter = normalise_quarter_key(key)
        if quarter is None:
            print(f"Warning: quarterly_commentary.json key {key!r} is not a quarter (use e.g. '26Q3'); skipped")
            continue
        if isinstance(entries, (str, dict)):
            entries = [entries]
        cleaned = []
        for entry in entries or []:
            if isinstance(entry, str):
                entry = {"commentary": entry}
            text = (entry.get("commentary") or "").strip() if isinstance(entry, dict) else ""
            if not text:
                continue
            item = {"commentary": text}
            for field in ("author", "date"):
                if entry.get(field):
                    item[field] = str(entry[field])
            cleaned.append(item)
        if cleaned:
            out.setdefault(quarter, []).extend(cleaned)
    return out


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


def _bucket_labels(bounds: list[int]) -> list[str]:
    """``[4, 9]`` → ``["0–4", "5–9", "10+"]``; a one-value bucket is just its value."""
    labels = []
    for index in range(len(bounds) + 1):
        low = 0 if index == 0 else bounds[index - 1] + 1
        if index == len(bounds):
            labels.append(f"{low}+")
        elif low == bounds[index]:
            labels.append(str(low))
        else:
            labels.append(f"{low}–{bounds[index]}")
    return labels


def _bucketed(business_days: list[int], bounds: list[int] = DURATION_BUCKETS) -> list[int]:
    """Counts per bucket of ``bounds`` (inclusive upper bounds), the last open-ended."""
    counts = [0] * (len(bounds) + 1)
    for bus in business_days:
        index = next((i for i, upper in enumerate(bounds) if bus <= upper), len(bounds))
        counts[index] += 1
    return counts


def _average(values: list[int]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _timing(business_days: list[int], bounds: list[int] = DURATION_BUCKETS) -> dict:
    ordered = sorted(business_days)
    return {
        "count": len(ordered),
        "median": stat_median(ordered) if ordered else None,
        "average": _average(ordered),
        "p90": _percentile(ordered, 0.9),
        "buckets": _bucketed(ordered, bounds),
    }


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


#: How each milestone kind reads in the page's and the PDF's list.
MILESTONE_LABELS = {
    "referred": "Referred to phase 2",
    "phase_1_refused": "Not approved at phase 1",
    "ceased": "Phase 1 review ceased",
    "public_benefit_application": "Public benefit application",
    "public_benefit_outcome": "Public benefit outcome",
    "tribunal_application": "Tribunal review sought",
    "judicial_review": "Federal Court review sought",
}

#: Kinds whose detail *is* the milestone: a phase 2 review is listed as how it
#: ended ("Not approved"), not as "Phase 2 outcome · Not approved".
_LABELLED_BY_DETAIL = {"phase_2_outcome"}


def _matter_ref(merger: dict, kind: str, on: str, detail: str | None = None) -> dict:
    """One milestone row. ``label`` is what the list shows; ``detail``, when
    present, is extra context shown after the matter (an applicant's name)."""
    entry = {
        "merger_id": merger.get("merger_id"),
        "merger_name": merger.get("merger_name"),
        "kind": kind,
        "date": on[:10],
    }
    if kind in _LABELLED_BY_DETAIL and detail:
        entry["label"] = detail
    else:
        entry["label"] = MILESTONE_LABELS.get(kind, kind)
        if detail and kind != "phase_1_refused":  # its label already says it
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


def _appeal_records(mergers: list) -> list[dict]:
    """Every Tribunal matter on the register, each tagged with its merger."""
    records = []
    for m in mergers:
        for appeal in m.get("appeals") or []:
            if not appeal.get("filed_date"):
                continue
            concluded = appeal.get("status") == tribunal.APPEAL_STATUS_CONCLUDED
            outcome = appeal.get("outcome") if concluded else None
            records.append({
                "tribunal_number": appeal.get("tribunal_number"),
                "tribunal_url": appeal.get("tribunal_url"),
                "merger_id": m.get("merger_id"),
                "merger_name": m.get("merger_name"),
                "appellant": appeal.get("appellant"),
                "filed_date": appeal["filed_date"][:10],
                "hearing_date": (appeal.get("hearing_date") or "")[:10] or None,
                "concluded": concluded,
                "concluded_date": (appeal.get("concluded_date") or "")[:10] or None,
                "outcome": outcome,
                "outcome_label": tribunal.APPEAL_OUTCOME_LABELS.get(outcome) if outcome else None,
            })
    records.sort(key=lambda a: (a["filed_date"], a["tribunal_number"] or ""))
    return records


def _day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


def _appeal_note(a: dict, concluded_here: bool, open_at_end: bool, start_iso: str) -> str:
    """One line on where a Tribunal matter stood in the quarter.

    Written here so the page and the PDF describe each matter identically.
    """
    parts = ["Lodged this quarter" if a["filed_date"] >= start_iso else "Carried in from an earlier quarter"]
    if concluded_here:
        parts.append(f"concluded {_day(a['concluded_date'])}" + (f": {a['outcome_label']}" if a["outcome_label"] else ""))
    elif open_at_end:
        parts.append("open at quarter end")
        if a["concluded"] and a["concluded_date"]:
            parts.append(f"since concluded {_day(a['concluded_date'])}"
                         + (f": {a['outcome_label']}" if a["outcome_label"] else ""))
        elif a["hearing_date"]:
            parts.append(f"hearing listed for {_day(a['hearing_date'])}")
    return "; ".join(parts)


def _quarter_appeals(records: list[dict], start: date, end: date) -> dict:
    """The Tribunal matters live during ``start``–``end``, and what each did then.

    A matter recorded as concluded with no date is taken to have ended before
    any quarter it would otherwise run past, so it can't be counted open.
    """
    start_iso, end_iso = start.isoformat(), end.isoformat()
    matters = []
    for a in records:
        if a["filed_date"] > end_iso:
            continue
        concluded_on = a["concluded_date"]
        if a["concluded"]:
            # Over before the quarter began: concluded earlier, or undated and
            # lodged earlier (lodged in the quarter, it was live in it).
            ended_before = concluded_on < start_iso if concluded_on else a["filed_date"] < start_iso
            if ended_before:
                continue
        concluded_here = a["concluded"] and concluded_on is not None and start_iso <= concluded_on <= end_iso
        open_at_end = not a["concluded"] or (concluded_on is not None and concluded_on > end_iso)
        matters.append({
            **{k: v for k, v in a.items() if k != "concluded"},
            "note": _appeal_note(a, concluded_here, open_at_end, start_iso),
            # What is known *now* about a matter that was open at quarter end
            # — its outcome, if it has since concluded — is kept, but these
            # flags describe the quarter itself.
            "lodged_in_quarter": a["filed_date"] >= start_iso,
            "concluded_in_quarter": concluded_here,
            "open_at_end": open_at_end,
        })
    return {
        "lodged": sum(1 for m in matters if m["lodged_in_quarter"]),
        "concluded": sum(1 for m in matters if m["concluded_in_quarter"]),
        "open_at_end": sum(1 for m in matters if m["open_at_end"]),
        "matters": matters,
    }


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


def _quarter_block(quarter, notifications, waivers, milestones, pre_notification, appeals, commentary) -> dict:
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

    pre_days = [bus for filed_on, bus in pre_notification if _quarter_of(filed_on) == quarter]

    p1_decided = len(p1_cleared) + len(p1_referred) + len(p1_refused)
    w_decided = len(w_granted) + len(w_refused)

    # The quarter's caseload for the "who and what" figures: notifications
    # filed in it plus waivers decided in it — the closest thing to "matters
    # that reached the ACCC this quarter" the register can say for both.
    arrivals = filed + decided_waivers

    return {
        "quarter": key,
        "url_key": url_key(quarter),
        "report_pdf": report_filename(quarter),
        "label": f"Q{quarter[1]} {quarter[0]}",
        "start": start.isoformat(),
        "end": end.isoformat(),
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
        # ``count`` is the notifications with an estimate; ``filed`` above is
        # all of them. The gap is voluntary-period matters and IDs the counter
        # can't place, neither of which has a usable estimate.
        "pre_notification": _timing(pre_days, PRE_NOTIFICATION_BUCKETS),
        "matters": len(arrivals),
        "industries": _industries(arrivals),
        "appeals": _quarter_appeals(appeals, start, end),
        "commentary": commentary.get(quarter, []),
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

    Comparisons are left off for the first quarter, which has nothing before it.
    """
    prev_label = previous["label"] if previous else ""
    compare_volume = previous is not None
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

    pre = block.get("pre_notification") or {}
    if pre.get("median") is not None:
        before = (previous or {}).get("pre_notification", {}).get("median") if previous else None
        change = ""
        if before is not None:
            delta = round(pre["median"] - before, 1)
            if delta == 0:
                change = f", the same as {prev_label}"
            else:
                unit = "day" if abs(delta) == 1 else "days"
                change = f", {_number(abs(delta))} {unit} {'longer' if delta > 0 else 'shorter'} than {prev_label}"
        out.append(
            f"Notifications filed had spent an estimated median {_number(pre['median'])} business days "
            f"in pre-notification{change}."
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
            counts = Counter(m.get("label") if m["kind"] in _LABELLED_BY_DETAIL else m.get("detail") for m in outcomes)
            detail = ", ".join(f"{count} {str(label).lower()}" for label, count in counts.items())
            parts.append(f"{_plural(len(outcomes), 'phase 2 review')} concluded ({detail})")
        joined = "; ".join(parts)
        out.append(f"{joined[0].upper()}{joined[1:]}.")

    appeals = block.get("appeals") or {}
    if appeals.get("matters"):
        lodged = [m for m in appeals["matters"] if m["lodged_in_quarter"]]
        parts = []
        if lodged:
            who = ", ".join(f"{m['appellant']} ({m['tribunal_number']})" for m in lodged)
            parts.append(f"{_plural(len(lodged), 'Tribunal review')} opened: {who}")
        if appeals["concluded"]:
            parts.append(f"{_plural(appeals['concluded'], 'Tribunal review')} concluded")
        parts.append(f"{appeals['open_at_end']} open at quarter end")
        out.append("; ".join(parts) + ".")

    return out


def generate(mergers: list, as_at: date | None = None, commentary: dict | None = None) -> dict:
    """Return the quarterly.json payload for pre-enriched mergers.

    ``as_at`` defaults to today in Sydney, as for ``analysis.current_status``:
    the quarter it falls in is still running, so the last quarter published is
    the one before. ``commentary`` is quarterly_commentary.json as loaded.
    """
    if as_at is None:
        as_at = datetime.now(_SYDNEY).date()
    notifications = filter_notifications(mergers)
    waivers = filter_waivers(mergers)
    milestones = _milestones(mergers)
    pre_notification = _pre_notification_durations(notifications)
    appeals = _appeal_records(notifications)
    by_quarter = _commentary_by_quarter(commentary)

    year, q = _quarter_of(as_at.isoformat())
    last = (year - 1, 4) if q == 1 else (year, q - 1)
    quarters = [
        _quarter_block(q, notifications, waivers, milestones, pre_notification, appeals, by_quarter)
        for q in _quarters_between(FIRST_QUARTER, last)
    ]
    for previous, block in zip([None] + quarters, quarters):
        block["findings"] = findings(block, previous)
    return {
        "as_at": as_at.isoformat(),
        "duration_buckets": _bucket_labels(DURATION_BUCKETS),
        "pre_notification_buckets": _bucket_labels(PRE_NOTIFICATION_BUCKETS),
        "quarters": quarters,
    }
