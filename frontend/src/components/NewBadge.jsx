import { SOLID_BADGE_SHAPE_CLASSES } from '../constants/mergerStatus';

// Flags a dashboard card the visitor hasn't seen yet. Solid, in the same shape
// as every other badge's solid form, and in the blue of the ring the card
// wears for the same reason (NEW_ITEM_BORDER), so the two read as one signal.
function NewBadge({ className = '' }) {
  return (
    <span
      className={`inline-flex items-center border ${SOLID_BADGE_SHAPE_CLASSES} bg-blue-700 text-white border-blue-700 ${className}`}
      role="img"
      aria-label="New item since last visit"
    >
      New
    </span>
  );
}

export default NewBadge;
