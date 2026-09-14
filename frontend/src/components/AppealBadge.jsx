// "Under appeal" badge shown wherever a merger under review at the Australian
// Competition Tribunal surfaces (detail page header, merger list, Phase 2
// cards, timeline). Layered on top of the ACCC outcome rather than replacing
// it — the underlying determination badge stays visible. Mirrors WaiverBadge.
//
// `solid` matches StatusBadge's loud form (filled, small-caps) for sitting
// directly beside a solid StatusBadge — the merger list pairs them as
// "NOT APPROVED · UNDER APPEAL" — rather than the quiet tint used elsewhere.
function AppealBadge({ className = '', solid = false }) {
  return (
    <span
      className={`inline-flex items-center border ${
        solid
          ? 'px-2 py-1 rounded-md text-[11px] font-bold uppercase tracking-widest bg-indigo-700 text-white border-indigo-700'
          : 'px-2 py-1 rounded-md text-xs font-medium leading-none bg-indigo-50 text-indigo-700 border-indigo-200/60'
      } ${className}`}
      role="img"
      aria-label="Under appeal at the Australian Competition Tribunal"
    >
      Under appeal
    </span>
  );
}

export default AppealBadge;
