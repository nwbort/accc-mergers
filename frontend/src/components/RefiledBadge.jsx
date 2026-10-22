import { FaRedo } from 'react-icons/fa';
import { GLYPH_BADGE_SHAPE_CLASSES, SOLID_BADGE_SHAPE_CLASSES } from '../constants/mergerStatus';

const ARIA_LABEL = 'Subsequently refiled as a separate matter';

// Flags a matter (waiver or notification) that was later re-filed as a
// separate matter — e.g. a declined waiver re-notified, or a ceased
// assessment re-filed under a new merger ID. Mirrors WaiverBadge/AppealBadge;
// colour matches the amber "related merger" link on the detail page.
//
// `solid` matches StatusBadge's loud form for sitting directly beside a solid
// StatusBadge — the merger list pairs them as "APPROVED · WAIVER · REFILED".
// Shape comes from the same SOLID_BADGE_SHAPE_CLASSES constant
// StatusBadge/WaiverBadge/AppealBadge use; only the colour here is
// RefiledBadge's own.

function RefiledBadge({ className = '', solid = false, glyph = false }) {
  // `glyph`: the solid colours as a symbol-only square, for the merger table
  // at phone width. The words stay in the accessible name and the tooltip.
  if (glyph) {
    return (
      <span
        className={`inline-flex items-center flex-shrink-0 border ${GLYPH_BADGE_SHAPE_CLASSES} bg-amber-700 text-white border-amber-700 ${className}`}
        role="img"
        aria-label={ARIA_LABEL}
        title="Refiled"
      >
        <FaRedo className="w-3 h-3" aria-hidden="true" />
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center border ${
        solid
          ? `${SOLID_BADGE_SHAPE_CLASSES} bg-amber-700 text-white border-amber-700`
          : 'px-2 py-1 rounded-md text-xs font-medium leading-none bg-amber-50 text-amber-700 border-amber-200/60'
      } ${className}`}
      role="img"
      aria-label={ARIA_LABEL}
    >
      Refiled
    </span>
  );
}

export default RefiledBadge;
