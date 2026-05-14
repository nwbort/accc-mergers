function WaiverBadge({ className = '', compact = false }) {
  if (compact) {
    return (
      // relative z-10 lifts the badge above the after:absolute row-link overlay
      // so the group-hover fires correctly on the badge itself
      <span
        className={`relative z-10 group/waiver inline-flex items-center rounded-md text-xs bg-amber-50 text-amber-700 border border-amber-200/60 shrink-0 ${className}`}
        role="status"
        aria-label="Merger type: Waiver application"
      >
        <span className="font-bold pl-1.5 py-0.5">W</span>
        {/* Outer span controls width only (no padding so w-0 is truly 0) */}
        <span className="w-0 min-w-0 group-hover/waiver:w-[3rem] overflow-hidden transition-[width] duration-200 ease-in-out">
          <span className="font-medium whitespace-nowrap py-0.5 pr-1.5 inline-block">aiver</span>
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
