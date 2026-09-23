"""
Canonical ACCC merger status, determination, and phase labels.

These strings mirror the values published by the ACCC public register and
must match what appears in the generated JSON data consumed by the frontend
(see frontend/src/constants/mergerStatus.js for the JS
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

# Phase keys: substrings of the values that appear in merger['stage'] (the
# register's full labels are "Phase 1 - initial assessment", "Phase 2 -
# detailed assessment", "Public benefit phase" and "Waiver application"), and
# the values of event['phase']. Match a stage against them with stage_phase()
# rather than a bare ``in`` test: the public benefit label is not capitalised
# the way the other three are.
PHASE_1 = 'Phase 1'
PHASE_2 = 'Phase 2'
PUBLIC_BENEFITS = 'Public benefit'
WAIVER = 'Waiver'

PHASES = [PHASE_1, PHASE_2, PUBLIC_BENEFITS, WAIVER]

# The register's full stage labels, where code needs to write one.
PHASE_2_STAGE = 'Phase 2 - detailed assessment'
PUBLIC_BENEFIT_STAGE = 'Public benefit phase'

# Statutory length of each phase, in business days (before extensions). A
# public benefit application is made within 21 calendar days of a Phase 2
# determination that refuses the acquisition or clears it on conditions; the
# ACCC publishes its public benefit assessment by business day 20 and the
# parties have until business day 35 to respond or offer a remedy.
PHASE_2_BUSINESS_DAYS = 90
PUBLIC_BENEFIT_BUSINESS_DAYS = 50
PUBLIC_BENEFIT_ASSESSMENT_BD = 20
PUBLIC_BENEFIT_RESPONSE_BD = 35


def stage_phase(stage: str | None) -> str | None:
    """Return the phase key (one of PHASES) a register stage label names.

    Case-insensitive, since the register writes "Public benefit phase" but
    "Phase 2 - detailed assessment". None for an empty or unrecognised stage.
    """
    lower = (stage or '').lower()
    if not lower:
        return None
    if WAIVER.lower() in lower:
        return WAIVER
    if PUBLIC_BENEFITS.lower() in lower:
        return PUBLIC_BENEFITS
    if PHASE_2.lower() in lower:
        return PHASE_2
    if PHASE_1.lower() in lower:
        return PHASE_1
    return None


def is_public_benefit_stage(stage: str | None) -> bool:
    """True when a register stage label is the public benefit phase."""
    return stage_phase(stage) == PUBLIC_BENEFITS
