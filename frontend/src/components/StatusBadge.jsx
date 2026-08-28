import {
  MERGER_STATUS,
  STATUS_COLORS,
  EMPHATIC_STATUS_COLORS,
  DEFAULT_STATUS_STYLE,
} from '../constants/mergerStatus';
import { OUTCOME_ICONS } from '../constants/outcomeIcons';
import { resolveEffectiveDetermination } from '../constants/appeal';

// Determinations take precedence over statuses, so the badge is styled by
// whichever of the two it is actually showing.
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

function StatusBadge({ status, determination, label, hasConditions, appeal }) {
  // A concluded tribunal appeal can replace the ACCC's determination with the
  // one that now stands, plus a suffix noting whether it was confirmed or
  // overturned (mirrors the "· with conditions" treatment). Resolved by the
  // shared helper so this badge and the detail page's outcome banner always
  // agree.
  const { determination: effectiveDetermination, appealSuffix } =
    resolveEffectiveDetermination(determination, appeal);

  // The single outcome this badge is speaking for. Everything below — colour,
  // emphasis, glyph — keys off it, so they cannot end up describing different
  // outcomes. 'Declined' and 'Not approved' share the same red palette (both
  // map to the same STATUS_COLORS entry).
  let styleKey = null;
  if (STYLED_DETERMINATIONS.includes(effectiveDetermination)) {
    styleKey = effectiveDetermination;
  } else if (STYLED_STATUSES.includes(status)) {
    styleKey = status;
  }

  const statusStyle =
    (styleKey && (EMPHATIC_STATUS_COLORS[styleKey] || STATUS_COLORS[styleKey])) ||
    DEFAULT_STATUS_STYLE;

  // A glyph as well as a colour, so an outcome is not distinguished by colour
  // alone (WCAG 1.4.1) and can be picked out of a long list without reading
  // it. Only decided outcomes have one; a live matter shows text only.
  const Icon = styleKey ? OUTCOME_ICONS[styleKey] : null;

  const displayText = label || effectiveDetermination || status;
  const showConditions =
    hasConditions && effectiveDetermination === MERGER_STATUS.APPROVED;

  const ariaLabelBase = effectiveDetermination
    ? `Determination: ${effectiveDetermination}${showConditions ? ', with conditions' : ''}`
    : `Status: ${status}`;
  const ariaLabel = appealSuffix ? `${ariaLabelBase}, ${appealSuffix}` : ariaLabelBase;

  return (
    // role="img" (not role="status", which would turn every badge in a list
    // into its own live region — see WaiverBadge).
    <span
      className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-semibold border ${statusStyle}`}
      role="img"
      aria-label={ariaLabel}
    >
      {Icon && <Icon className="w-3 h-3 mr-1.5 flex-shrink-0" aria-hidden="true" />}
      {displayText}
      {showConditions && (
        <span className="ml-1 font-normal">· with conditions</span>
      )}
      {appealSuffix && (
        <span className="ml-1 font-normal">· {appealSuffix}</span>
      )}
    </span>
  );
}

export default StatusBadge;
