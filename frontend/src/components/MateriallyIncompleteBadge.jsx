import { FaHourglassHalf } from 'react-icons/fa';
import { GLYPH_BADGE_SHAPE_CLASSES, SOLID_BADGE_SHAPE_CLASSES } from '../constants/mergerStatus';

const ARIA_LABEL = 'Notification materially incomplete: no effective notification date yet';

// Flags a notification the ACCC has held to be materially incomplete under
// s 51ABZ (merger.materially_incomplete). It is a transient state, not a type:
// the flag is set only while the matter waits for the parties to supply what
// is missing, and clears once the ACCC publishes an effective notification
// date (as MN-30003 and MN-95001 did), so the badge goes with it. Grey because
// the matter is on hold rather than heading toward any outcome.
//
// Mirrors WaiverBadge/RefiledBadge: role="img" (never a live region), and
// `solid`/`glyph` forms for sitting beside a solid StatusBadge. gray-600 with
// white text clears 4.5:1.

function MateriallyIncompleteBadge({ className = '', solid = false, glyph = false }) {
  if (glyph) {
    return (
      <span
        className={`inline-flex items-center flex-shrink-0 border ${GLYPH_BADGE_SHAPE_CLASSES} bg-gray-600 text-white border-gray-600 ${className}`}
        role="img"
        aria-label={ARIA_LABEL}
        title="Materially incomplete"
      >
        <FaHourglassHalf className="w-3 h-3" aria-hidden="true" />
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center border ${
        solid
          ? `${SOLID_BADGE_SHAPE_CLASSES} bg-gray-600 text-white border-gray-600`
          : 'px-2 py-1 rounded-md text-xs font-medium leading-none bg-gray-100 text-gray-700 border-gray-300/60'
      } ${className}`}
      role="img"
      aria-label={ARIA_LABEL}
    >
      Materially incomplete
    </span>
  );
}

export default MateriallyIncompleteBadge;
