/**
 * Chart colour palette shared by Analysis, Dashboard, and Extensions.
 *
 * CHART_PALETTE holds the named brand colours (plus rgba "Light" variants)
 * used to build chart.js datasets on Analysis/Dashboard. THEME_HEXES holds
 * the hex values that mirror tailwind.config.js theme colors, for contexts
 * (inline styles) that can't reference Tailwind classes directly.
 */
import { MERGER_STATUS } from './mergerStatus';

export const CHART_PALETTE = {
  primary: '#335145',
  primaryLight: 'rgba(51, 81, 69, 0.15)',
  accent: '#e07a5f',
  accentLight: 'rgba(224, 122, 95, 0.15)',
  teal: '#6b8f7f',
  tealLight: 'rgba(107, 143, 127, 0.15)',
  sage: '#8cafa0',
};

// Fallback order for chart segments whose label has no explicit colour
// mapping below (e.g. an unrecognised determination).
export const CHART_PALETTE_ORDER = [
  CHART_PALETTE.primary,
  CHART_PALETTE.accent,
  CHART_PALETTE.teal,
  CHART_PALETTE.sage,
];

// merger.accc_determination -> chart colour, so "Approved" is always the
// primary green regardless of key order in the underlying stats object.
export const DETERMINATION_COLORS = {
  [MERGER_STATUS.APPROVED]: CHART_PALETTE.primary,
  [MERGER_STATUS.NOT_APPROVED]: CHART_PALETTE.accent,
  [MERGER_STATUS.DECLINED]: CHART_PALETTE.accent,
  [MERGER_STATUS.NOT_OPPOSED]: CHART_PALETTE.teal,
  [MERGER_STATUS.REFERRED_TO_PHASE_2]: CHART_PALETTE.sage,
};

// Hex values mirroring tailwind.config.js theme colors (primary, phase-2,
// phase-2-referral), for use where a Tailwind class isn't applicable.
export const THEME_HEXES = {
  primary: '#335145',
  phase2: '#52489c',
  phase2Referral: '#d97706',
};
