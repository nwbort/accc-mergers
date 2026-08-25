// "Under appeal" badge shown wherever a merger under review at the Australian
// Competition Tribunal surfaces (detail page header, merger list, Phase 2
// cards, timeline). Layered on top of the ACCC outcome rather than replacing
// it — the underlying determination badge stays visible. Mirrors WaiverBadge.
function AppealBadge({ className = '' }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium leading-none bg-indigo-50 text-indigo-700 border border-indigo-200/60 ${className}`}
      role="img"
      aria-label="Under appeal at the Australian Competition Tribunal"
    >
      Under appeal
    </span>
  );
}

export default AppealBadge;
