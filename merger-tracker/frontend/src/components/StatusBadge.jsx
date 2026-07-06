import { MERGER_STATUS, STATUS_COLORS, DEFAULT_STATUS_STYLE } from '../constants/mergerStatus';

function StatusBadge({ status, determination, label, hasConditions }) {
  const getStatusStyle = () => {
    // Determinations take precedence over statuses; 'Declined' and 'Not approved'
    // share the same red palette (both map to the same STATUS_COLORS entry).
    if (
      determination === MERGER_STATUS.APPROVED ||
      determination === MERGER_STATUS.DECLINED ||
      determination === MERGER_STATUS.NOT_APPROVED ||
      determination === MERGER_STATUS.REFERRED_TO_PHASE_2 ||
      determination === MERGER_STATUS.ASSESSMENT_CEASED
    ) {
      return STATUS_COLORS[determination];
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

  const displayText = label || determination || status;
  const showConditions = hasConditions && determination === MERGER_STATUS.APPROVED;

  const ariaLabel = determination
    ? `Determination: ${determination}${showConditions ? ', with conditions' : ''}`
    : `Status: ${status}`;

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
    </span>
  );
}

export default StatusBadge;
