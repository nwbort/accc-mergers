import { FaGavel } from 'react-icons/fa';
import { SOLID_BADGE_SHAPE_CLASSES } from '../constants/mergerStatus';

// "Under appeal" badge shown wherever a merger under review at the Australian
// Competition Tribunal surfaces (detail page header, merger list, Phase 2
// cards). Layered on top of the ACCC outcome rather than replacing it — the
// underlying determination badge stays visible. Mirrors WaiverBadge.
//
// `solid` matches StatusBadge's loud form for sitting directly beside a solid
// StatusBadge — the merger list pairs them as "NOT APPROVED · UNDER APPEAL".
// The shape comes from the same SOLID_BADGE_SHAPE_CLASSES constant StatusBadge
// uses, so the two solid badges can't drift apart in size or weight — only
// the colour here is AppealBadge's own.
function AppealBadge({ className = '', solid = false }) {
  return (
    <span
      className={`inline-flex items-center border ${
        solid
          ? `${SOLID_BADGE_SHAPE_CLASSES} bg-indigo-700 text-white border-indigo-700`
          : 'px-2 py-1 rounded-md text-xs font-medium leading-none bg-indigo-50 text-indigo-700 border-indigo-200/60'
      } ${className}`}
      role="img"
      aria-label="Under appeal at the Australian Competition Tribunal"
    >
      {/* The same glyph, and the same treatment of it, StatusBadge gives a
          determination — so an appeal standing next to an outcome reads as its
          peer rather than as an afterthought pinned beside it. */}
      <FaGavel className="w-3 h-3 mr-1.5 flex-shrink-0" aria-hidden="true" />
      Under appeal
    </span>
  );
}

export default AppealBadge;
