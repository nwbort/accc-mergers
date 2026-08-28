/**
 * Palette for the merger detail page's outcome banner — the saturated block
 * that states, in one glance, how a decided matter ended.
 *
 * These are the same fills the dashboard card grids use for the same outcomes
 * (constants/cardStyles.js), so a result reads as the same colour everywhere on
 * the site. They are kept separate from CARD_STYLES because that table bakes a
 * hover state into `bg` for its clickable cards, which a static banner has no
 * use for, and because the banner needs two things the cards don't: an accent
 * colour for the card's top rule and a focus-ring treatment for the link that
 * sits on the fill.
 *
 * The contrast rules from cardStyles carry over — every layer has to clear
 * 4.5:1 against the block it sits on (WCAG 1.4.3), which is why the fill is
 * deep enough for white text, `sub` is a full-opacity tint rather than a faded
 * one, and `chip` darkens the fill instead of lightening it. The focus ring is
 * white rather than the site-wide primary green, which would sit under the 3:1
 * a focus indicator needs (WCAG 1.4.11) against these fills.
 *
 * `accent` is a plain hex because it is fed to the `--card-accent` custom
 * property that repaints `.card-accent`'s top rule (see index.css); the values
 * are the Tailwind shades named alongside them.
 */

import { MERGER_STATUS } from './mergerStatus';

const ON_DARK = {
  text: 'text-white',
  chip: 'bg-black/20 text-white',
  chipHover: 'hover:bg-black/30',
  focus: 'focus-visible:ring-white focus-visible:ring-offset-0',
};

export const OUTCOME_BANNER_STYLES = {
  [MERGER_STATUS.APPROVED]: {
    bg: 'bg-emerald-700',
    sub: 'text-emerald-50',
    accent: '#047857', // emerald-700
    ...ON_DARK,
  },
  [MERGER_STATUS.NOT_OPPOSED]: {
    bg: 'bg-emerald-700',
    sub: 'text-emerald-50',
    accent: '#047857', // emerald-700
    ...ON_DARK,
  },
  [MERGER_STATUS.NOT_APPROVED]: {
    bg: 'bg-red-700',
    sub: 'text-red-100',
    accent: '#b91c1c', // red-700
    ...ON_DARK,
  },
  [MERGER_STATUS.DECLINED]: {
    bg: 'bg-red-700',
    sub: 'text-red-100',
    accent: '#b91c1c', // red-700
    ...ON_DARK,
  },
  [MERGER_STATUS.ASSESSMENT_CEASED]: {
    bg: 'bg-purple-700',
    sub: 'text-purple-100',
    accent: '#7e22ce', // purple-700
    ...ON_DARK,
  },
};

export const DEFAULT_OUTCOME_BANNER_STYLE = {
  bg: 'bg-gray-700',
  sub: 'text-gray-100',
  accent: '#374151', // gray-700
  ...ON_DARK,
};

export function getOutcomeBannerStyle(outcome) {
  return OUTCOME_BANNER_STYLES[outcome] || DEFAULT_OUTCOME_BANNER_STYLE;
}
