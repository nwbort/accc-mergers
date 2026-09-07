/**
 * Palette for the merger detail page's header card once a matter is decided:
 * the card's title block is filled with the outcome's colour, so the result is
 * the first thing the page says rather than something to hunt for in a badge.
 *
 * These are the same fills the dashboard card grids use for the same outcomes
 * (constants/cardStyles.js), so a result reads as the same colour everywhere on
 * the site. They are kept separate from CARD_STYLES because that table bakes a
 * hover state into `bg` for its clickable cards, which a static header has no
 * use for, and because the header needs three things the cards don't: an accent
 * colour for the card's top rule, a link treatment, and a focus-ring treatment
 * for the controls that now sit on the fill.
 *
 * The contrast rules from cardStyles carry over — every layer has to clear
 * 4.5:1 against the block it sits on (WCAG 1.4.3), which is why the fill is
 * deep enough for white text, `sub` is a full-opacity tint rather than a faded
 * one, and `chip` darkens the fill instead of lightening it (a white/15 wash
 * lands around 4.1:1 and fails). Links are underlined rather than tinted, since
 * on this fill they would otherwise be distinguished from the surrounding text
 * by colour alone (WCAG 1.4.1). The focus ring is white rather than the
 * site-wide primary green, which would sit under the 3:1 a focus indicator
 * needs (WCAG 1.4.11) against these fills.
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
  link: 'text-white underline decoration-white/60 underline-offset-2 hover:decoration-white',
  focus: 'focus-visible:ring-white focus-visible:ring-offset-0',
};

export const OUTCOME_HEADER_STYLES = {
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

export const DEFAULT_OUTCOME_HEADER_STYLE = {
  bg: 'bg-gray-700',
  sub: 'text-gray-100',
  accent: '#374151', // gray-700
  ...ON_DARK,
};

export function getOutcomeHeaderStyle(outcome) {
  return OUTCOME_HEADER_STYLES[outcome] || DEFAULT_OUTCOME_HEADER_STYLE;
}

/**
 * The overlay that marks a header block as contested — a matter whose ACCC
 * decision is currently under review at the Australian Competition Tribunal.
 *
 * Deliberately keyed off the appeal rather than the outcome. A refusal taken
 * to the Tribunal by the parties is the common case, but a third party can
 * just as well appeal a clearance, and both are the same fact about the
 * matter: the result on the banner is not settled. So the outcome keeps the
 * field — red stays red, emerald stays emerald — and the appeal is a stripe
 * laid over it, in the indigo AppealBadge already wears.
 *
 * Contrast is checked on the blend, not assumed. The stripe is indigo-700 at
 * partial alpha composited over the fill, which for every outcome colour lands
 * darker than the fill it covers — emerald 5.5:1 -> 7.3:1, red 6.5:1 -> 8.5:1,
 * purple 7.0:1 -> 7.6:1 against white — so white text on those blocks only
 * ever gains contrast. The gray fallback is the one that goes the other way
 * (10.3:1 -> 9.4:1) and still clears 4.5:1 with room to spare, which is what
 * the test in __tests__/outcomeHeader.test.js pins: every band of every fill
 * over 4.5:1 (WCAG 1.4.3), not that the stripe is always the darker of the two.
 *
 * The stripe is never the only signal that a matter is under appeal: the
 * AppealBadge sits in the same block and says it in words (WCAG 1.4.1).
 */
const APPEAL_STRIPE_COLOR = 'rgba(67, 56, 202, 0.5)'; // indigo-700
const APPEAL_STRIPE_ANGLE = '135deg';
// A pinstripe, not hazard tape: a narrow band on a wide gap keeps the outcome
// colour the field and the appeal a mark laid over it. Equal bands read as a
// second background competing with the h1 sitting on them.
const APPEAL_STRIPE_BAND = 5; // px of stripe
const APPEAL_STRIPE_GAP = 16; // px of untouched fill between bands

const appealStripeImage = (scale = 1) => {
  const gap = APPEAL_STRIPE_GAP * scale;
  const end = gap + APPEAL_STRIPE_BAND * scale;
  return (
    `repeating-linear-gradient(${APPEAL_STRIPE_ANGLE}, transparent 0 ${gap}px, ` +
    `${APPEAL_STRIPE_COLOR} ${gap}px ${end}px)`
  );
};

/**
 * Inline background for the header's title block when a matter is under
 * appeal, replacing the flat `style.bg` class. Returns null when it isn't, so
 * the caller keeps the Tailwind class and no inline style is emitted.
 */
export function getAppealStripeStyle(style) {
  if (!style) return null;
  return {
    backgroundColor: style.accent,
    backgroundImage: appealStripeImage(),
  };
}

/**
 * The matching value for `--card-accent`, so the card's 3px top rule carries
 * the same stripe rather than sitting as a solid bar above a striped block.
 * The pattern is halved: at 3px tall the full-size stripe reads as a smear.
 */
export function getAppealStripeAccent(style) {
  if (!style) return null;
  return `${appealStripeImage(0.5)}, ${style.accent}`;
}
