function WaiverBadge({ className = '', compact = false }) {
  if (compact) {
    return (
      <span
        className={`relative z-10 group/waiver inline-flex items-center rounded-md text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200/60 shrink-0 select-none px-1.5 py-0.5 ${className}`}
        role="status"
        aria-label="Merger type: Waiver application"
      >
        <span>W</span>
        {/* No padding here — outer badge handles it, so w-0 is truly zero */}
        <span className="w-0 min-w-0 group-hover/waiver:w-[2rem] overflow-hidden transition-[width] duration-200 ease-in-out">
          <span className="whitespace-nowrap">aiver</span>
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
