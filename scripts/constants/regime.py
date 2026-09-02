"""Key dates in Australia's merger notification regime.

Mirrors ``frontend/src/constants/regime.js`` — keep the two in step. The new
regime opened on 1 July 2025, but notifying was optional until 1 January 2026,
and matters filed in between behave differently enough that inferences drawn
from the shape of the caseload don't carry over to them: a thin, self-selected
caseload, filed before the register had any waiver applications to date the
case-number counter against (see :mod:`static_data.prenotification`).
"""

# First day notification became mandatory. Compared against a YYYY-MM-DD prefix.
MANDATORY_REGIME_START = "2026-01-01"


def is_voluntary_period_notification(merger: dict) -> bool:
    """Whether ``merger`` was notified before the mandatory regime began."""
    notified = (
        merger.get("original_notification_datetime")
        or merger.get("effective_notification_datetime")
        or ""
    )
    return bool(notified) and notified[:10] < MANDATORY_REGIME_START
