/**
 * Palette for the merger detail page's header card: the card's title block is
 * filled with the colour of whatever the matter is carrying — the outcome once
 * it is decided, the status it is sitting at until then — so where a matter
 * stands is the first thing the page says rather than something to hunt for in
 * a badge.
 *
 * There are two registers, and which one a matter gets says whether it is
 * finished:
 *
 *   - **Decided** matters take a deep fill with white text (ON_DARK). The
 *     result is what the reader came for, and the colour is the page's loudest
 *     statement.
 *   - **Live** matters take a pale tint of their status colour with dark text
 *     (ON_LIGHT), close to the white the header used to be. A matter that has
 *     not finished has nothing to announce yet; shouting a provisional status
 *     in the same voice as a determination would tell the reader the wrong
 *     thing, and nine pages in ten are live.
 *
 * Both registers carry the same set of treatments, so the header's structure —
 * the status line, the chips hanging off it — is identical either way. That is
 * what lets "under appeal" read as the same chip in the same place whether the
 * matter under it is decided or still running, instead of needing a badge of
 * its own somewhere else on the page.
 *
 * The deep fills are the ones the dashboard card grids use for the same
 * outcomes (constants/cardStyles.js) and the pale ones are StatusBadge's tints
 * (constants/mergerStatus.js), so a result reads as the same colour everywhere
 * on the site. They are kept separate from both because those tables serve
 * smaller surfaces, and because the header needs three things they don't: an
 * accent colour for the card's top rule, a link treatment, and a focus-ring
 * treatment for the controls that sit on the fill.
 *
 * The contrast rules from cardStyles carry over — every layer has to clear
 * 4.5:1 against the block it sits on (WCAG 1.4.3). On the deep fills that means
 * the fill is dark enough for white text, `sub` is a full-opacity tint rather
 * than a faded one, links are underlined rather than tinted so they aren't
 * distinguished by colour alone (WCAG 1.4.1), and the focus ring is white
 * rather than the site-wide primary green, which would sit under the 3:1 a
 * focus indicator needs (WCAG 1.4.11). On the pale fills the binding constraint
 * is the other way up: `sub` is gray-600, not the gray-500 it would be on
 * white, which lands at 4.47:1 on the under-assessment tint.
 *
 * `accent` is a plain hex because it is fed to the `--card-accent` custom
 * property that repaints `.card-accent`'s top rule (see index.css); the values
 * are the Tailwind shades named alongside them. A pale fill keeps the saturated
 * shade here, so the card is still marked with its status colour in a form you
 * can actually see at 3px.
 */

import { MERGER_STATUS } from './mergerStatus';

// `heading` is the status line's own colour. It is empty on a deep fill, where
// the line inherits the block's white; on a pale one it carries the status
// colour, which is what keeps a quiet header still coloured by where the matter
// stands. `onDark` says which register a style belongs to — the controls sitting
// on the fill and the appeal fade below both need to know.
const ON_DARK = {
  text: 'text-white',
  heading: '',
  link: 'text-white underline decoration-white/60 underline-offset-2 hover:decoration-white',
  focus: 'focus-visible:ring-white focus-visible:ring-offset-0',
  onDark: true,
};

const ON_LIGHT = {
  text: 'text-gray-900',
  sub: 'text-gray-600',
  link: 'text-primary hover:text-primary-dark',
  // The site-wide focus ring is already right on a pale fill.
  focus: '',
  onDark: false,
};

export const OUTCOME_HEADER_STYLES = {
  // Determinations
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

  // Everything a matter can be carrying before it is decided. A phase 2
  // referral is a determination but not an ending, so it belongs here with the
  // statuses: the matter is still running and the header should say so in the
  // same voice.
  [MERGER_STATUS.REFERRED_TO_PHASE_2]: {
    bg: 'bg-amber-50',
    heading: 'text-amber-800',
    accent: '#b45309', // amber-700
    ...ON_LIGHT,
  },
  [MERGER_STATUS.UNDER_ASSESSMENT]: {
    bg: 'bg-primary/5',
    heading: 'text-primary',
    accent: '#335145', // primary
    ...ON_LIGHT,
  },
  [MERGER_STATUS.ASSESSMENT_SUSPENDED]: {
    bg: 'bg-orange-50',
    heading: 'text-orange-800',
    accent: '#c2410c', // orange-700
    ...ON_LIGHT,
  },
};

