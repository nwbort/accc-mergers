function StatusBadge({ status, determination }) {
  const getStatusStyle = () => {
    if (determination === 'Approved' || determination === 'Not opposed') {
      return 'bg-green-100 text-green-800';
    } else if (determination === 'Declined') {
      return 'bg-red-100 text-red-800';
    } else if (status === 'Under assessment') {
      return 'bg-blue-100 text-blue-800';
    } else if (status === 'Assessment completed') {
      return 'bg-gray-100 text-gray-800';
    }
    return 'bg-gray-100 text-gray-800';
  };

  const displayText = determination || status;

  const ariaLabel = determination
    ? `Determination: ${determination}`
    : `Status: ${status}`;

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusStyle()}`}
      role="status"
      aria-label={ariaLabel}
    >
      {displayText}
    </span>
  );
}

export default StatusBadge;
