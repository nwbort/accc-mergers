function StatusBadge({ status, determination }) {
  const getStatusStyle = () => {
    if (determination === 'Approved') {
      return 'bg-emerald-50 text-emerald-700 border-emerald-200/60';
    } else if (determination === 'Declined' || determination === 'Not approved') {
      return 'bg-red-50 text-red-700 border-red-200/60';
    } else if (status === 'Under assessment') {
      return 'bg-primary/5 text-primary border-primary/20';
    } else if (status === 'Assessment completed') {
      return 'bg-gray-50 text-gray-600 border-gray-200/60';
    }
    return 'bg-gray-50 text-gray-600 border-gray-200/60';
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
