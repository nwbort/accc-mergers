// role="img" rather than role="status": the badge is a static label, and
// role="status" would make every one of them a live region, so a list that
// re-renders (filtering the mergers table, say) announces each badge again.
function WaiverBadge({ className = '' }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium leading-none bg-waiver-pale text-waiver-dark border border-waiver-light/60 ${className}`}
      role="img"
      aria-label="Merger type: Waiver application"
    >
      Waiver
    </span>
  );
}

export default WaiverBadge;
