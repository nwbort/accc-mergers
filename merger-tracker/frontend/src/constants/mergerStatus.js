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
  ASSESSMENT_CEASED: 'Assessment ceased',

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
// Dark variants use a translucent tint + a light (300-level) text colour so the
// badge keeps WCAG AA contrast on dark card surfaces (gray-800/gray-900). The
// brand green (#335145) is too dark to read on a dark surface, so the
// "Under assessment" badge switches to the lighter accent green.
export const DEFAULT_STATUS_STYLE = 'bg-gray-50 text-gray-600 border-gray-200/60 dark:bg-gray-700/40 dark:text-gray-300 dark:border-gray-600/60';

// StatusBadge: status/determination → Tailwind classes.
// Determinations take precedence over statuses in StatusBadge (see component).
export const STATUS_COLORS = {
  [MERGER_STATUS.APPROVED]: 'bg-emerald-50 text-emerald-700 border-emerald-200/60 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/30',
  [MERGER_STATUS.DECLINED]: 'bg-red-50 text-red-700 border-red-200/60 dark:bg-red-500/10 dark:text-red-300 dark:border-red-500/30',
  [MERGER_STATUS.NOT_APPROVED]: 'bg-red-50 text-red-700 border-red-200/60 dark:bg-red-500/10 dark:text-red-300 dark:border-red-500/30',
  [MERGER_STATUS.REFERRED_TO_PHASE_2]: 'bg-amber-50 text-amber-700 border-amber-200/60 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30',
  [MERGER_STATUS.UNDER_ASSESSMENT]: 'bg-primary/5 text-primary border-primary/20 dark:bg-accent/10 dark:text-accent-light dark:border-accent/30',
  [MERGER_STATUS.ASSESSMENT_SUSPENDED]: 'bg-orange-50 text-orange-700 border-orange-200/60 dark:bg-orange-500/10 dark:text-orange-300 dark:border-orange-500/30',
  [MERGER_STATUS.ASSESSMENT_COMPLETED]: DEFAULT_STATUS_STYLE,
  [MERGER_STATUS.ASSESSMENT_CEASED]: 'bg-purple-50 text-purple-700 border-purple-200/60 dark:bg-purple-500/10 dark:text-purple-300 dark:border-purple-500/30',
};

// Digest.jsx color keys — correspond to the Tailwind color names declared in
// tailwind.config.js (see the `new-merger`, `cleared`, `declined`, `phase-1`,
// `phase-2` extensions under theme.extend.colors).
export const DIGEST_COLOR_KEYS = {
  NEW_MERGER: 'new-merger',
  CLEARED: 'cleared',
  DECLINED: 'declined',
  CEASED: 'ceased',
  PHASE_2_REFERRAL: 'phase-2-referral',
  PHASE_1: 'phase-1',
  PHASE_2: 'phase-2',
};

