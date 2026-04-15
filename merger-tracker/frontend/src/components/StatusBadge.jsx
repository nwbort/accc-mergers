import { MERGER_STATUS, STATUS_COLORS, DEFAULT_STATUS_STYLE } from '../constants/mergerStatus';

function StatusBadge({ status, determination }) {
  const getStatusStyle = () => {
    // Determinations take precedence over statuses; 'Declined' and 'Not approved'
    // share the same red palette (both map to the same STATUS_COLORS entry).
    if (
      determination === MERGER_STATUS.APPROVED ||
      determination === MERGER_STATUS.DECLINED ||
      determination === MERGER_STATUS.NOT_APPROVED ||
      determination === MERGER_STATUS.REFERRED_TO_PHASE_2
    ) {
      return STATUS_COLORS[determination];
    }
    if (
      status === MERGER_STATUS.UNDER_ASSESSMENT ||
      status === MERGER_STATUS.ASSESSMENT_SUSPENDED ||
      status === MERGER_STATUS.ASSESSMENT_COMPLETED
    ) {
      return STATUS_COLORS[status];
    }
    return DEFAULT_STATUS_STYLE;
  };

  const displayText = determination || status;

  const ariaLabel = determination
    ? `Determination: ${determination}`
    : `Status: ${status}`;

  return (
    <span
      className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-semibold border ${getStatusStyle()}`}
      role="status"
      aria-label={ariaLabel}
    >
      {displayText}
    </span>
  );
}

export default StatusBadge;
