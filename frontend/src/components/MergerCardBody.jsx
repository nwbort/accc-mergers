import { Link } from 'react-router';
import { mergerPath } from '../utils/slug';
import NewBadge from './NewBadge';

// Shared chip base for the caller-supplied meta-row chips (a tribunal number,
// "Phase 2", "With conditions") laid over a card's style. Flags that are badges
// elsewhere on the site — New, Waiver, Refiled — use the badge components
// instead, so they look the same here as everywhere else.
export const CHIP_BASE_CLASS = 'inline-flex items-center rounded-md px-2 py-1 leading-none';

// Common body for the dashboard/Phase 2 card grids: an uppercase label row
// (with an optional top-right chip), a title link using the stretched-link
// trick so the whole card is clickable, and a meta row of caller-supplied
// children. `isNew` puts a NewBadge top right.
function MergerCardBody({ style, label, isNew = false, mergerId, mergerName, children }) {
  return (
    <>
      {isNew ? (
        <div className="flex items-start justify-between gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide">{label}</span>
          <NewBadge className="flex-shrink-0" />
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
