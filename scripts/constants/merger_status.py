"""
Canonical ACCC merger status, determination, and phase labels.

These strings mirror the values published by the ACCC public register and
must match what appears in the generated JSON data consumed by the frontend
(see merger-tracker/frontend/src/constants/mergerStatus.js for the JS
counterpart). Renaming any value here would invalidate data in
public/data/*.json.

Source of truth:
  https://www.accc.gov.au/public-registers/mergers-registers
"""

# Values that appear in merger['status'].
UNDER_ASSESSMENT = 'Under assessment'
ASSESSMENT_SUSPENDED = 'Assessment suspended'
ASSESSMENT_COMPLETED = 'Assessment completed'
ASSESSMENT_CEASED = 'Assessment ceased'

# Values that appear in merger['accc_determination'] (and phase-specific
# determinations: phase_1_determination, phase_2_determination, etc.).
APPROVED = 'Approved'
NOT_APPROVED = 'Not approved'
DECLINED = 'Declined'
NOT_OPPOSED = 'Not opposed'
REFERRED_TO_PHASE_2 = 'Referred to phase 2'

# Cleared-vs-blocked split of the determination values above, shared by every
# output that classifies outcomes (stats.py, refiled.py, the weekly digest and
# the frontend's OUTCOME_DOT_COLORS) so the split can't drift between them.
CLEARED_DETERMINATIONS = frozenset({APPROVED, NOT_OPPOSED})
BLOCKED_DETERMINATIONS = frozenset({NOT_APPROVED, DECLINED})

# Display label, not an ACCC-published value: the register records a
# conditional clearance as a plain "Approved" and carries the conditions
# separately (merger['has_conditions'], set by enrichment.detect_has_conditions).
# Used where the two need to read as distinct outcomes — currently stats.json's
# Phase 2 outcome counts. Mirrors the "· with conditions" the frontend's
# StatusBadge appends elsewhere.
APPROVED_WITH_CONDITIONS = 'Approved with conditions'

# Values that appear in merger['stage'].
PHASE_1 = 'Phase 1'
PHASE_2 = 'Phase 2'
PUBLIC_BENEFITS = 'Public Benefits'
WAIVER = 'Waiver'

PHASES = [PHASE_1, PHASE_2, PUBLIC_BENEFITS, WAIVER]
