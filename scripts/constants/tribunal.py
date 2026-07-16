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
