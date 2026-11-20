/**
 * Which outcome a matter's badge or glyph speaks for, and how it reads.
 *
 * Shared by StatusBadge and StatusGlyph so the merger list's glyph and every
 * badge on the site resolve a matter the same way. Determinations take
 * precedence over statuses, and a concluded tribunal appeal can replace the
 * ACCC's determination with the one that now stands
 * (resolveEffectiveDetermination), with a suffix saying how.
 */
import { MERGER_STATUS } from '../constants/mergerStatus';
import { resolveEffectiveDetermination } from '../constants/appeal';

const STYLED_DETERMINATIONS = [
  MERGER_STATUS.APPROVED,
  MERGER_STATUS.DECLINED,
  MERGER_STATUS.NOT_APPROVED,
  MERGER_STATUS.REFERRED_TO_PHASE_2,
  MERGER_STATUS.ASSESSMENT_CEASED,
];

const STYLED_STATUSES = [
  MERGER_STATUS.UNDER_ASSESSMENT,
  MERGER_STATUS.ASSESSMENT_SUSPENDED,
  MERGER_STATUS.ASSESSMENT_COMPLETED,
  MERGER_STATUS.ASSESSMENT_CEASED,
];

/**
 * `styleKey` is the one outcome the colour, glyph and shape key off (null when
 * the matter carries nothing styled); `displayText` the words; and
 * `ariaLabel` the accessible name a badge or glyph gives it.
 */
export function resolveStatusDisplay({ status, determination, label, hasConditions, appeal }) {
  const { determination: effectiveDetermination, appealSuffix } =
    resolveEffectiveDetermination(determination, appeal);

  let styleKey = null;
  if (STYLED_DETERMINATIONS.includes(effectiveDetermination)) {
    styleKey = effectiveDetermination;
  } else if (STYLED_STATUSES.includes(status)) {
    styleKey = status;
  }

  const displayText = label || effectiveDetermination || status;
  const showConditions = Boolean(hasConditions) && effectiveDetermination === MERGER_STATUS.APPROVED;

  const ariaLabelBase = effectiveDetermination
    ? `Determination: ${effectiveDetermination}${showConditions ? ', with conditions' : ''}`
    : `Status: ${status}`;
  const ariaLabel = appealSuffix ? `${ariaLabelBase}, ${appealSuffix}` : ariaLabelBase;

  return { styleKey, effectiveDetermination, displayText, showConditions, appealSuffix, ariaLabel };
}
