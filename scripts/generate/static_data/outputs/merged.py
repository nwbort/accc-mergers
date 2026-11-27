"""Australia Merged, the year in review — ``merged.json``.

Everything the ``/merged`` deck shows, as a list of cards plus the quiz, so the
page renders what it is handed and no figure is ever typed into JSX by hand.
See `docs/australia-merged.md` for the editorial brief behind each card.

Two rules this module exists to keep:

**The numbers are derived, the wording is not.** Every figure below is computed
from the enriched mergers; every sentence is written in `_cards()`, which reads
those figures out of one `facts` dict. Editing the copy means editing strings in
one place and cannot change a number. The page then has no arithmetic in it.

**The year is a snapshot, not a live view.** `as_at` is the day the file was
generated and `complete` says whether the year has actually finished, because a
"year in review" published in December is covering eleven months and should say
so. A card that depends on the cut-off (the monthly chart's last bar) carries
`partial` so the page can mark it rather than let a short month read as a
collapse in filings.

**Scope.** Counting cards (how many matters, how fast, what share cleared) are
scoped to matters *filed* in `YEAR`, which is what a volume statistic means.
Narrative cards (the refusals, the appeals, the records) are scoped to what
*happened* in `YEAR`, because the regime's most consequential matter —
Coles – Kalgoorlie — was filed in the 2025 voluntary window and decided,
appealed and litigated through 2026. Each fact below says which it uses.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict

from scripts.constants import merger_status
from scripts.generate.static_data.business_days import (
    calculate_business_days,
    is_business_day,
)
from scripts.generate.static_data.outputs import extensions as extensions_out
from scripts.merger_filters import filter_notifications, filter_waivers

# The year the deck covers. A 2027 edition changes this line and nothing else.
YEAR = 2026

# The statutory phase 1 clock, in business days, before any extension.
STATUTORY_PHASE_1_BD = extensions_out.STATUTORY_PHASE_1_BD

MONTH_LABELS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

# Outcome keys the frontend maps to a Material shape and colour
# (frontend/src/utils/materialShapes.js, constants/mergedTones.js). They are
# the register's own determination strings so the mapping needs no translation.
#
# A card carries one only when it is *about* that outcome. In the app a shape
# is what an outcome looks like — a sunny seal is cleared, a four-sided cookie
# is refused — so putting one on a card about filing volumes would spend that
# meaning on decoration, and a glyph on all 22 cards is wallpaper either way.
GLYPH_CLEARED = merger_status.APPROVED
GLYPH_REFUSED = merger_status.NOT_APPROVED
GLYPH_LIVE = merger_status.UNDER_ASSESSMENT
GLYPH_PHASE_2 = merger_status.REFERRED_TO_PHASE_2
GLYPH_CEASED = merger_status.ASSESSMENT_CEASED


# --------------------------------------------------------------------------
# dates
# --------------------------------------------------------------------------

def _date(value: str | None) -> dt.date | None:
    """The calendar date of an ISO timestamp, or None."""
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _in_year(value: str | None, year: int) -> bool:
    d = _date(value)
    return d is not None and d.year == year


def _filed(merger: dict) -> str | None:
    return merger.get("effective_notification_datetime")


def _decided(merger: dict) -> str | None:
    return merger.get("determination_publication_date")


def _business_days_in(year: int, upto: dt.date) -> list[dt.date]:
    """Every business day of `year` up to and including `upto`."""
    day = dt.date(year, 1, 1)
    end = min(upto, dt.date(year, 12, 31))
    days = []
    while day <= end:
        if is_business_day(dt.datetime(day.year, day.month, day.day)):
            days.append(day)
        day += dt.timedelta(days=1)
    return days


def _fmt_date(value: str | dt.date | None) -> str:
    """"14 August" — a date as the cards write it, without the year."""
    d = value if isinstance(value, dt.date) else _date(value)
    return f"{d.day} {d.strftime('%B')}" if d else ""


def _fmt_full(value: str | dt.date | None) -> str:
    """"14 August 2026"."""
    d = value if isinstance(value, dt.date) else _date(value)
    return f"{d.day} {d.strftime('%B %Y')}" if d else ""


def _median(values: list[float]):
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        value = ordered[mid]
    else:
        value = round((ordered[mid - 1] + ordered[mid]) / 2, 1)
    # A whole median reads as "18", not "18.0".
    return int(value) if float(value).is_integer() else value


def _pct(part: int, whole: int, places: int = 1):
    return round(part / whole * 100, places) if whole else None


def _ref(merger: dict) -> dict:
    """A matter as the cards cite it: id, name and nothing else."""
    return {"merger_id": merger.get("merger_id"), "merger_name": merger.get("merger_name")}


# --------------------------------------------------------------------------
# facts
# --------------------------------------------------------------------------

def _volume(filed_this_year: list, notifications: list, waivers: list,
            year: int, as_at: dt.date) -> dict:
    """How many matters arrived, how often, and on which days."""
    days = [_date(_filed(m)) for m in filed_this_year]
    per_day = Counter(d for d in days if d)
    business_days = _business_days_in(year, as_at)
    quiet = [d for d in business_days if not per_day.get(d)]

    busiest_date, busiest_count = (per_day.most_common(1) or [(None, 0)])[0]
    weekday = Counter(d.strftime("%A") for d in days if d)
    weekend = [m for m in filed_this_year if (_date(_filed(m)) or as_at).weekday() >= 5]
    first_weekend = min(
        (m for m in weekend),
        key=lambda m: _filed(m) or "",
        default=None,
    )

    months = []
    for index, label in enumerate(MONTH_LABELS, start=1):
        month_days = [d for d in days if d and d.month == index]
        if not month_days and dt.date(year, index, 1) > as_at:
            continue  # a month that hasn't started yet is not a zero
        months.append({
            "month": index,
            "label": label,
            "name": dt.date(year, index, 1).strftime("%B"),
            "count": len(month_days),
            # The month the cut-off falls in is still running, so its bar is
            # short for a reason the reader needs told.
            "partial": index == as_at.month and as_at.year == year,
        })

    busiest_month = max(months, key=lambda m: (m["count"], -m["month"]), default=None)
    opening_month = months[0] if months else None

    return {
        "matters": len(filed_this_year),
        "notifications": len(notifications),
        "waivers": len(waivers),
        "business_days": len(business_days),
        "per_business_day": round(len(filed_this_year) / len(business_days), 1) if business_days else None,
        "quiet_business_days": len(quiet),
        "busiest_day": busiest_date.isoformat() if busiest_date else None,
        "busiest_day_count": busiest_count,
        "by_weekday": [
            {"day": day, "short": day[:3], "count": weekday.get(day, 0),
             "weekend": day in ("Saturday", "Sunday")}
            for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        ],
        "busiest_weekday": max(
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            key=lambda d: weekday.get(d, 0),
        ),
        "quietest_weekday": min(
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            key=lambda d: weekday.get(d, 0),
        ),
        "weekday_counts": {d: weekday.get(d, 0) for d in weekday},
        "weekend_filings": len(weekend),
        "first_weekend_filing": (
            {**_ref(first_weekend), "date": (_date(_filed(first_weekend)) or as_at).isoformat()}
            if first_weekend else None
        ),
        "months": months,
        "busiest_month": busiest_month,
        "opening_month": opening_month,
    }


def _durations(notifications: list, waivers: list, all_matters: list, year: int) -> dict:
    """How long reviews took, and the records at each end."""
    def runs(matters):
        out = []
        for m in matters:
            days = calculate_business_days(_filed(m), _decided(m))
            if days is not None:
                out.append({**_ref(m), "business_days": days,
                            "determination": m.get("accc_determination")})
        return sorted(out, key=lambda r: (r["business_days"], r["merger_id"] or ""))

    notification_runs = runs(notifications)
    waiver_runs = runs(waivers)

    # The longest *review* is scoped to what concluded in the year, not what
    # was filed in it: the longest of 2026 were filed in the 2025 voluntary
    # window, so `all_matters` is every matter on the register, not the
    # year's intake.
    concluded = runs([m for m in all_matters if _in_year(_decided(m), year)])
    longest = list(reversed(concluded))[:4]

    # Phase 1 alone, which is the clock the statute actually sets.
    phase_1 = []
    for m in notifications:
        days = calculate_business_days(_filed(m), m.get("phase_1_determination_date"))
        if days is not None:
            phase_1.append({**_ref(m), "business_days": days,
                            "determination": m.get("phase_1_determination"),
                            "has_conditions": bool(m.get("has_conditions"))})
    phase_1.sort(key=lambda r: (-r["business_days"], r["merger_id"] or ""))
    longest_cleared_phase_1 = next(
        (r for r in phase_1 if r["determination"] in merger_status.CLEARED_DETERMINATIONS),
        None,
    )

    return {
        "statutory_phase_1_bd": STATUTORY_PHASE_1_BD,
        "notification_median_bd": _median([r["business_days"] for r in notification_runs]),
        "notification_fastest_bd": notification_runs[0]["business_days"] if notification_runs else None,
        "notification_fastest_count": sum(
            1 for r in notification_runs
            if notification_runs and r["business_days"] == notification_runs[0]["business_days"]
        ),
        "waiver_median_bd": _median([r["business_days"] for r in waiver_runs]),
        "fastest_waiver": waiver_runs[0] if waiver_runs else None,
        "fastest_waiver_filed": (
            _date(_filed(next(m for m in waivers if m.get("merger_id") == waiver_runs[0]["merger_id"]))).isoformat()
            if waiver_runs else None
        ),
        "fastest_waiver_decided": (
            _date(_decided(next(m for m in waivers if m.get("merger_id") == waiver_runs[0]["merger_id"]))).isoformat()
            if waiver_runs else None
        ),
        "longest_concluded": longest,
        "longest_cleared_phase_1": longest_cleared_phase_1,
    }


def _outcomes(notifications: list, waivers: list, all_matters: list, year: int) -> dict:
    """What the ACCC decided, and the few times it said no."""
    decided = [m for m in notifications if m.get("accc_determination")]
    cleared = [m for m in decided if m.get("accc_determination") in merger_status.CLEARED_DETERMINATIONS]
    waivers_decided = [m for m in waivers if m.get("accc_determination")]
    waivers_granted = [m for m in waivers_decided
                       if m.get("accc_determination") in merger_status.CLEARED_DETERMINATIONS]

    # Refusals are scoped to the year's *decisions*, so a 2025 filing refused
    # in 2026 counts — which is the whole Coles story. The date is the phase 2
    # determination's own where there is one: a matter that goes on to apply
    # for a public benefit determination has its headline determination
    # cleared again while that runs (enrichment.public_benefit_in_progress),
    # so the refusal would otherwise have no date and drop out of the year.
    refused = []
    for m in filter_notifications(all_matters):
        phase_2 = m.get("phase_2_determination")
        if phase_2 in merger_status.BLOCKED_DETERMINATIONS:
            when = m.get("phase_2_determination_date") or _decided(m)
        elif m.get("accc_determination") in merger_status.BLOCKED_DETERMINATIONS:
            when = _decided(m)
        else:
            continue
        if _in_year(when, year):
            refused.append((when, m))
    refused.sort(key=lambda pair: pair[0] or "")

    return {
        "notifications_decided": len(decided),
        "clearance_rate_pct": _pct(len(cleared), len(decided)),
        "waivers_decided": len(waivers_decided),
        "waiver_grant_rate_pct": _pct(len(waivers_granted), len(waivers_decided)),
        "waivers_declined": len(waivers_decided) - len(waivers_granted),
        "refused": [
            {**_ref(m), "date": _date(when).isoformat()} for when, m in refused
        ],
        "refused_after_phase_2": sum(
            1 for _, m in refused if extensions_out._escalated_to_phase_2(m)
        ),
        "refused_all_phase_2": all(
            extensions_out._escalated_to_phase_2(m) for _, m in refused
        ) if refused else False,
    }


def _phase_2(notifications: list, year: int) -> dict:
    """Phase 2: how many got there and how they ended."""
    reached = [m for m in notifications if extensions_out._escalated_to_phase_2(m)]
    completed, current = [], []
    for m in reached:
        outcome = m.get("phase_2_determination")
        if m.get("status") == merger_status.ASSESSMENT_CEASED:
            outcome = merger_status.ASSESSMENT_CEASED
        if outcome:
            completed.append({**_ref(m), "outcome": outcome,
                              "has_conditions": bool(m.get("has_conditions"))})
        else:
            current.append(_ref(m))

    counts = Counter(
        merger_status.APPROVED_WITH_CONDITIONS
        if c["outcome"] in merger_status.CLEARED_DETERMINATIONS and c["has_conditions"]
        else c["outcome"]
        for c in completed
    )
    conditional = next(
        (c for c in completed
         if c["outcome"] in merger_status.CLEARED_DETERMINATIONS and c["has_conditions"]),
        None,
    )
    # A ceased matter that was notified again: the register links the two
    # with `suspended_refiled_as`, pointing forward from the abandoned one.
    came_back = [
        m for m in reached
        if m.get("status") == merger_status.ASSESSMENT_CEASED
        and (m.get("related_merger") or {}).get("relationship") == "suspended_refiled_as"
    ]
    ceased_refiled = len(came_back)

    return {
        "referred": len(reached),
        "completed": len(completed),
        "ceased_refiled": ceased_refiled,
        # The abandoned matter, not the one it was re-filed as: the card is
        # about the review that stopped.
        "ceased_refiled_matter": _ref(came_back[0]) if came_back else None,
        "current": current,
        "outcomes": [{"outcome": k, "count": v} for k, v in counts.most_common()],
        "refused": counts.get(merger_status.NOT_APPROVED, 0),
        "ceased": counts.get(merger_status.ASSESSMENT_CEASED, 0),
        "conditional": conditional,
    }


def _public_benefit(all_matters: list, year: int) -> dict:
    """The stage after a phase 2 refusal, which 2026 reached exactly once.

    A matter refused at phase 2, or cleared on conditions, has 21 calendar
    days to apply for a public benefit determination. The register then reads
    the matter as live again, which is why its refusal has no headline date
    (see `_outcomes`). The clock is 50 business days from the application.
    """
    live, decided = [], []
    for m in all_matters:
        applied = m.get("public_benefit_application_date")
        if not applied:
            continue
        entry = {
            **_ref(m),
            "short_name": _short(m.get("merger_id"), m.get("merger_name")),
            "refused_date": m.get("phase_2_determination_date"),
            "applied_date": applied,
            "response_date": m.get("public_benefit_response_date"),
            "deadline": m.get("end_of_determination_period"),
            "determination": m.get("public_benefits_determination"),
        }
        (decided if entry["determination"] else live).append(entry)

    return {
        "applications": len(live) + len(decided),
        "live": live,
        "decided": decided,
        "business_days": merger_status.PUBLIC_BENEFIT_BUSINESS_DAYS,
        "assessment_bd": merger_status.PUBLIC_BENEFIT_ASSESSMENT_BD,
        "response_bd": merger_status.PUBLIC_BENEFIT_RESPONSE_BD,
    }


def _extensions(notifications: list) -> dict:
    """The clock being stretched, and what that turned out to predict."""
    payload = extensions_out.generate(notifications)
    summary = payload["summary"]
    reasons = {r["category"]: r for r in payload["reasons"]}
    matters = [m for m in payload["matters"] if m.get("total_extension_bd")]
    top = [
        {"merger_id": m["merger_id"], "merger_name": m["merger_name"],
         "business_days": m["total_extension_bd"], "count": m["extension_count"]}
        for m in matters[:4]
    ]
    longest_single_matter = max(
        (
            m for m in payload["matters"]
            if any(e["business_days"] for e in m["extensions"])
        ),
        key=lambda m: max(e["business_days"] or 0 for e in m["extensions"]),
        default=None,
    )
    return {
        "matters_extended": summary["matters_extended"],
        "share_extended_pct": summary["share_extended_pct"],
        "events": summary["extension_events_total"],
        "total_bd": summary["total_extension_bd"],
        "longest_single_bd": summary["longest_single_bd"],
        "longest_single_matter": _ref(longest_single_matter) if longest_single_matter else None,
        "by_parties": reasons.get("Requested by the merger parties", {}).get("events", 0),
        "by_accc": reasons.get("ACCC information request", {}).get("events", 0),
        "for_remedy": reasons.get("Remedy under consideration", {}).get("events", 0),
        "base_phase_2_rate_pct": summary["base_phase_2_rate_pct"],
        "phase_2_rate_given_extension_pct": summary["escalation_rate_given_extension_pct"],
        "phase_2_preceded_by_extension": summary["extended_escalated_to_phase_2"],
        "phase_2_total": summary["phase_2_total"],
        "top": top,
    }


def _questionnaires(notifications: list, questionnaire_data: dict) -> dict:
    """What the ACCC asked the market, and how rarely it asked more."""
    names = {m.get("merger_id"): m.get("merger_name") for m in notifications}
    rows = []
    for merger_id, record in (questionnaire_data or {}).items():
        if merger_id not in names:
            continue
        count = (record or {}).get("questions_count")
        if count:
            rows.append({"merger_id": merger_id, "merger_name": names[merger_id], "count": count})
    rows.sort(key=lambda r: (-r["count"], r["merger_id"]))
    counts = [r["count"] for r in rows]
    median = _median(counts)
    return {
        "published": len(rows),
        "questions": sum(counts),
        "median": median,
        "at_median": sum(1 for c in counts if c == median),
        "most": rows[0] if rows else None,
        "fewest": rows[-1] if rows else None,
    }


def _pre_notification(notifications: list) -> dict:
    """The stage before the clock starts, which the register never dates."""
    rows = []
    for m in notifications:
        estimate = (m.get("pre_notification") or {}).get("estimated_days")
        if estimate is not None:
            rows.append({**_ref(m), "days": estimate})
    rows.sort(key=lambda r: (-r["days"], r["merger_id"] or ""))
    return {
        "estimated": len(rows),
        "median_days": _median([r["days"] for r in rows]),
        "longest": rows[:3],
    }


def _parties(filed_this_year: list) -> dict:
    """Who kept turning up."""
    counts = Counter()
    seen = defaultdict(set)
    for m in filed_this_year:
        for role in ("acquirers", "targets", "other_parties"):
            for party in m.get(role) or []:
                page = party.get("party_page") or {}
                key = page.get("id") or party.get("name")
                name = page.get("name") or party.get("name")
                if not key or m.get("merger_id") in seen[key]:
                    continue
                seen[key].add(m.get("merger_id"))
                counts[(key, name)] += 1
    top = [{"id": key, "name": name, "count": n} for (key, name), n in counts.most_common(4)]
    return {"total": len(counts), "top": top}


def _industries(filed_this_year: list) -> dict:
    counts = Counter()
    for m in filed_this_year:
        for code in m.get("anzsic_codes") or []:
            if code.get("name"):
                counts[code["name"]] += 1
    return {"top": [{"name": n, "count": c} for n, c in counts.most_common(4)]}


def _appeals(mergers: list, year: int, as_at: dt.date) -> dict:
    """Tribunal reviews lodged in the year, and the matter fighting hardest."""
    lodged = []
    for m in mergers:
        for appeal in m.get("appeals") or []:
            if _in_year(appeal.get("filed_date"), year):
                lodged.append({
                    **_ref(m),
                    "appellant": appeal.get("appellant"),
                    "number": appeal.get("tribunal_number"),
                    "filed_date": appeal.get("filed_date"),
                    "hearing_date": appeal.get("hearing_date"),
                    "concluded": bool(appeal.get("concluded_date")),
                })
    lodged.sort(key=lambda a: a.get("filed_date") or "")

    # The matter with both a Tribunal review and a Federal Court file is the
    # year's long war; if more than one, the one with the most events.
    contested = [
        m for m in mergers
        if (m.get("appeals") and m.get("judicial_reviews"))
    ]
    contested.sort(key=lambda m: len(m.get("events") or []), reverse=True)
    long_war = None
    if contested:
        m = contested[0]
        appeal = (m.get("appeals") or [{}])[0]
        review = (m.get("judicial_reviews") or [{}])[0]
        review = (m.get("judicial_reviews") or [{}])[0]
        long_war = {
            **_ref(m),
            "short_name": SHORT_NAMES.get(m.get("merger_id"), m.get("merger_name")),
            "events": len(m.get("events") or []),
            "filed_date": (_date(_filed(m)) or dt.date(year, 1, 1)).isoformat(),
            "filed_before_regime": (_date(_filed(m)) or dt.date(year, 1, 1)).year < year,
            "phase_2_referral_date": m.get("phase_1_determination_date"),
            "refused_date": _decided(m),
            "tribunal_number": appeal.get("tribunal_number"),
            "tribunal_filed_date": appeal.get("filed_date"),
            "tribunal_documents": len(appeal.get("documents") or []),
            "hearing_date": appeal.get("hearing_date"),
            "hearing_end_date": appeal.get("hearing_end_date"),
            "court_case_number": review.get("case_number"),
            "court_filed_date": review.get("filed_date"),
            "court_outcome": review.get("outcome"),
            "court_concluded_date": review.get("concluded_date"),
        }

    # Two applicants can take the same decision to the Tribunal separately
    # (MN-65005: IAG as ACT 3, RACWA as ACT 4), so the reviews outnumber the
    # decisions under review. Listing them apart reads as two disputes.
    by_matter: dict[str, dict] = {}
    for appeal in lodged:
        entry = by_matter.setdefault(
            appeal["merger_id"],
            {"merger_id": appeal["merger_id"], "merger_name": appeal["merger_name"],
             "short_name": SHORT_NAMES.get(appeal["merger_id"], appeal["merger_name"]),
             "appellants": [], "numbers": []},
        )
        entry["appellants"].append(appeal["appellant"])
        entry["numbers"].append(appeal["number"])

    pending = [a for a in lodged if not a["concluded"]]
    next_hearing = min(
        (a["hearing_date"] for a in pending
         if a.get("hearing_date") and _date(a["hearing_date"]) > as_at),
        default=None,
    )
    return {
        "lodged": lodged,
        "decisions": list(by_matter.values()),
        "undecided": len(pending),
        "next_hearing": next_hearing,
        "long_war": long_war,
    }


def _refiles(mergers: list, year: int) -> dict:
    """Waivers declined, then filed again as full notifications."""
    from scripts.generate.static_data.outputs import refiled as refiled_out

    payload = refiled_out.generate(mergers)
    completed = payload.get("completed") or []
    current = payload.get("current") or []
    cleared = [
        r for r in completed
        if r.get("notification_determination") in merger_status.CLEARED_DETERMINATIONS
    ]
    first = min(
        (r for r in completed + current if _in_year(r.get("waiver_declined_date"), year)),
        key=lambda r: r.get("waiver_declined_date") or "",
        default=None,
    )
    first_detail = None
    if first:
        first_detail = {
            "waiver_id": first.get("waiver_id"),
            "name": first.get("waiver_name"),
            "waiver_filed_date": first.get("waiver_filed_date"),
            "waiver_declined_date": first.get("waiver_declined_date"),
            "waiver_business_days": calculate_business_days(
                first.get("waiver_filed_date"), first.get("waiver_declined_date")
            ),
            "notification_id": first.get("notification_id"),
            "notification_filed_date": first.get("notification_filed_date"),
            "notification_determination_date": first.get("notification_determination_date"),
            "notification_business_days": calculate_business_days(
                first.get("notification_filed_date"),
                first.get("notification_determination_date"),
            ),
            "notification_determination": first.get("notification_determination"),
            # Declined to re-filed: how long it took to come back.
            "gap_business_days": calculate_business_days(
                first.get("waiver_declined_date"), first.get("notification_filed_date")
            ),
        }
    return {
        "refiled": len(completed) + len(current),
        "completed": len(completed),
        "cleared": len(cleared),
        "first": first_detail,
    }


def build_facts(mergers: list, questionnaire_data: dict | None,
                year: int, as_at: dt.date) -> dict:
    """Every figure the deck quotes, computed once."""
    filed_this_year = [m for m in mergers if _in_year(_filed(m), year)]
    notifications = filter_notifications(filed_this_year)
    waivers = filter_waivers(filed_this_year)

    return {
        "volume": _volume(filed_this_year, notifications, waivers, year, as_at),
        "durations": _durations(notifications, waivers, mergers, year),
        "outcomes": _outcomes(notifications, waivers, mergers, year),
        "phase_2": _phase_2(notifications, year),
        "extensions": _extensions(notifications),
        "public_benefit": _public_benefit(mergers, year),
        "questionnaires": _questionnaires(notifications, questionnaire_data),
        "pre_notification": _pre_notification(notifications),
        "parties": _parties(filed_this_year),
        "industries": _industries(filed_this_year),
        "appeals": _appeals(mergers, year, as_at),
        "refiles": _refiles(mergers, year),
    }


# --------------------------------------------------------------------------
# copy
#
# Everything below this line is wording. Every number in it comes out of the
# `facts` dict built above, so editing a sentence cannot change a figure and a
# data change cannot leave a sentence stale. Rewrite freely; keep the `{}`
# slots pointing at facts rather than typing a number in.
#
# Body paragraphs are markdown (`**bold**`), as the quarterly commentary and
# merger commentary already are, and render through the same ReactMarkdown.
# --------------------------------------------------------------------------

# The register names a matter in full ("Coles – supermarket and liquor site in
# Kalgoorlie, WA"), which is right on its own page and unreadable inside a
# sentence. These are the short forms the deck says out loud, by merger id;
# anything not listed keeps its register name. Checked at generation time
# (`_check_short_names`), so a renamed or deduped matter fails the build
# rather than quietly leaving the long name in a headline.
SHORT_NAMES = {
    "MN-01068": "Coles – Kalgoorlie",
    "MN-80005": "Kimberly-Clark / Kenvue",
    "MN-60027": "Amadeus / Idemia",
}

# Quiz 5 asks which of four well-known deals was refused. "Well known" is not
# a thing the register records, so the three cleared decoys are named here by
# hand — and checked at generation time (`_famous_cleared`), which fails the
# build if one of them is not in fact a cleared matter of the year.
# Google – Wiz, Amazon – Globalstar, Alcoa – South32 aluminium assets.
FAMOUS_CLEARED_IDS = ("MN-15002", "MN-50025", "MN-25047")

# A guess with one or two options is not a guess. A card that cannot field at
# least this many real options is dropped rather than shown as a formality.
MIN_QUIZ_OPTIONS = 3

# Three lines, because that is how it reads when it is pasted somewhere.
SHARE_TEXT = (
    "{matters} mergers. {refused} refused.\n"
    "I got {score} out of {total} on Australia Merged {year}\n"
    "https://mergers.fyi/merged"
)

# Keyed by score. The generator fills a line in for every possible score, so
# the table has to cover 0 to however many questions the deck ends up with.
SCORE_LINES = {
    "all": "You got all {total} questions right. You had your finger on the pulse.",
    "most": "You got {score} of {total} right. Respectable.",
    "some": "You got {score} of {total} right. The register is right there.",
    "none": "You got none of them. Nobody saw this year coming either.",
}


def _score_lines(total: int) -> dict:
    """A line per possible score, so the page never has to pick one."""
    lines = {}
    for score in range(total + 1):
        if total and score == total:
            key = "all"
        elif score == 0:
            key = "none"
        elif score >= total / 2:
            key = "most"
        else:
            key = "some"
        lines[str(score)] = SCORE_LINES[key].format(score=score, total=total)
    return lines


def _famous_cleared(mergers: list, year: int) -> list[dict]:
    """The hand-named decoys for quiz 5, checked against the register."""
    by_id = {m.get("merger_id"): m for m in mergers}
    chosen = []
    for merger_id in FAMOUS_CLEARED_IDS:
        merger = by_id.get(merger_id)
        if merger is None:
            raise ValueError(
                f"merged.json: FAMOUS_CLEARED_IDS names {merger_id}, which is not "
                f"on the register. Name a matter that is, or drop the card."
            )
        if merger.get("accc_determination") not in merger_status.CLEARED_DETERMINATIONS:
            raise ValueError(
                f"merged.json: FAMOUS_CLEARED_IDS names {merger_id} "
                f"({merger.get('merger_name')}) as a cleared decoy, but its "
                f"determination is {merger.get('accc_determination')!r}. The quiz "
                f"would be wrong — name a different matter."
            )
        if not _in_year(_decided(merger), year):
            raise ValueError(
                f"merged.json: FAMOUS_CLEARED_IDS names {merger_id}, decided "
                f"{(_decided(merger) or '')[:10] or 'never'}, which is not in {year}."
            )
        chosen.append(_ref(merger))
    return chosen


def _check_short_names(mergers: list) -> None:
    """Every short form must still name a matter on the register."""
    known = {m.get("merger_id") for m in mergers}
    missing = sorted(set(SHORT_NAMES) - known)
    if missing:
        raise ValueError(
            f"merged.json: SHORT_NAMES names {', '.join(missing)}, which "
            f"{'is' if len(missing) == 1 else 'are'} not on the register. "
            f"Drop the entry or point it at the matter that replaced it."
        )


def _short(merger_id: str | None, fallback: str | None) -> str:
    """How the deck says a matter's name inside a sentence."""
    return SHORT_NAMES.get(merger_id) or fallback or ""