// Digest.jsx: color key → grouped Tailwind classes used across section headers,
// summary cards, and table rows. Full class names are required so Tailwind's
// scanner can detect them at build time (dynamic interpolation gets purged).
export const DIGEST_COLOR_CLASSES = {
  [DIGEST_COLOR_KEYS.NEW_MERGER]: {
    borderLeft: 'border-l-new-merger',
    borderLight: 'border-new-merger-light/20 dark:border-new-merger-light/10',
    headerBg: 'from-new-merger-pale/50 dark:from-new-merger-dark/25',
    emptyText: 'text-new-merger/70 dark:text-new-merger-light/70',
    text: 'text-new-merger dark:text-new-merger-light',
    hoverText: 'hover:text-new-merger-dark dark:hover:text-new-merger-pale',
    cardFrom: 'from-new-merger-pale dark:from-new-merger-dark/25',
    cardTo: 'to-new-merger-pale/50 dark:to-new-merger-dark/10',
    cardBorder: 'border-new-merger-light/30 dark:border-new-merger-light/20',
    groupHoverText: 'group-hover:text-new-merger-dark dark:group-hover:text-new-merger-pale',
    labelText: 'text-new-merger-dark/80 dark:text-new-merger-light/80',
  },
  [DIGEST_COLOR_KEYS.CLEARED]: {
    borderLeft: 'border-l-cleared',
    borderLight: 'border-cleared-light/20 dark:border-cleared-light/10',
    headerBg: 'from-cleared-pale/50 dark:from-cleared-dark/25',
    emptyText: 'text-cleared/70 dark:text-cleared-light/70',
    text: 'text-cleared dark:text-cleared-light',
    hoverText: 'hover:text-cleared-dark dark:hover:text-cleared-pale',
    cardFrom: 'from-cleared-pale dark:from-cleared-dark/25',
    cardTo: 'to-cleared-pale/50 dark:to-cleared-dark/10',
    cardBorder: 'border-cleared-light/30 dark:border-cleared-light/20',
    groupHoverText: 'group-hover:text-cleared-dark dark:group-hover:text-cleared-pale',
    labelText: 'text-cleared-dark/80 dark:text-cleared-light/80',
  },
  [DIGEST_COLOR_KEYS.DECLINED]: {
    borderLeft: 'border-l-declined',
    borderLight: 'border-declined-light/20 dark:border-declined-light/10',
    headerBg: 'from-declined-pale/50 dark:from-declined-dark/25',
    emptyText: 'text-declined/70 dark:text-declined-light/70',
    text: 'text-declined dark:text-declined-light',
    hoverText: 'hover:text-declined-dark dark:hover:text-declined-pale',
    cardFrom: 'from-declined-pale dark:from-declined-dark/25',
    cardTo: 'to-declined-pale/50 dark:to-declined-dark/10',
    cardBorder: 'border-declined-light/30 dark:border-declined-light/20',
    groupHoverText: 'group-hover:text-declined-dark dark:group-hover:text-declined-pale',
    labelText: 'text-declined-dark/80 dark:text-declined-light/80',
  },
  [DIGEST_COLOR_KEYS.CEASED]: {
    borderLeft: 'border-l-ceased',
    borderLight: 'border-ceased-light/20 dark:border-ceased-light/10',
    headerBg: 'from-ceased-pale/50 dark:from-ceased-dark/25',
    emptyText: 'text-ceased/70 dark:text-ceased-light/70',
    text: 'text-ceased dark:text-ceased-light',
    hoverText: 'hover:text-ceased-dark dark:hover:text-ceased-pale',
    cardFrom: 'from-ceased-pale dark:from-ceased-dark/25',
    cardTo: 'to-ceased-pale/50 dark:to-ceased-dark/10',
    cardBorder: 'border-ceased-light/30 dark:border-ceased-light/20',
    groupHoverText: 'group-hover:text-ceased-dark dark:group-hover:text-ceased-pale',
    labelText: 'text-ceased-dark/80 dark:text-ceased-light/80',
  },
  [DIGEST_COLOR_KEYS.PHASE_2_REFERRAL]: {
    borderLeft: 'border-l-phase-2-referral',
    borderLight: 'border-phase-2-referral-light/20 dark:border-phase-2-referral-light/10',
    headerBg: 'from-phase-2-referral-pale/50 dark:from-phase-2-referral-dark/25',
    emptyText: 'text-phase-2-referral/70 dark:text-phase-2-referral-light/70',
    text: 'text-phase-2-referral dark:text-phase-2-referral-light',
    hoverText: 'hover:text-phase-2-referral-dark dark:hover:text-phase-2-referral-pale',
    cardFrom: 'from-phase-2-referral-pale dark:from-phase-2-referral-dark/25',
    cardTo: 'to-phase-2-referral-pale/50 dark:to-phase-2-referral-dark/10',
    cardBorder: 'border-phase-2-referral-light/30 dark:border-phase-2-referral-light/20',
    groupHoverText: 'group-hover:text-phase-2-referral-dark dark:group-hover:text-phase-2-referral-pale',
    labelText: 'text-phase-2-referral-dark/80 dark:text-phase-2-referral-light/80',
  },
  [DIGEST_COLOR_KEYS.PHASE_1]: {
    borderLeft: 'border-l-phase-1',
    borderLight: 'border-phase-1-light/20 dark:border-phase-1-light/10',
    headerBg: 'from-phase-1-pale/50 dark:from-phase-1-dark/25',
    emptyText: 'text-phase-1/70 dark:text-phase-1-light/70',
    text: 'text-phase-1 dark:text-phase-1-light',
    hoverText: 'hover:text-phase-1-dark dark:hover:text-phase-1-pale',
    cardFrom: 'from-phase-1-pale dark:from-phase-1-dark/25',
    cardTo: 'to-phase-1-pale/50 dark:to-phase-1-dark/10',
    cardBorder: 'border-phase-1-light/30 dark:border-phase-1-light/20',
    groupHoverText: 'group-hover:text-phase-1-dark dark:group-hover:text-phase-1-pale',
    labelText: 'text-phase-1-dark/80 dark:text-phase-1-light/80',
  },
  [DIGEST_COLOR_KEYS.PHASE_2]: {
    borderLeft: 'border-l-phase-2',
    borderLight: 'border-phase-2-light/20 dark:border-phase-2-light/10',
    headerBg: 'from-phase-2-pale/50 dark:from-phase-2-dark/25',
    emptyText: 'text-phase-2/70 dark:text-phase-2-light/70',
    text: 'text-phase-2 dark:text-phase-2-light',
    hoverText: 'hover:text-phase-2-dark dark:hover:text-phase-2-pale',
    cardFrom: 'from-phase-2-pale dark:from-phase-2-dark/25',
    cardTo: 'to-phase-2-pale/50 dark:to-phase-2-dark/10',
    cardBorder: 'border-phase-2-light/30 dark:border-phase-2-light/20',
    groupHoverText: 'group-hover:text-phase-2-dark dark:group-hover:text-phase-2-pale',
    labelText: 'text-phase-2-dark/80 dark:text-phase-2-light/80',
  },
};
