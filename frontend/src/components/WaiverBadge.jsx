import { SOLID_BADGE_SHAPE_CLASSES } from '../constants/mergerStatus';

// role="img" rather than role="status": the badge is a static label, and
// role="status" would make every one of them a live region, so a list that
// re-renders (filtering the mergers table, say) announces each badge again.
//
// `solid` matches StatusBadge's loud form for sitting directly beside a solid
// StatusBadge — the merger list pairs them as "APPROVED · WAIVER". Shape comes
// from the same SOLID_BADGE_SHAPE_CLASSES constant StatusBadge/AppealBadge
// use; only the colour here is WaiverBadge's own. `waiver`'s DEFAULT is the
// same amber-400 Tailwind uses for the referred-to-Phase-2 solid badge, so it
// takes that badge's amber-950 text for the same 4.5:1 contrast reason.
function WaiverBadge({ className = '', solid = false }) {
  return (
    <span
      className={`inline-flex items-center border ${
        solid
          ? `${SOLID_BADGE_SHAPE_CLASSES} bg-waiver text-amber-950 border-waiver`
          : 'px-2 py-1 rounded-md text-xs font-medium leading-none bg-waiver-pale text-waiver-dark border-waiver-light/60'
      } ${className}`}
      role="img"
      aria-label="Merger type: Waiver application"
    >
      Waiver
    </span>
  );
}

export default WaiverBadge;
