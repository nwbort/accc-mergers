/**
 * Solid-colour card treatments keyed by determination or status, used by the
 * dashboard card grids (recent determinations + recently notified mergers).
 *
 * Each entry is a saturated block with text laid directly on top, echoing the
 * Industries treemap cells. `sub` tints secondary text and `chip` styles the
 * inline badges so they sit on the coloured surface. Most use white text; the
 * amber "referred to phase 2" block reads better with dark text. Full class
 * strings are required so Tailwind's scanner keeps them at build time.
 */

import { MERGER_STATUS } from './mergerStatus';

const ON_DARK = { text: 'text-white', chip: 'bg-white/20 text-white' };

export const CARD_STYLES = {
  // Determinations
  [MERGER_STATUS.APPROVED]: { bg: 'bg-emerald-600 hover:bg-emerald-700', sub: 'text-emerald-50/80', ...ON_DARK },
  [MERGER_STATUS.DECLINED]: { bg: 'bg-red-600 hover:bg-red-700', sub: 'text-red-50/80', ...ON_DARK },
  [MERGER_STATUS.NOT_APPROVED]: { bg: 'bg-red-600 hover:bg-red-700', sub: 'text-red-50/80', ...ON_DARK },
  [MERGER_STATUS.REFERRED_TO_PHASE_2]: {
    bg: 'bg-amber-400 hover:bg-amber-500',
    text: 'text-amber-950',
    sub: 'text-amber-900/70',
    chip: 'bg-black/10 text-amber-950',
  },
  [MERGER_STATUS.ASSESSMENT_CEASED]: { bg: 'bg-purple-600 hover:bg-purple-700', sub: 'text-purple-50/80', ...ON_DARK },

  // Statuses (recently notified mergers)
  [MERGER_STATUS.UNDER_ASSESSMENT]: { bg: 'bg-primary hover:bg-primary-dark', sub: 'text-white/70', ...ON_DARK },
  [MERGER_STATUS.ASSESSMENT_SUSPENDED]: { bg: 'bg-orange-500 hover:bg-orange-600', sub: 'text-orange-50/80', ...ON_DARK },
  [MERGER_STATUS.ASSESSMENT_COMPLETED]: { bg: 'bg-gray-500 hover:bg-gray-600', sub: 'text-gray-50/80', ...ON_DARK },
};

export const DEFAULT_CARD_STYLE = { bg: 'bg-gray-500 hover:bg-gray-600', sub: 'text-gray-50/80', ...ON_DARK };

// Blue ring applied to cards for items the visitor hasn't seen yet (those that
// also show a "New" badge), so recent arrivals stand out from the grid. A ring
// (rather than a border) avoids shifting the card's layout. Full class string
// required so Tailwind's scanner keeps it at build time.
export const NEW_ITEM_BORDER = 'ring-2 ring-blue-500';

// Determination takes precedence over status, mirroring StatusBadge.
export function getCardStyle({ determination, status } = {}) {
  return CARD_STYLES[determination] || CARD_STYLES[status] || DEFAULT_CARD_STYLE;
}
