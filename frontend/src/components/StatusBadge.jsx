import { MERGER_STATUS, STATUS_COLORS, DEFAULT_STATUS_STYLE } from '../constants/mergerStatus';
import { resolveEffectiveDetermination } from '../constants/appeal';

function StatusBadge({ status, determination, label, hasConditions, appeal }) {
  // A concluded tribunal appeal can replace the ACCC's determination with the
  // one that now stands, plus a suffix noting whether it was confirmed or
  // overturned (mirrors the "· with conditions" treatment). Resolved by the
  // shared helper so this badge and the detail page's outcome banner always
  // agree.
  const { determination: effectiveDetermination, appealSuffix } =
    resolveEffectiveDetermination(determination, appeal);

  const getStatusStyle = () => {
    // Determinations take precedence over statuses; 'Declined' and 'Not approved'
    // share the same red palette (both map to the same STATUS_COLORS entry).
    if (
      effectiveDetermination === MERGER_STATUS.APPROVED ||
      effectiveDetermination === MERGER_STATUS.DECLINED ||
      effectiveDetermination === MERGER_STATUS.NOT_APPROVED ||
      effectiveDetermination === MERGER_STATUS.REFERRED_TO_PHASE_2 ||
      effectiveDetermination === MERGER_STATUS.ASSESSMENT_CEASED
    ) {
      return STATUS_COLORS[effectiveDetermination];
    }
    if (
      status === MERGER_STATUS.UNDER_ASSESSMENT ||
      status === MERGER_STATUS.ASSESSMENT_SUSPENDED ||
      status === MERGER_STATUS.ASSESSMENT_COMPLETED ||
      status === MERGER_STATUS.ASSESSMENT_CEASED
    ) {
      return STATUS_COLORS[status];
    }
    return DEFAULT_STATUS_STYLE;
  };

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
      className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-semibold border ${getStatusStyle()}`}
      role="img"
      aria-label={ariaLabel}
    >
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
