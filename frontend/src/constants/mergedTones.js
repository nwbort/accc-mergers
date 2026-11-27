/**
 * How the /merged deck wears Material 3: a card's tonal sheet, and an
 * outcome's glyph tile.
 *
 * The deck is built from the Android app's Material 3 Expressive language, so
 * a card is a tonal container rather than a bordered box, and an outcome is
 * carried by its Material shape as well as its colour — the same shapes the
 * app's StatusGlyph uses (`outcomeShape` in utils/materialShapes.js).
 *
 * Tones are named by the generator (scripts/generate/static_data/outputs/
 * merged.py), which picks one per card. The outcome tints follow the app's
 * MergerCard: the glyph's solid fill at 10% over white (16% for amber, which
 * is pale to begin with), light enough that body text keeps its contrast.
 *
 * Full class strings throughout, so Tailwind's scanner keeps them.
 */
import { FaRegClock } from 'react-icons/fa';
import { MERGER_STATUS } from './mergerStatus';
import { OUTCOME_ICONS } from './outcomeIcons';

/** A card's sheet: its background and the ink on it. */
export const SHEET_TONES = {
  primary: 'bg-m3-primary text-m3-on-primary',
  'primary-container': 'bg-m3-primary-container text-m3-on-primary-container',
  'secondary-container': 'bg-m3-secondary-container text-m3-on-secondary-container',
  'tertiary-container': 'bg-m3-tertiary-container text-m3-on-tertiary-container',
  surface: 'bg-m3-surface-container-high text-m3-on-surface',
  cleared: 'bg-[color-mix(in_srgb,#047857_10%,white)] text-m3-on-surface',
  refused: 'bg-[color-mix(in_srgb,#b91c1c_10%,white)] text-m3-on-surface',
  'phase-2': 'bg-[color-mix(in_srgb,#fbbf24_16%,white)] text-m3-on-surface',
  appeal: 'bg-[color-mix(in_srgb,#4338ca_10%,white)] text-m3-on-surface',
};

export const DEFAULT_SHEET_TONE = SHEET_TONES.surface;

/**
 * An outcome's glyph tile: the solid fill and ink the app's statusColors give
 * it. These are also the site's SOLID_STATUS_COLORS, so an outcome looks the
 * same here, on a merger card and on a phone.
 */
export const GLYPH_TONES = {
  [MERGER_STATUS.APPROVED]: 'bg-emerald-700 text-white',
  [MERGER_STATUS.NOT_OPPOSED]: 'bg-emerald-700 text-white',
  [MERGER_STATUS.APPROVED_WITH_CONDITIONS]: 'bg-emerald-700 text-white',
  [MERGER_STATUS.NOT_APPROVED]: 'bg-red-700 text-white',
  [MERGER_STATUS.DECLINED]: 'bg-red-700 text-white',
  [MERGER_STATUS.REFERRED_TO_PHASE_2]: 'bg-amber-400 text-amber-950',
  [MERGER_STATUS.UNDER_ASSESSMENT]: 'bg-m3-primary text-white',
  [MERGER_STATUS.ASSESSMENT_SUSPENDED]: 'bg-orange-700 text-white',
  [MERGER_STATUS.ASSESSMENT_CEASED]: 'bg-purple-700 text-white',
};

export const DEFAULT_GLYPH_TONE = 'bg-gray-600 text-white';

export function glyphTone(status) {
  return GLYPH_TONES[status] || DEFAULT_GLYPH_TONE;
}

export function sheetTone(tone) {
  return SHEET_TONES[tone] || DEFAULT_SHEET_TONE;
}

/**
 * The glyph inside an outcome's tile. OUTCOME_ICONS covers the decided
 * outcomes; the live states deliberately have none there, because a made-up
 * symbol for "still going" reads as a result. The deck needs something in the
 * tile all the same, so a clock stands in — the same one the Android app's
 * StatusGlyph uses, and its amber fill is what tells a phase 2 referral from
 * an ordinary live review.
 */
// One table rather than a lookup function: the component indexes this
// directly, as StatusBadge does with OUTCOME_ICONS. A helper that *returns* a
// component reads to the linter as one created during render.
export const GLYPH_ICONS = {
  ...OUTCOME_ICONS,
  [MERGER_STATUS.UNDER_ASSESSMENT]: FaRegClock,
  [MERGER_STATUS.REFERRED_TO_PHASE_2]: FaRegClock,
};
