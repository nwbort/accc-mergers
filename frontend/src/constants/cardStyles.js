/**
 * Solid-colour card treatments keyed by determination or status, used by the
 * dashboard card grids (recent determinations + recently notified mergers).
 *
 * Each entry is a saturated block with text laid directly on top, echoing the
 * Industries treemap cells. `sub` tints secondary text and `chip` styles the
 * inline badges so they sit on the coloured surface. Most use white text; the
 * amber "referred to phase 2" block reads better with dark text. Full class
 * strings are required so Tailwind's scanner keeps them at build time.
 *
 * Every layer here has to clear 4.5:1 against the block it sits on (WCAG
 * 1.4.3), which sets three constraints: the fill is deep enough for white
 * body text, `sub` is a full-opacity tint rather than a faded one (an /80
 * tint blends back toward the fill and loses ~1.3:1), and the chip darkens
 * the fill instead of lightening it — a white/20 wash moves the chip's
 * background toward its own white text.
 */

import { MERGER_STATUS } from './mergerStatus';

const ON_DARK = { text: 'text-white', chip: 'bg-black/20 text-white' };

export const CARD_STYLES = {
  // Determinations
  [MERGER_STATUS.APPROVED]: { bg: 'bg-emerald-700 hover:bg-emerald-800', sub: 'text-emerald-50', ...ON_DARK },
  [MERGER_STATUS.DECLINED]: { bg: 'bg-red-700 hover:bg-red-800', sub: 'text-red-100', ...ON_DARK },
  [MERGER_STATUS.NOT_APPROVED]: { bg: 'bg-red-700 hover:bg-red-800', sub: 'text-red-100', ...ON_DARK },
  [MERGER_STATUS.REFERRED_TO_PHASE_2]: {
    bg: 'bg-amber-400 hover:bg-amber-500',
    text: 'text-amber-950',
    sub: 'text-amber-900',
    chip: 'bg-black/10 text-amber-950',
  },
  [MERGER_STATUS.ASSESSMENT_CEASED]: { bg: 'bg-purple-700 hover:bg-purple-800', sub: 'text-purple-100', ...ON_DARK },

  // Statuses (recently notified mergers)
  [MERGER_STATUS.UNDER_ASSESSMENT]: { bg: 'bg-primary hover:bg-primary-dark', sub: 'text-white/80', ...ON_DARK },
  [MERGER_STATUS.ASSESSMENT_SUSPENDED]: { bg: 'bg-orange-700 hover:bg-orange-800', sub: 'text-orange-100', ...ON_DARK },
  [MERGER_STATUS.ASSESSMENT_COMPLETED]: { bg: 'bg-gray-600 hover:bg-gray-700', sub: 'text-gray-100', ...ON_DARK },
};

export const DEFAULT_CARD_STYLE = { bg: 'bg-gray-600 hover:bg-gray-700', sub: 'text-gray-100', ...ON_DARK };

// Blue ring applied to cards for items the visitor hasn't seen yet (those that
// also show a "New" badge), so recent arrivals stand out from the grid. A ring
// (rather than a border) avoids shifting the card's layout. Full class string
// required so Tailwind's scanner keeps it at build time.
export const NEW_ITEM_BORDER = 'ring-2 ring-blue-500';

// The same fills, without the hover step, for surfaces that colour something
// smaller than a card by outcome: the Phase 2 tracker's outcome split bar and
// its legend dots. They sit on the same page as the cards above, so a result
// has to read as the same green, red or purple in both.
//
// "Approved with conditions" is the one entry with no card of its own — it is
// a display label, since the register publishes a conditional clearance as a
// plain "Approved" and the cards spell the difference out with a chip. The
// split gives it its own segment (at Phase 2 that distinction is the point),
// so it needs a green that is unmistakably not the outright-approval green
// beside it while still reading as a clearance: the accent green the site
// already marks approvals with elsewhere, two steps lighter than the card
// fill. A neighbouring shade (emerald-600) is not a distinction anyone reads,
// and a pale tint reads as a colour of its own rather than as a green.
export const OUTCOME_FILLS = {
  [MERGER_STATUS.APPROVED]: 'bg-emerald-700',
  [MERGER_STATUS.APPROVED_WITH_CONDITIONS]: 'bg-emerald-500',
  [MERGER_STATUS.NOT_OPPOSED]: 'bg-emerald-700',
  [MERGER_STATUS.NOT_APPROVED]: 'bg-red-700',
  [MERGER_STATUS.DECLINED]: 'bg-red-700',
  [MERGER_STATUS.REFERRED_TO_PHASE_2]: 'bg-amber-400',
  [MERGER_STATUS.ASSESSMENT_CEASED]: 'bg-purple-700',
};

export const DEFAULT_OUTCOME_FILL = 'bg-gray-600';

export function getOutcomeFill(determination) {
  return OUTCOME_FILLS[determination] || DEFAULT_OUTCOME_FILL;
}

// Determination takes precedence over status, mirroring StatusBadge.
export function getCardStyle({ determination, status } = {}) {
  return CARD_STYLES[determination] || CARD_STYLES[status] || DEFAULT_CARD_STYLE;
}
