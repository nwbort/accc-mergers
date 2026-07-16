function WaiverBadge({ className = '' }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium leading-none bg-waiver-pale text-waiver-dark border border-waiver-light/60 ${className}`}
      role="status"
      aria-label="Merger type: Waiver application"
    >
      Waiver
    </span>
  );
}

export default WaiverBadge;
