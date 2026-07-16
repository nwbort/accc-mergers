import { Link } from 'react-router-dom';
import { mergerPath } from '../utils/slug';

// Shared chip base for the small inline badges (the top-right "New" flag and
// any caller-supplied meta-row chips like "Waiver") laid over a card's style.
export const CHIP_BASE_CLASS = 'inline-flex items-center rounded-md px-2 py-1 leading-none';

// Common body for the dashboard/Phase 2 card grids: an uppercase label row
// (with an optional top-right chip), a title link using the stretched-link
// trick so the whole card is clickable, and a meta row of caller-supplied
// children.
function MergerCardBody({ style, label, chip, mergerId, mergerName, children }) {
  return (
    <>
      {chip ? (
        <div className="flex items-start justify-between gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide">{label}</span>
          <span className={`${CHIP_BASE_CLASS} text-xs font-semibold ${style.chip}`}>
            {chip}
          </span>
        </div>
      ) : (
        <span className="text-xs font-semibold uppercase tracking-wide">{label}</span>
      )}
      <Link
        to={mergerPath(mergerId, mergerName)}
        className={`mt-2 text-sm font-semibold leading-snug hover:underline after:absolute after:inset-0 ${style.text}`}
        aria-label={`View merger details for ${mergerName}`}
      >
        {mergerName}
      </Link>
      <div className={`mt-2 flex flex-wrap items-center gap-2 text-xs ${style.sub}`}>
        {children}
      </div>
    </>
  );
}

export default MergerCardBody;
