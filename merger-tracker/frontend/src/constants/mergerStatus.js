/**
 * Canonical ACCC merger status, determination, and phase labels.
 *
 * These strings mirror the values published by the ACCC public register and
 * must match what appears in the generated JSON data pipeline output
 * (see scripts/constants/merger_status.py for the Python counterpart).
 * Renaming any value here would invalidate data in public/data/*.json.
 *
 * Source of truth:
 *   https://www.accc.gov.au/public-registers/mergers-registers
 */

// Values that appear in merger.status and merger.accc_determination.
export const MERGER_STATUS = {
  // merger.status
  UNDER_ASSESSMENT: 'Under assessment',
  ASSESSMENT_SUSPENDED: 'Assessment suspended',
  ASSESSMENT_COMPLETED: 'Assessment completed',

  // merger.accc_determination
  APPROVED: 'Approved',
  NOT_APPROVED: 'Not approved',
  DECLINED: 'Declined',
  NOT_OPPOSED: 'Not opposed',
  REFERRED_TO_PHASE_2: 'Referred to phase 2',
};

// Values that appear in merger.stage.
export const PHASES = {
  PHASE_1: 'Phase 1',
  PHASE_2: 'Phase 2',
  PUBLIC_BENEFITS: 'Public Benefits',
  WAIVER: 'Waiver',
};

// Fallback Tailwind classes for StatusBadge when no specific status matches.
export const DEFAULT_STATUS_STYLE = 'bg-gray-50 text-gray-600 border-gray-200/60';

// StatusBadge: status/determination → Tailwind classes.
// Determinations take precedence over statuses in StatusBadge (see component).
export const STATUS_COLORS = {
  [MERGER_STATUS.APPROVED]: 'bg-emerald-50 text-emerald-700 border-emerald-200/60',
  [MERGER_STATUS.DECLINED]: 'bg-red-50 text-red-700 border-red-200/60',
  [MERGER_STATUS.NOT_APPROVED]: 'bg-red-50 text-red-700 border-red-200/60',
  [MERGER_STATUS.REFERRED_TO_PHASE_2]: 'bg-amber-50 text-amber-700 border-amber-200/60',
  [MERGER_STATUS.UNDER_ASSESSMENT]: 'bg-primary/5 text-primary border-primary/20',
  [MERGER_STATUS.ASSESSMENT_SUSPENDED]: 'bg-orange-50 text-orange-700 border-orange-200/60',
  [MERGER_STATUS.ASSESSMENT_COMPLETED]: DEFAULT_STATUS_STYLE,
};

// Digest.jsx color keys — correspond to the Tailwind color names declared in
// tailwind.config.js (see the `new-merger`, `cleared`, `declined`, `phase-1`,
// `phase-2` extensions under theme.extend.colors).
export const DIGEST_COLOR_KEYS = {
  NEW_MERGER: 'new-merger',
  CLEARED: 'cleared',
  DECLINED: 'declined',
  PHASE_1: 'phase-1',
  PHASE_2: 'phase-2',
};

// Digest.jsx: color key → grouped Tailwind classes used across section headers,
// summary cards, and table rows. Full class names are required so Tailwind's
// scanner can detect them at build time (dynamic interpolation gets purged).
export const DIGEST_COLOR_CLASSES = {
  [DIGEST_COLOR_KEYS.NEW_MERGER]: {
    borderLeft: 'border-l-new-merger',
    borderLight: 'border-new-merger-light/20',
    headerBg: 'from-new-merger-pale/50',
    emptyText: 'text-new-merger/70',
    text: 'text-new-merger',
    hoverText: 'hover:text-new-merger-dark',
    cardFrom: 'from-new-merger-pale',
    cardTo: 'to-new-merger-pale/50',
    cardBorder: 'border-new-merger-light/30',
    groupHoverText: 'group-hover:text-new-merger-dark',
    labelText: 'text-new-merger-dark/80',
  },
  [DIGEST_COLOR_KEYS.CLEARED]: {
    borderLeft: 'border-l-cleared',
    borderLight: 'border-cleared-light/20',
    headerBg: 'from-cleared-pale/50',
    emptyText: 'text-cleared/70',
    text: 'text-cleared',
    hoverText: 'hover:text-cleared-dark',
    cardFrom: 'from-cleared-pale',
    cardTo: 'to-cleared-pale/50',
    cardBorder: 'border-cleared-light/30',
    groupHoverText: 'group-hover:text-cleared-dark',
    labelText: 'text-cleared-dark/80',
  },
  [DIGEST_COLOR_KEYS.DECLINED]: {
    borderLeft: 'border-l-declined',
    borderLight: 'border-declined-light/20',
    headerBg: 'from-declined-pale/50',
    emptyText: 'text-declined/70',
    text: 'text-declined',
    hoverText: 'hover:text-declined-dark',
    cardFrom: 'from-declined-pale',
    cardTo: 'to-declined-pale/50',
    cardBorder: 'border-declined-light/30',
    groupHoverText: 'group-hover:text-declined-dark',
    labelText: 'text-declined-dark/80',
  },
  [DIGEST_COLOR_KEYS.PHASE_1]: {
    borderLeft: 'border-l-phase-1',
    borderLight: 'border-phase-1-light/20',
    headerBg: 'from-phase-1-pale/50',
    emptyText: 'text-phase-1/70',
    text: 'text-phase-1',
    hoverText: 'hover:text-phase-1-dark',
    cardFrom: 'from-phase-1-pale',
    cardTo: 'to-phase-1-pale/50',
    cardBorder: 'border-phase-1-light/30',
    groupHoverText: 'group-hover:text-phase-1-dark',
    labelText: 'text-phase-1-dark/80',
  },
  [DIGEST_COLOR_KEYS.PHASE_2]: {
    borderLeft: 'border-l-phase-2',
    borderLight: 'border-phase-2-light/20',
    headerBg: 'from-phase-2-pale/50',
    emptyText: 'text-phase-2/70',
    text: 'text-phase-2',
    hoverText: 'hover:text-phase-2-dark',
    cardFrom: 'from-phase-2-pale',
    cardTo: 'to-phase-2-pale/50',
    cardBorder: 'border-phase-2-light/30',
    groupHoverText: 'group-hover:text-phase-2-dark',
    labelText: 'text-phase-2-dark/80',
  },
};