export const DEFAULT_OUTCOME_HEADER_STYLE = {
  bg: 'bg-gray-700',
  sub: 'text-gray-100',
  accent: '#374151', // gray-700
  ...ON_DARK,
};

/**
 * The header treatment for what a matter is carrying — pass the label from
 * `getHeaderStatus`, which is a determination or a status depending on how far
 * the matter has got. Anything the register throws up that has no entry lands
 * on the neutral default rather than borrowing another outcome's colour.
 */
export function getOutcomeHeaderStyle(outcomeOrStatus) {
  return OUTCOME_HEADER_STYLES[outcomeOrStatus] || DEFAULT_OUTCOME_HEADER_STYLE;
}

/**
 * The treatment that marks a header block as contested — a matter whose ACCC
 * decision is currently under review at the Australian Competition Tribunal.
 *
 * Deliberately keyed off the appeal rather than the outcome. A refusal taken
 * to the Tribunal by the parties is the common case, but a third party can
 * just as well appeal a clearance, and both are the same fact about the
 * matter: the result on the banner is not settled. So the outcome keeps the
 * block — red stays red, emerald stays emerald — and the appeal washes in from
 * the right, in the indigo AppealBadge already wears.
 *
 * Deep fills only. The wash runs to indigo-700, which a pale fill's dark text
 * could not survive, and washing a pale fill to a pale indigo instead would be
 * a change you have to be told about to see. A live matter under appeal says so
 * in the chip on its status line, which is the part that carries the meaning
 * anyway — the fade has never been more than reinforcement (see below).
 *
 * A left-to-right fade rather than a pattern laid over the fill. The outcome
 * holds the left edge, where the result line and the title start, and the
 * indigo arrives at the right edge under the "under appeal" chip — so the
 * gradient runs from what the ACCC decided towards who is now contesting it,
 * and the badge reads as the end of the fade rather than a sticker on it.
 * APPEAL_FADE_START keeps the first third flat so the outcome colour still
 * reads as itself before the wash begins.
 *
 * Contrast is checked across the whole ramp, not just its ends. Both endpoints
 * clear 4.5:1 against white on their own, but a gradient's midpoints are not
 * guaranteed to — interpolating between two dark colours can pass through a
 * lighter one — so the test in __tests__/outcomeHeader.test.js samples every
 * step of every outcome's ramp and pins the minimum over 4.5:1 (WCAG 1.4.3).
 * That is also why the gradient is left in sRGB rather than switched to
 * `in oklab`: the test's own interpolation matches what the browser paints,
 * so the number it checks is the number on screen.
 *
 * The fade is never the only signal that a matter is under appeal: the status
 * line in the same block says it in words (WCAG 1.4.1).
 */
export const APPEAL_FADE_COLOR = '#4338ca'; // indigo-700
const APPEAL_FADE_START = 35; // % of the width the outcome colour holds flat

const appealFadeImage = (style) =>
  `linear-gradient(90deg, ${style.accent} 0%, ${style.accent} ${APPEAL_FADE_START}%, ` +
  `${APPEAL_FADE_COLOR} 100%)`;

/**
 * Inline background for the header's title block when a matter is under
 * appeal, replacing the flat `style.bg` class. Returns null when it isn't, and
 * for the pale register, which doesn't fade — either way the caller keeps the
 * Tailwind class and no inline style is emitted.
 */
export function getAppealFadeStyle(style) {
  if (!style?.onDark) return null;
  return {
    backgroundColor: style.accent,
    backgroundImage: appealFadeImage(style),
  };
}

/**
 * The matching value for `--card-accent`, so the card's 3px top rule runs the
 * same fade instead of sitting as a solid bar above a graded block.
 */
export function getAppealFadeAccent(style) {
  if (!style?.onDark) return null;
  return appealFadeImage(style);
}
