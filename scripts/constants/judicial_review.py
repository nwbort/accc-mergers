"""Federal Court judicial review constants.

An ACCC merger decision can also be challenged in the Federal Court of
Australia, by judicial review: a review of the decision's lawfulness rather
than its merits (which is the Tribunal's job; see :mod:`.tribunal`).
``data/processed/judicial_reviews.json`` holds, per merger, one record per
Federal Court file: a few hand-maintained fields plus a ``portal`` block that
:mod:`scripts.scrape.scrape_federal_court` fills in from the Commonwealth
Courts Portal.

Unlike a tribunal appeal, a review's lifecycle is read off the portal itself:
the court records the date a file is finalised and how it was finalised
("Finalised - Discontinued/Withdrawn"), so ``status``, ``outcome`` and
``concluded_date`` are derived here unless a record sets them by hand. The
outcome labels below must match ``JUDICIAL_REVIEW_OUTCOME_LABELS`` in
``frontend/src/constants/judicialReview.js``.
"""

from scripts.constants.tribunal import APPEAL_STATUS_CONCLUDED, APPEAL_STATUS_CURRENT

# The same two lifecycle values as a tribunal appeal, so every reader that
# already knows "current"/"concluded" reads a review the same way.
STATUS_CURRENT = APPEAL_STATUS_CURRENT
STATUS_CONCLUDED = APPEAL_STATUS_CONCLUDED

# What the court did with the application, once finalised.
OUTCOME_WITHDRAWN = 'withdrawn'    # discontinued by the applicant
OUTCOME_DISMISSED = 'dismissed'    # application dismissed: the ACCC decision stands
OUTCOME_SET_ASIDE = 'set_aside'    # application allowed: the ACCC decision set aside

OUTCOMES = frozenset({OUTCOME_WITHDRAWN, OUTCOME_DISMISSED, OUTCOME_SET_ASIDE})

OUTCOME_LABELS = {
    OUTCOME_WITHDRAWN: 'Review discontinued',
    OUTCOME_DISMISSED: 'Application dismissed',
    OUTCOME_SET_ASIDE: 'ACCC decision set aside',
}

# Words in the portal's "Finalised - ..." listing outcome, mapped to an
# outcome. Checked in order; an outcome the portal words some other way is
# left unset (the review still reads as concluded) until it is set by hand.
_FINALISED_OUTCOME_WORDS = (
    (('discontinued', 'withdrawn'), OUTCOME_WITHDRAWN),
    (('dismissed',), OUTCOME_DISMISSED),
    (('allowed', 'set aside', 'quashed'), OUTCOME_SET_ASIDE),
)

# A listing outcome that ends the file, e.g. "Finalised - Discontinued/Withdrawn".
FINALISED_PREFIX = 'finalised'

# Listing reasons, and the location, that mean the judge dealing with the file
# on the papers rather than a hearing anyone attends ("Administrative Listing",
# or a judgment delivered in "Chambers"). They are left off the upcoming
# hearings.
ADMINISTRATIVE_LISTING_REASONS = frozenset({'administrative listing'})
CHAMBERS_LOCATION = 'chambers'


def review_records(entry) -> list[dict]:
    """The Federal Court files filed against one merger, as a list.

    A bare record is accepted as a list of one, so the original single-record
    shape still loads. The returned dicts are the entry's own objects, so a
    caller may update them in place.
    """
    if isinstance(entry, dict):
        return [entry] if entry else []
    if isinstance(entry, list):
        return [record for record in entry if isinstance(record, dict) and record]
    return []


def listings(record: dict) -> list[dict]:
    """Every court listing on the record's file, across its applications,
    newest first as the portal shows them."""
    portal = record.get('portal') or {}
    out = []
    for app in portal.get('applications') or []:
        out.extend(app.get('events') or [])
    return sorted(out, key=lambda e: (e.get('date') or '', _time_key(e.get('time'))), reverse=True)


def _time_key(value: str | None) -> str:
    """'8:30' -> '08:30', so times sort as text."""
    hours, _, minutes = (value or '').partition(':')
    return f"{hours.zfill(2)}:{minutes}" if minutes else (value or '')


def finalised_date(record: dict) -> str | None:
    """The date the court finalised the file, or None while it is on foot."""
    portal = record.get('portal') or {}
    return (portal.get('file') or {}).get('finalised_date') or None


def outcome_from_listing(text: str | None) -> str | None:
    """The outcome a "Finalised - ..." listing outcome records, or None."""
    lowered = (text or '').lower()
    if not lowered.startswith(FINALISED_PREFIX):
        return None
    for words, outcome in _FINALISED_OUTCOME_WORDS:
        if any(word in lowered for word in words):
            return outcome
    return None


def status(record: dict) -> str:
    """``concluded`` once the court has finalised the file (or the record
    says so by hand), else ``current``."""
    if record.get('status') in (STATUS_CURRENT, STATUS_CONCLUDED):
        return record['status']
    return STATUS_CONCLUDED if finalised_date(record) else STATUS_CURRENT


def outcome(record: dict) -> str | None:
    """The hand-set outcome, else the one the finalising listing records."""
    if record.get('outcome'):
        return record['outcome']
    if status(record) != STATUS_CONCLUDED:
        return None
    for listing in listings(record):
        found = outcome_from_listing(listing.get('outcome'))
        if found:
            return found
    return None


def concluded_date(record: dict) -> str | None:
    """The hand-set concluded date, else the portal's finalised date."""
    if status(record) != STATUS_CONCLUDED:
        return None
    return record.get('concluded_date') or finalised_date(record)


def is_current(record: dict) -> bool:
    return status(record) == STATUS_CURRENT


def is_hearing(listing: dict) -> bool:
    """True for a listing someone attends, as opposed to the judge dealing
    with the file in chambers."""
    reason = (listing.get('reason') or '').strip().lower()
    location = (listing.get('location') or '').strip().lower()
    return reason not in ADMINISTRATIVE_LISTING_REASONS and location != CHAMBERS_LOCATION
