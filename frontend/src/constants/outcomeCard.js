/**
 * Outcome -> how a merger list card wears it, after the Android app's
 * MergerCard (ui/Common.kt):
 *
 * - `glyph`: the solid fill and ink of the outcome's shape at the head of the
 *   card (StatusGlyph). The same fills as SOLID_STATUS_COLORS, which are the
 *   app's statusColors.
 * - `tint`: the card itself, that fill at 10% over white, as the app tints
 *   its cards. Light enough that every text colour on the card keeps its
 *   contrast (gray-600 meta text is over 6:1 on the deepest of them).
 *
 * Full class strings are required so Tailwind's scanner keeps them at build
 * time.
 */
import { MERGER_STATUS } from './mergerStatus';
import { resolveStatusDisplay } from '../utils/statusDisplay';

const EMERALD = {
  glyph: 'bg-emerald-700 text-white',
  tint: 'bg-[color-mix(in_srgb,#047857_10%,white)]',
};
const RED = {
  glyph: 'bg-red-700 text-white',
  tint: 'bg-[color-mix(in_srgb,#b91c1c_10%,white)]',
};

export const OUTCOME_CARD_STYLES = {
  [MERGER_STATUS.APPROVED]: EMERALD,
  [MERGER_STATUS.NOT_OPPOSED]: EMERALD,
  [MERGER_STATUS.NOT_APPROVED]: RED,
  [MERGER_STATUS.DECLINED]: RED,
  [MERGER_STATUS.REFERRED_TO_PHASE_2]: {
    glyph: 'bg-amber-400 text-amber-950',
    tint: 'bg-[color-mix(in_srgb,#fbbf24_16%,white)]',
  },
  [MERGER_STATUS.UNDER_ASSESSMENT]: {
    glyph: 'bg-primary text-white',
    tint: 'bg-[color-mix(in_srgb,#335145_10%,white)]',
  },
  [MERGER_STATUS.ASSESSMENT_SUSPENDED]: {
    glyph: 'bg-orange-700 text-white',
    tint: 'bg-[color-mix(in_srgb,#c2410c_10%,white)]',
  },
  [MERGER_STATUS.ASSESSMENT_CEASED]: {
    glyph: 'bg-purple-700 text-white',
    tint: 'bg-[color-mix(in_srgb,#7e22ce_10%,white)]',
  },
};

export const DEFAULT_OUTCOME_CARD_STYLE = {
  glyph: 'bg-gray-600 text-white',
  tint: 'bg-white',
};

export function getOutcomeCardStyle(styleKey) {
  return OUTCOME_CARD_STYLES[styleKey] || DEFAULT_OUTCOME_CARD_STYLE;
}

/** The card tint for a matter, given what StatusBadge would be given. */
export function getOutcomeCardTint(statusInput) {
  return getOutcomeCardStyle(resolveStatusDisplay(statusInput).styleKey).tint;
}
