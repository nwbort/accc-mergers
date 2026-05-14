function WaiverBadge({ className = '', compact = false }) {
  if (compact) {
    return (
      <span className="relative group/waiver inline-flex items-center shrink-0">
        <span
          className={`inline-flex items-center px-1.5 py-0.5 rounded-md text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200/60 ${className}`}
          role="status"
          aria-label="Merger type: Waiver application"
        >
          W
        </span>
        <span className="absolute left-0 top-0 z-10 pointer-events-none whitespace-nowrap opacity-0 group-hover/waiver:opacity-100 transition-opacity duration-150 inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200/60 shadow-sm">
          Waiver
        </span>
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200/60 ${className}`}
      role="status"
      aria-label="Merger type: Waiver application"
    >
      Waiver
    </span>
  );
}

export default WaiverBadge;
