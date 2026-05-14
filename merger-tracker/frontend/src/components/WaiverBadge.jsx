function WaiverBadge({ className = '', compact = false }) {
  if (compact) {
    return (
      <span
        className={`group/waiver inline-flex items-center overflow-hidden rounded-md text-xs bg-amber-50 text-amber-700 border border-amber-200/60 shrink-0 ${className}`}
        role="status"
        aria-label="Merger type: Waiver application"
      >
        <span className="font-bold pl-1.5 py-0.5">W</span>
        <span className="font-medium whitespace-nowrap overflow-hidden max-w-0 group-hover/waiver:max-w-[2.5rem] py-0.5 pr-0 group-hover/waiver:pr-1.5 transition-all duration-200 ease-out">aiver</span>
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
