"""Australian Competition Tribunal appeal constants.

When the ACCC clears or blocks a merger, the decision can be taken to the
Australian Competition Tribunal for limited merits review. Three routes exist:

  * a third party can seek review of a decision to clear a merger;
  * a party to the merger can seek review of a clearance granted only subject
    to conditions; and
  * a party can seek review of a refusal (at Phase 2 or at the public-benefits
    stage).

These ``appeal_type`` values are stored in ``data/processed/tribunal_appeals.json``
and surfaced on the frontend. The human-readable labels below must match the
``APPEAL_TYPE_LABELS`` map in
``merger-tracker/frontend/src/constants/appeal.js``.
"""

# A party to the merger seeking review of a refusal (Phase 2 or public benefits).
PARTY_DENIAL = 'party_denial'
# A party seeking review of a clearance granted only subject to conditions.
PARTY_CONDITIONAL_CLEARANCE = 'party_conditional_clearance'
# A third party seeking review of a decision to clear.
THIRD_PARTY_CLEARANCE = 'third_party_clearance'

APPEAL_TYPES = frozenset({
    PARTY_DENIAL,
    PARTY_CONDITIONAL_CLEARANCE,
    THIRD_PARTY_CLEARANCE,
})

# appeal_type → short human label (kept in sync with the frontend).
APPEAL_TYPE_LABELS = {
    PARTY_DENIAL: 'Appeal against refusal',
    PARTY_CONDITIONAL_CLEARANCE: 'Appeal against conditional clearance',
    THIRD_PARTY_CLEARANCE: 'Third party appeal against clearance',
}

# Appeal lifecycle status. A matter is "current" while it is live before the
# tribunal and "concluded" once the tribunal has decided it, or it has been
# withdrawn/dismissed. Only a *current* appeal makes a merger "under appeal":
# a record (and its documents) can persist here long after the appeal itself
# has finished, so the presence of an appeal never implies a live one.
APPEAL_STATUS_CURRENT = 'current'
APPEAL_STATUS_CONCLUDED = 'concluded'

APPEAL_STATUSES = frozenset({
    APPEAL_STATUS_CURRENT,
    APPEAL_STATUS_CONCLUDED,
})

# Records without an explicit status are treated as current — a concluded
# appeal must be marked so deliberately (usually with an outcome).
DEFAULT_APPEAL_STATUS = APPEAL_STATUS_CURRENT


def is_current_appeal(appeal: dict) -> bool:
    """Return True when the appeal is still live before the tribunal.

    An appeal is current unless it is explicitly marked ``concluded``. Anything
    other than ``concluded`` (including a missing status) is treated as current
    so a freshly-scraped matter is never silently hidden.
    """
    if not appeal:
        return False
    return appeal.get('status', DEFAULT_APPEAL_STATUS) != APPEAL_STATUS_CONCLUDED
