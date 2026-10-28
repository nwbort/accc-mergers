import { FaBalanceScale } from 'react-icons/fa';
import { GLYPH_BADGE_SHAPE_CLASSES, SOLID_BADGE_SHAPE_CLASSES } from '../constants/mergerStatus';
import { UNDER_JUDICIAL_REVIEW_LABEL } from '../constants/judicialReview';

const ARIA_LABEL = 'Under judicial review in the Federal Court';

// "Under judicial review" badge: the Federal Court twin of AppealBadge, shown
// wherever a merger under a live judicial review surfaces beside its outcome.
// The same indigo, since both say the ACCC's decision is being contested and
// the detail page washes its header the same colour for either. The balance
// scale is the review's own glyph, as the gavel is the appeal's.

function JudicialReviewBadge({ className = '', solid = false, glyph = false }) {
  // `glyph`: the solid colours as a symbol-only square, for the merger table
  // at phone width. The words stay in the accessible name and the tooltip.
  if (glyph) {
    return (
      <span
        className={`inline-flex items-center flex-shrink-0 border ${GLYPH_BADGE_SHAPE_CLASSES} bg-indigo-700 text-white border-indigo-700 ${className}`}
        role="img"
        aria-label={ARIA_LABEL}
        title={UNDER_JUDICIAL_REVIEW_LABEL}
      >
        <FaBalanceScale className="w-3 h-3" aria-hidden="true" />
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center border ${
        solid
          ? `${SOLID_BADGE_SHAPE_CLASSES} bg-indigo-700 text-white border-indigo-700`
          : 'px-2 py-1 rounded-md text-xs font-medium leading-none bg-indigo-50 text-indigo-700 border-indigo-200/60'
      } ${className}`}
      role="img"
      aria-label={ARIA_LABEL}
    >
      <FaBalanceScale className="w-3 h-3 mr-1.5 flex-shrink-0" aria-hidden="true" />
      {UNDER_JUDICIAL_REVIEW_LABEL}
    </span>
  );
}

export default JudicialReviewBadge;