def _link(merger_id: str | None, fallback: str | None = None) -> str:
    """A matter's name as a markdown link to its page.

    Every matter the deck names in prose links to it, so a reader who wants
    the detail is one tap away. The exception is a quiz option, where a link
    would both give the game away and be the wrong thing to tap.
    """
    name = _short(merger_id, fallback)
    return f"[{name}](/mergers/{merger_id})" if merger_id else name


def _plural(n: int, one: str, many: str | None = None) -> str:
    return one if n == 1 else (many or one + "s")


def _outcome_plural(outcome: str, count: int) -> str:
    """"3 assessments ceased", not "3 assessment ceased"."""
    lower = (outcome or "").lower()
    if count == 1:
        return lower
    # Only the noun takes the plural: it is the assessments that ceased.
    return lower.replace("assessment ", "assessments ", 1)


def _join(items: list[str]) -> str:
    """"a, b and c" — a list as a sentence reads it."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def _cards(f: dict, mergers: list, filed_this_year: list, year: int, as_at: dt.date) -> list[dict]:
    v, d, o = f["volume"], f["durations"], f["outcomes"]
    p2, ext, q = f["phase_2"], f["extensions"], f["questionnaires"]
    pre, parties, inds = f["pre_notification"], f["parties"], f["industries"]
    benefit = f["public_benefit"]
    appeals, refiles = f["appeals"], f["refiles"]

    war = appeals["long_war"]
    fastest_waiver = d["fastest_waiver"]
    longest = d["longest_concluded"]
    slowest = longest[0] if longest else None
    top_party = parties["top"][0] if parties["top"] else None
    runner_up = parties["top"][1] if len(parties["top"]) > 1 else None
    first_refile = refiles["first"]

    cards = [{
        "id": "opening",
        "kind": "opening",
        "tone": "primary",
        "eyebrow": f"{year} year in review",
        "heading": "Australia Merged",
        "lede": (
            f"Year one of mandatory merger control. **{v['matters']} deals** went "
            f"to the ACCC. Almost all of them were fine."
        ),
        "body": ["Almost."],
    }]

    cards.append({
        "id": "scale",
        "kind": "stat",
        "tone": "primary-container",
        "eyebrow": "The scale",
        "stat": v["matters"],
        "heading": f"matters came to the ACCC in {year}",
        "figures": [
            {"value": v["notifications"], "label": "notifications"},
            {"value": v["waivers"], "label": "waiver applications"},
            {"value": v["per_business_day"], "label": "a business day"},
        ],
        "body": [
            f"Only **{v['quiet_business_days']}** of the year's "
            f"{v['business_days']} business days passed without a single filing."
        ] if v["business_days"] else [],
    })

    if v["opening_month"] and v["busiest_month"] and v["opening_month"]["count"]:
        cards.append({
            "id": "months",
            "kind": "months",
            "tone": "surface",
            "eyebrow": "The shape of the year",
            "heading": (
                f"{v['opening_month']['name']} was a trickle. By "
                f"{v['busiest_month']['name']} the ACCC was taking "
                f"{v['busiest_month']['count']} matters a month."
            ),
            "months": v["months"],
            "body": [
                f"Around {round(v['busiest_month']['count'] / v['opening_month']['count'])} "
                f"times the opening pace. It never went back."
            ],
        })

    if v["busiest_day"]:
        busiest = dt.date.fromisoformat(v["busiest_day"])
        body = [
            f"**{busiest.strftime('%A')} {_fmt_date(busiest)}.** "
            f"{v['busiest_weekday']}s took "
            f"{v['weekday_counts'].get(v['busiest_weekday'], 0)} filings across the "
            f"year. {v['quietest_weekday']}s took "
            f"{v['weekday_counts'].get(v['quietest_weekday'], 0)}."
        ]
        if v["weekend_filings"] and v["first_weekend_filing"]:
            first_day = dt.date.fromisoformat(v["first_weekend_filing"]["date"])
            same_day = sum(
                1 for day in [_date(_filed(m)) for m in filed_this_year] if day == first_day
            )
            body.append(
                f"{v['weekend_filings']} deals were filed on a **weekend**. "
                f"{same_day} lonely souls filed on {first_day.strftime('%A')} "
                f"{_fmt_date(first_day)}."
            )
        cards.append({
            "id": "quiz-weekday",
            "kind": "quiz",
            "tone": "tertiary-container",
            "eyebrow": "Guess",
            "question": (
                f"One day in {year}, {v['busiest_day_count']} matters landed at once. "
                f"What day of the week was it?"
            ),
            "options": [
                {"key": day["day"], "label": day["day"]} for day in v["by_weekday"]
            ],
            "answer": busiest.strftime("%A"),
            # The week behind the answer: a single busiest day means little
            # without the shape of an ordinary one beside it.
            "weekdays": v["by_weekday"],
            "body": body,
        })

    if d["notification_median_bd"]:
        body = []
        if fastest_waiver and d["fastest_waiver_filed"] and d["fastest_waiver_decided"]:
            filed = dt.date.fromisoformat(d["fastest_waiver_filed"])
            answered = dt.date.fromisoformat(d["fastest_waiver_decided"])
            body.append(
                f"Waivers ran to a median of **{d['waiver_median_bd']}**. The fastest "
                f"took only **{fastest_waiver['business_days']}**. "
                f"{_link(fastest_waiver['merger_id'], fastest_waiver['merger_name'])} "
                f"filed on {filed.strftime('%A')} "
                f"{_fmt_date(filed)} and had its answer on the "
                f"{answered.strftime('%A')}."
            )
        cards.append({
            "id": "speed",
            "kind": "rail",
            "tone": "secondary-container",
            "eyebrow": "Speed",
            "heading": (
                f"The law gives the ACCC {d['statutory_phase_1_bd']} business days. "
                f"It used a median of {d['notification_median_bd']}."
            ),
            "rail": {
                "used": d["notification_median_bd"],
                "total": d["statutory_phase_1_bd"],
                "statutory": d["statutory_phase_1_bd"],
                "mark": d["notification_median_bd"],
                "mark_label": f"Median {d['notification_median_bd']}",
                "start_label": "Day 1",
                "end_label": f"Day {d['statutory_phase_1_bd']}",
            },
            "lede": (
                f"Half of all phase 1 reviews were done with "
                f"{d['statutory_phase_1_bd'] - d['notification_median_bd']} business "
                f"days to spare."
            ),
            "body": body,
        })

    if o["clearance_rate_pct"] is not None:
        body = []
        if o["waiver_grant_rate_pct"] is not None:
            body.append(
                f"**{o['waiver_grant_rate_pct']}%** of waiver applications were "
                f"granted. If you filed a merger in Australia in {year}, you were "
                f"almost certainly fine."
            )
        cards.append({
            "id": "verdict",
            "kind": "stat",
            "tone": "cleared",
            "glyph": GLYPH_CLEARED,
            "eyebrow": "The verdict",
            "stat": o["clearance_rate_pct"],
            "stat_suffix": "%",
            "heading": "of decided notifications ended in clearance",
            "body": body,
            "coda": "Almost.",
        })

    if o["refused"]:
        cards.append({
            "id": "refusals",
            "kind": "rows",
            "tone": "refused",
            "glyph": GLYPH_REFUSED,
            "eyebrow": "The exceptions",
            "heading": (
                f"{len(o['refused'])} {_plural(len(o['refused']), 'deal was', 'deals were')} "
                f"refused"
                + (
                    ". Every one had been through phase 2."
                    if o["refused_all_phase_2"] else
                    f", {o['refused_after_phase_2']} of them after phase 2."
                )
            ),
            "rows": [
                {
                    "glyph": GLYPH_REFUSED,
                    "merger_id": r["merger_id"],
                    "text": (
                        f"**{_link(r['merger_id'], r['merger_name'])}**, "
                        f"refused {_fmt_date(r['date'])}."
                    ),
                }
                for r in o["refused"]
            ],
        })

    if slowest and len(longest) >= MIN_QUIZ_OPTIONS:
        cards.append({
            "id": "quiz-longest",
            "kind": "quiz",
            "tone": "surface",
            "eyebrow": "Guess",
            "question": f"Which review concluded in {year} took the longest?",
            "options": [
                {"key": r["merger_id"], "label": r["merger_name"]}
                for r in longest
            ],
            "answer": slowest["merger_id"],
            "body": [
                f"**{_link(slowest['merger_id'], slowest['merger_name'])}: "
                f"{slowest['business_days']} business days**, "
                f"notification to determination. That is "
                f"{round(slowest['business_days'] / d['statutory_phase_1_bd'], 1)} times "
                f"the statutory phase 1 clock.",
                "Runners-up: "
                + _join([
                    f"{_link(r['merger_id'], r['merger_name'])} at {r['business_days']}"
                    for r in longest[1:]
                ])
                + ".",
            ],
        })

    cards.append({
        "id": "extensions",
        "kind": "stat",
        "tone": "phase-2",
        "glyph": GLYPH_PHASE_2,
        "eyebrow": "Extensions",
        "stat": ext["total_bd"],
        "heading": f"business days of extra time, across {ext['events']} extensions",
        "body": [
            f"**{ext['matters_extended']} matters** had their clock extended in {year}, "
            f"{ext['share_extended_pct']}% of notifications. The merger parties asked "
            f"for {ext['by_parties']} of the {ext['events']}, the ACCC for "
            f"{ext['by_accc']}, and {ext['for_remedy']} were to weigh a remedy.",
        ],
        "figures": [
            {"value": ext["base_phase_2_rate_pct"], "suffix": "%",
             "label": "phase 2 referral rate"},
            {"value": ext["phase_2_rate_given_extension_pct"], "suffix": "%",
             "label": "referred when extended"},
        ],
        "coda": (
            f"{ext['phase_2_preceded_by_extension']} of the {ext['phase_2_total']} "
            f"phase 2 referrals had been extended first."
        ),
    })

    if len(ext["top"]) >= MIN_QUIZ_OPTIONS:
        winner = ext["top"][0]
        cards.append({
            "id": "quiz-extension",
            "kind": "quiz",
            "tone": "surface",
            "eyebrow": "Guess",
            "question": "Which deal ate the most of that extra time?",
            "options": [
                {"key": r["merger_id"], "label": r["merger_name"]} for r in ext["top"]
            ],
            "answer": winner["merger_id"],
            "body": [
                f"**{_link(winner['merger_id'], winner['merger_name'])}: "
                f"{winner['business_days']} business days**, "
                f"over {winner['count']} separate "
                f"{_plural(winner['count'], 'extension')}.",
                f"The single biggest one-off extension went to "
                f"{_link(ext['longest_single_matter']['merger_id'], ext['longest_single_matter']['merger_name'])}: "
                f"**{ext['longest_single_bd']} business days**, more extra time than "
                f"the whole statutory clock allows.",
            ],
        })

    slow_p1 = d["longest_cleared_phase_1"]
    if slow_p1 and slow_p1["business_days"] > d["statutory_phase_1_bd"]:
        cards.append({
            "id": "extension-cost",
            "kind": "rail",
            "tone": "phase-2",
            "glyph": GLYPH_PHASE_2,
            "eyebrow": "What an extension costs",
            "rail": {
                "used": slow_p1["business_days"],
                "total": slow_p1["business_days"],
                "statutory": d["statutory_phase_1_bd"],
                "mark": d["statutory_phase_1_bd"],
                "mark_label": f"Statutory day {d['statutory_phase_1_bd']}",
                "start_label": "Day 1",
                "end_label": f"Day {slow_p1['business_days']}",
            },
            "merger_id": slow_p1["merger_id"],
            "heading": (
                f"{slow_p1['merger_name']} spent {slow_p1['business_days']} business "
                f"days in phase 1."
            ),
            "lede": (
                f"The clock is {d['statutory_phase_1_bd']}. It had the longest phase 1 "
                f"review of any deal the ACCC cleared all year."
            ),
        })

    cards.append({
        "id": "phase-2",
        "kind": "rows",
        "tone": "surface",
        "glyph": GLYPH_PHASE_2,
        "eyebrow": "Phase 2",
        "stat": p2["referred"],
        "heading": (
            f"matters went to phase 2, out of {v['notifications']}. "
            f"{p2['completed']} finished."
        ),
        "rows": (
            [
                {
                    "glyph": (
                        GLYPH_REFUSED if row["outcome"] == merger_status.NOT_APPROVED
                        else GLYPH_CEASED if row["outcome"] == merger_status.ASSESSMENT_CEASED
                        else GLYPH_CLEARED
                    ),
                    "text": f"**{row['count']} {_outcome_plural(row['outcome'], row['count'])}**",
                }
                for row in p2["outcomes"]
            ]
            + ([{
                "glyph": GLYPH_LIVE,
                "text": "**" + str(len(p2["current"])) + " still running**: "
                        + _join([
                            _link(c["merger_id"], c["merger_name"]) for c in p2["current"]
                        ]),
            }] if p2["current"] else [])
        ),
        "body": [
            f"{p2['ceased']} of the {p2['completed']} completed phase 2 reviews ended "
            f"with the parties walking away."
        ] if p2["ceased"] else [],
        "coda": (
            f"But {p2['ceased_refiled']} came back."
            if p2["ceased_refiled"] == 1 and p2["ceased_refiled_matter"]
            else None
        ),
        "coda_merger_id": (
            p2["ceased_refiled_matter"]["merger_id"] if p2["ceased_refiled_matter"] else None
        ),
    })

    if war:
        cards.append({
            "id": "long-war",
            "kind": "timeline",
            "tone": "appeal",
            "glyph": GLYPH_REFUSED,
            "eyebrow": "The long war",
            "merger_id": war["merger_id"],
            "heading": (
                f"{war['short_name']} was filed before the regime was mandatory, "
                f"and it continues."
                if war["filed_before_regime"]
                else f"{war['short_name']} continues."
            ),
            "timeline": [
                {"date": war["filed_date"], "label": "**Filed**"
                    + (" in the voluntary window" if war["filed_before_regime"] else "")},
                {"date": war["phase_2_referral_date"], "label": "**Referred to phase 2**"},
                {"date": war["refused_date"], "label": "**Refused**"},
                {"date": war["tribunal_filed_date"],
                 "label": f"**Tribunal review lodged**, {war['tribunal_number']}"},
                {"date": war["court_filed_date"],
                 "label": f"**Federal Court judicial review filed**, {war['court_case_number']}"},
                {"date": war.get("court_concluded_date"),
                 "label": f"**Federal Court review {war.get('court_outcome') or 'concluded'}**"},
                {"date": war["hearing_date"], "end_date": war.get("hearing_end_date"),
                 "label": "**Tribunal hearing**"},
            ],
            "body": ["Tribunal decision forthcoming."],
        })

    if benefit["applications"]:
        first = (benefit["live"] + benefit["decided"])[0]
        cards.append({
            "id": "public-benefit",
            "kind": "timeline",
            "tone": "phase-2",
            "glyph": GLYPH_PHASE_2,
            "eyebrow": "The stage nobody had reached",
            "merger_id": first["merger_id"],
            "heading": (
                f"A refused merger gets one more argument: that it is good for "
                f"the public anyway."
            ),
            "timeline": [
                {"date": first["refused_date"], "label": "**Refused at phase 2**"},
                {"date": first["applied_date"],
                 "label": f"**{_link(first['merger_id'], first['merger_name'])} applied**"},
                {"date": first["response_date"],
                 "label": f"**Responses or a remedy due**, business day {benefit['response_bd']}"},
                {"date": first["deadline"],
                 "label": f"**Determination due**, business day {benefit['business_days']}"},
            ],
            "body": [
                f"{_plural(benefit['applications'], 'One matter', 'Matters')} reached it "
                f"in {year}, and the ACCC has {benefit['business_days']} business days "
                f"to decide."
                if benefit["applications"] == 1 else
                f"{benefit['applications']} matters reached it in {year}, each with "
                f"{benefit['business_days']} business days on the clock."
            ],
            "coda": (
                "A merger refused in September could still be cleared."
                if benefit["live"] else None
            ),
        })

    if appeals["lodged"]:
        cards.append({
            "id": "appeals",
            "kind": "rows",
            "tone": "appeal",
            "glyph": GLYPH_REFUSED,
            "eyebrow": "Appeals",
            "stat": len(appeals["lodged"]),
            "heading": (
                f"Tribunal {_plural(len(appeals['lodged']), 'review was', 'reviews were')} "
                f"lodged in {year}, over "
                + (
                    f"{len(appeals['decisions'])} decisions. "
                    if len(appeals["decisions"]) != len(appeals["lodged"])
                    else f"{_plural(len(appeals['decisions']), 'one decision', 'as many decisions')}. "
                )
                + (
                    "None has been decided."
                    if appeals["undecided"] == len(appeals["lodged"])
                    else f"{appeals['undecided']} are still undecided."
                )
            ),
            # One row per decision under review, not per review: two applicants
            # taking the same decision to the Tribunal is one dispute.
            "rows": [
                {
                    "glyph": GLYPH_REFUSED,
                    "merger_id": decision["merger_id"],
                    "text": (
                        f"**{_join(decision['appellants'])}**"
                        + (" both" if len(decision["appellants"]) == 2 else "")
                        + (" each" if len(decision["appellants"]) > 2 else "")
                        + f" appealed over {_link(decision['merger_id'], decision['merger_name'])}"
                        + f" ({_join(decision['numbers'])})"
                    ),
                }
                for decision in appeals["decisions"]
            ],
            "body": (
                [f"The next hearing starts **{_fmt_full(appeals['next_hearing'])}**. "
                 f"Year one ends with the hard questions all still open."]
                if appeals["next_hearing"] else []
            ),
        })

    if q["most"]:
        cards.append({
            "id": "quiz-questions",
            "kind": "quiz",
            "tone": "surface",
            "eyebrow": "Guess",
            "question": (
                f"The ACCC published {q['published']} market questionnaires in {year}, "
                f"asking {q['questions']:,} questions. The median asked {q['median']}. "
                f"How many did the most-questioned deal get?"
            ),
            "options": _question_options(q["most"]["count"]),
            "answer": str(q["most"]["count"]),
            "body": [
                f"**{q['most']['count']}**, for "
                f"{_link(q['most']['merger_id'], q['most']['merger_name'])}. The shortest, "
                f"{_link(q['fewest']['merger_id'], q['fewest']['merger_name'])}, "
                f"got {q['fewest']['count']}.",
                f"{q['at_median']} of the {q['published']} asked exactly {q['median']} "
                f"questions, drawing on a standard set. When the ACCC asks a fourth "
                f"question, pay attention.",
            ],
        })

    if pre["longest"]:
        cards.append({
            "id": "pre-notification",
            "kind": "stat",
            "tone": "secondary-container",
            "eyebrow": "Before the clock starts",
            "stat": pre["median_days"],
            "heading": "estimated median days in pre-notification, before day one",
            "body": [
                f"The longest: **{_link(pre['longest'][0]['merger_id'], pre['longest'][0]['merger_name'])}**, "
                f"an estimated **{pre['longest'][0]['days']} days** of conversation with "
                f"the ACCC before the clock even started. "
                + _join([
                    _link(r["merger_id"], r["merger_name"]) for r in pre["longest"][1:]
                ])
                + (
                    " took the next two places."
                    if len(pre["longest"]) > 2
                    else " took second place."
                ),
            ],
        })

    if len(parties["top"]) >= MIN_QUIZ_OPTIONS:
        cards.append({
            "id": "quiz-parties",
            "kind": "quiz",
            "tone": "surface",
            "eyebrow": "Guess",
            "question": (
                f"{parties['total']:,} different companies appeared on the register in "
                f"{year}. Who turned up most?"
            ),
            "options": [
                {"key": r["id"], "label": r["name"]} for r in parties["top"]
            ],
            "answer": top_party["id"],
            "body": [
                f"**{top_party['name']}: {top_party['count']} matters.**"
                + (
                    f" {runner_up['name']} was second with {runner_up['count']}."
                    if runner_up else ""
                ),
            ],
        })

    if inds["top"]:
        cards.append({
            "id": "industries",
            "kind": "ranking",
            "tone": "primary-container",
            "eyebrow": "What Australia actually bought",
            "heading": (
                f"The most-tagged industry of the year was {inds['top'][0]['name']}."
            ),
            "ranking": [
                {"label": r["name"], "value": r["count"]} for r in inds["top"]
            ],
            "ranking_unit": "Industry",
        })

    if o["refused"]:
        decoys = _famous_cleared(mergers, year)
        answer = o["refused"][0]
        cards.append({
            "id": "quiz-refused",
            "kind": "quiz",
            "tone": "surface",
            "eyebrow": "Guess",
            "question": "Last one. Which of these did the ACCC refuse?",
            "options": [
                {"key": r["merger_id"], "label": _short(r["merger_id"], r["merger_name"])}
                for r in decoys + [answer]
            ],
            "answer": answer["merger_id"],
            # No reveal: the answer is the whole joke, and explaining it
            # would be explaining it.
            "body": [],
        })

    if first_refile:
        cards.append({
            "id": "comeback",
            "kind": "stat",
            "tone": "cleared",
            "glyph": GLYPH_CLEARED,
            "eyebrow": "The comeback",
            "lede": "Getting knocked back isn't the end.",
            "stat": refiles["refiled"],
            "heading": "deals were refused a waiver and came back as a full notification",
            "body": [
                f"Of the {refiles['completed']} that have finished, "
                f"**{refiles['cleared']} were cleared.**",
                f"**{_link(first_refile['notification_id'], first_refile['name'])}** was "
                f"the first knocked back, {first_refile['waiver_business_days']} business "
                f"days after filing, only to come back stronger "
                f"{first_refile['gap_business_days']} business days later.",
            ],
        })

    # The only card the generator cannot write: the figures come from this
    # browser's own follow list. `{followed}` and `{industries}` are filled in
    # by the page (pages/Merged.jsx), which is also why the counts are not in
    # `facts` — they never leave the device.
    cards.append({
        "id": "your-year",
        "kind": "personal",
        "tone": "tertiary-container",
        "eyebrow": "Your year",
        "heading": "You followed {followed} matters this year.",
        "body": ["Keep it up."],
        "industries_line": "You followed {industries}: {names}.",
        "empty_heading": "You didn't follow any matters this year.",
        "empty_body": "There's always next year.",
    })

    cards.append({
        "id": "closing",
        "kind": "closing",
        "tone": "primary",
        "eyebrow": "That was year one",
        "heading": f"{v['matters']} matters",
        "figures": [
            {"value": o["clearance_rate_pct"], "suffix": "%", "label": "cleared"},
            {"value": len(o["refused"]), "label": "refused"},
            {"value": len(appeals["lodged"]), "label": "in the Tribunal"},
        ],
        "lede": f"See you in {year + 1}.",
    })

    return cards


def _question_options(answer: int) -> list[dict]:
    """Four plausible answers for the questionnaire card, around the real one.

    Spread rather than centred: the median is three, so every option should
    feel absurd, and the over-guess should be the furthest away.
    """
    candidates = sorted({
        max(2, answer // 2),
        max(3, answer - 4),
        answer,
        answer * 2,
    })
    while len(candidates) < 4:
        candidates.append(max(candidates) + 5)
    return [{"key": str(c), "label": str(c)} for c in sorted(candidates)[:4]]


def _quiz(cards: list[dict]) -> list[dict]:
    """The quiz cards in order, as the page's score needs them."""
    return [
        {"id": c["id"], "question": c["question"], "answer": c["answer"]}
        for c in cards if c["kind"] == "quiz"
    ]


def generate(mergers: list, questionnaire_data: dict | None = None,
             *, year: int = YEAR, today: dt.date | None = None) -> dict:
    """Return the merged.json payload."""
    as_at = today or dt.date.today()
    _check_short_names(mergers)
    facts = build_facts(mergers, questionnaire_data, year, as_at)
    filed_this_year = [m for m in mergers if _in_year(_filed(m), year)]
    cards = _cards(facts, mergers, filed_this_year, year, as_at)
    quiz = _quiz(cards)
    complete = as_at >= dt.date(year, 12, 31)

    for index, card in enumerate(cards, start=1):
        card["index"] = index
    for position, card in enumerate(c for c in cards if c["kind"] == "quiz"):
        card["eyebrow"] = f"{card['eyebrow']} · {position + 1} of {len(quiz)}"

    return {
        "year": year,
        "as_at": as_at.isoformat(),
        "complete": complete,
        "coverage": (
            f"Figures cover 1 January to 31 December {year}."
            if complete else
            f"Figures cover 1 January to {_fmt_full(as_at)}; the year is not over."
        ),
        "share_text": SHARE_TEXT,
        "score_lines": _score_lines(len(quiz)),
        "quiz_total": len(quiz),
        "facts": facts,
        "cards": cards,
    }
