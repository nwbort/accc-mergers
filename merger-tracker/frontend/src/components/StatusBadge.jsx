import { MERGER_STATUS, STATUS_COLORS, DEFAULT_STATUS_STYLE } from '../constants/mergerStatus';
import { APPEAL_STATUS, APPEAL_OUTCOME_BADGE_SUFFIX } from '../constants/appeal';

function StatusBadge({ status, determination, label, hasConditions, appeal }) {
  // Once a tribunal appeal has concluded, the effective determination — the
  // outcome that now stands — takes over from the ACCC's original one, with a
  // suffix noting whether it was confirmed or overturned (mirrors the
  // "· with conditions" treatment). A current appeal is shown separately via
  // AppealBadge and leaves the ACCC determination untouched here.
  const concludedAppeal =
    appeal && appeal.status === APPEAL_STATUS.CONCLUDED ? appeal : null;
  const effectiveDetermination =
    concludedAppeal?.effective_determination || determination;
  const appealSuffix = concludedAppeal
    ? APPEAL_OUTCOME_BADGE_SUFFIX[concludedAppeal.outcome]
    : null;

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
    <span
      className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-semibold border ${getStatusStyle()}`}
      role="status"
      aria-label={ariaLabel}
    >
      {displayText}
      {showConditions && (
        <span className="ml-1 font-normal opacity-80">· with conditions</span>
      )}
      {appealSuffix && (
        <span className="ml-1 font-normal opacity-80">· {appealSuffix}</span>
      )}
    </span>
  );
}

export default StatusBadge;
