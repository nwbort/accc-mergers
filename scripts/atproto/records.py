"""Turn a generated merger detail file into a ``fyi.mergers.matter`` record.

The input is whatever ``generate_static_data`` wrote into
``frontend/public/data/mergers/`` - the same JSON the site serves. That is the
point: the ATmosphere copy should say exactly what mergers.fyi says, so the
two can never quietly drift into two different accounts of the register.

Three things this module is careful about:

* **Dates, not timestamps.** The register publishes dates; the pipeline stores
  them as midday UTC so they survive a timezone round trip. Republishing that
  midday as a real instant would be inventing a fact, so every date-shaped
  field is emitted as a plain ``YYYY-MM-DD`` string. Only ``indexedAt``, which
  really is an instant we know, is a datetime.
* **Nothing empty.** Absent is absent: a key with ``null`` or ``[]`` behind it
  costs bytes in every consumer's copy of the repo and says nothing a missing
  key doesn't.
* **A stable digest.** ``record_digest`` hashes everything *except*
  ``indexedAt``, so an unchanged matter hashes the same forever and a publish
  run rewrites only what moved. Without that, every run would rewrite every
  record and the collection's history would be noise.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from scripts.atproto import config

#: Record keys may only hold these characters (and may not be "." or "..").
RKEY_ALLOWED = re.compile(r"^[A-Za-z0-9._:~-]{1,512}$")

#: Matches the lexicon's declared cap on ``summary``.
MAX_SUMMARY_GRAPHEMES = 6000

#: Matches the lexicon's declared cap on ``events``.
MAX_EVENTS = 200

#: Phrases that classify a timeline entry the pipeline left unflagged. Ordered:
#: the first match wins, so the more specific phrases come first.
_EVENT_KIND_PHRASES: tuple[tuple[str, str], ...] = (
    ("notice of competition concerns", "competition-concerns-notice"),
    ("subject to phase 2", "phase-2-referral"),
    ("timeline extended", "timeline-extension"),
    ("remedy offer", "remedy-offer"),
    ("undertaking", "undertaking"),
    ("questionnaire", "questionnaire"),
    ("notified to accc", "notification"),
)


def load_matters(directory: Path | None = None) -> list[dict]:
    """Read every generated merger detail file, oldest matter id first.

    The directory also holds the paginated list files, which carry no
    ``merger_id`` and are skipped on that basis rather than by filename - the
    list files have been renamed before now.
    """
    directory = Path(directory) if directory else config.MATTER_DATA_DIR
    matters = []
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("merger_id"):
            matters.append(payload)
    return matters


def matter_rkey(merger_id: str) -> str:
    """Validate a matter id for use as a record key.

    ACCC matter ids (``MN-01016``) are already legal record keys, so this is a
    guard against a future id format rather than a transformation: silently
    mangling an id would break the addressability that keying on it buys.
    """
    rkey = (merger_id or "").strip()
    if rkey in {".", ".."} or not RKEY_ALLOWED.match(rkey):
        raise ValueError(f"matter id is not a usable record key: {merger_id!r}")
    return rkey


def event_kind(event: dict) -> str:
    """Classify one timeline entry.

    The pipeline's own flags win, because they survive the ACCC re-titling an
    entry; the phrase table only covers what carries no flag.
    """
    if event.get("is_appeal"):
        return "appeal"
    if event.get("is_determination_event"):
        return "determination"
    if event.get("is_questionnaire_event"):
        return "questionnaire"

    title = (event.get("display_title") or event.get("title") or "").lower()
    for phrase, kind in _EVENT_KIND_PHRASES:
        if phrase in title:
            return kind
    return "other"


def matter_record(merger: dict, *, indexed_at: str) -> dict:
    """Build the ``fyi.mergers.matter`` record for one matter."""
    merger_id = merger["merger_id"]

    record: dict = {
        "$type": config.MATTER_COLLECTION,
        "matterId": merger_id,
        "title": merger.get("merger_name") or merger_id,
        "matterType": "waiver" if merger.get("is_waiver") else "notification",
        "status": merger.get("status") or "Under assessment",
        "url": f"{config.SITE_URL}/mergers/{merger_id}",
        "indexedAt": indexed_at,
    }

    _set(record, "summary", _truncate(merger.get("merger_description")))
    _set(record, "phase", merger.get("stage"))
    _set(record, "registerUrl", merger.get("url"))

    notified = _date(merger.get("effective_notification_datetime"))
    originally = _date(merger.get("original_notification_datetime"))
    _set(record, "notifiedOn", notified)
    # Only worth carrying when the clock was actually reset; otherwise it is
    # the same date twice.
    if originally and originally != notified:
        record["originallyNotifiedOn"] = originally
    _set(record, "determinationDueBy", _date(merger.get("end_of_determination_period")))
    _set(record, "consultationClosesOn", _date(merger.get("consultation_response_due_date")))

    _set(record, "acquirers", _parties(merger.get("acquirers")))
    _set(record, "targets", _parties(merger.get("targets")))
    _set(record, "otherParties", _parties(merger.get("other_parties")))
    _set(record, "industries", _industries(merger.get("anzsic_codes")))

    _set(record, "determinations", _determinations(merger))
    _set(record, "appeals", _appeals(merger))
    _set(record, "events", _events(merger.get("events")))

    return record


def record_digest(record: dict) -> str:
    """Content hash of a record, ignoring when it was written.

    ``indexedAt`` is excluded so that "has this matter changed" is a question
    about the matter, not about the clock.
    """
    body = {k: v for k, v in record.items() if k != "indexedAt"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Field builders
# ---------------------------------------------------------------------------


def _set(record: dict, key: str, value) -> None:
    """Assign only truthy values - see "Nothing empty" in the module docstring."""
    if value:
        record[key] = value


def _date(value) -> str | None:
    """Take the date off an ISO timestamp (or pass a bare date through)."""
    if not isinstance(value, str) or len(value) < 10:
        return None
    candidate = value[:10]
    return candidate if re.match(r"^\d{4}-\d{2}-\d{2}$", candidate) else None


def _truncate(text) -> str | None:
    if not isinstance(text, str):
        return None
    text = text.strip()
    if len(text) <= MAX_SUMMARY_GRAPHEMES:
        return text or None
    return text[: MAX_SUMMARY_GRAPHEMES - 1].rstrip() + "…"


def _parties(parties) -> list[dict]:
    out = []
    for party in parties or []:
        name = (party or {}).get("name")
        if not name:
            continue
        entry = {"name": name}
        _set(entry, "identifierType", party.get("identifier_type"))
        _set(entry, "identifier", party.get("identifier"))
        out.append(entry)
    return out


def _industries(codes) -> list[dict]:
    out = []
    for code in codes or []:
        value = (code or {}).get("code")
        if not value:
            continue
        entry = {"code": str(value)}
        _set(entry, "name", code.get("name"))
        out.append(entry)
    return out


def _determination_documents(merger: dict) -> dict[str, str]:
    """Map each phase to the URL of the determination document filed under it."""
    documents: dict[str, str] = {}
    for event in merger.get("events") or []:
        if not event.get("is_determination_event") or not event.get("url"):
            continue
        documents.setdefault(event.get("phase") or "", event["url"])
    return documents


def _determinations(merger: dict) -> list[dict]:
    """Every determination made on the matter, oldest first.

    A referral to phase 2 is a phase 1 determination in its own right, so a
    phase 2 matter carries two. ``accc_determination`` is the register's
    single headline field and duplicates the phase-specific ones wherever
    those exist, so it is only used when neither does - which is every waiver,
    where there are no phases to split.
    """
    documents = _determination_documents(merger)
    out: list[dict] = []

    for phase_key, phase_label, event_phase in (
        ("phase_1", "Phase 1 - initial assessment", "Phase 1"),
        ("phase_2", "Phase 2 - detailed assessment", "Phase 2"),
    ):
        outcome = merger.get(f"{phase_key}_determination")
        if not outcome:
            continue
        entry = {"outcome": outcome, "phase": phase_label}
        _set(entry, "decidedOn", _date(merger.get(f"{phase_key}_determination_date")))
        _set(entry, "documentUrl", documents.get(event_phase))
        out.append(entry)

    if not out and merger.get("accc_determination"):
        entry = {"outcome": merger["accc_determination"]}
        _set(entry, "phase", merger.get("stage"))
        _set(entry, "decidedOn", _date(merger.get("determination_publication_date")))
        _set(entry, "documentUrl", documents.get("Waiver") or documents.get(""))
        out.append(entry)

    # Conditions attach to the clearance itself, which is always the last
    # determination: a matter cleared with conditions at phase 2 was not
    # cleared with conditions when it was referred there.
    if out and merger.get("has_conditions"):
        out[-1]["withConditions"] = True

    return out


def _appeals(merger: dict) -> list[dict]:
    """Tribunal merits review and Federal Court judicial review, in that order."""
    out = []

    appeal = merger.get("appeal") or {}
    if appeal:
        entry = {"forum": "australian-competition-tribunal"}
        _set(entry, "caseNumber", appeal.get("tribunal_number"))
        _set(entry, "caseUrl", appeal.get("tribunal_url"))
        _set(entry, "applicant", appeal.get("appellant"))
        _set(entry, "filedOn", _date(appeal.get("filed_date")))
        _set(entry, "status", appeal.get("status"))
        _set(entry, "outcome", appeal.get("outcome"))
        out.append(entry)

    review = merger.get("judicial_review") or {}
    if review:
        entry = {"forum": "federal-court-of-australia"}
        _set(entry, "caseNumber", review.get("case_number"))
        _set(entry, "caseUrl", review.get("case_url"))
        _set(entry, "applicant", review.get("applicant"))
        _set(entry, "filedOn", _date(review.get("filed_date")))
        out.append(entry)

    return out


def _events(events) -> list[dict]:
    """The timeline, oldest first, capped at the lexicon's declared maximum.

    The cap trims the *oldest* entries if it ever bites, since a matter that
    long has its early procedural steps well behind it. Nothing on the
    register comes close today (the longest timeline is 42 entries).
    """
    out = []
    for event in events or []:
        date = _date(event.get("date"))
        title = event.get("display_title") or event.get("title")
        if not date or not title:
            continue
        entry = {"date": date, "title": title, "kind": event_kind(event)}
        _set(entry, "phase", event.get("phase"))
        _set(entry, "documentUrl", event.get("url"))
        out.append(entry)

    out.sort(key=lambda entry: entry["date"])
    return out[-MAX_EVENTS:]
