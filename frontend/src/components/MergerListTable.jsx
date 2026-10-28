import { FaArrowDown, FaStar } from 'react-icons/fa';
import { Link, useNavigate } from 'react-router';
import StatusBadge from './StatusBadge';
import WaiverBadge from './WaiverBadge';
import AppealBadge from './AppealBadge';
import JudicialReviewBadge from './JudicialReviewBadge';
import RefiledBadge from './RefiledBadge';
import { formatDate } from '../utils/dates';
import { mergerPath } from '../utils/slug';
import { CARD } from '../utils/classNames';

const HEADER_CELL = 'px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap';

// A column header that sorts the list by its field. The sort itself lives in
// ?sort=, shared with the select above the list, so the two never disagree.
function SortableHeader({ field, label, sortField, sortDir, onSort, className = '' }) {
  const active = field === sortField;
  return (
    <th
      scope="col"
      className={`${HEADER_CELL} ${className}`}
      aria-sort={active ? (sortDir === 'asc' ? 'ascending' : 'descending') : undefined}
    >
      <button
        type="button"
        onClick={() => onSort(field)}
        className={`inline-flex items-center gap-1.5 uppercase tracking-wider hover:text-gray-700 transition-colors ${
          active ? 'text-gray-700' : ''
        }`}
      >
        {label}
        {active && (
          <FaArrowDown
            className={`h-3 w-3 transition-transform ${sortDir === 'asc' ? 'rotate-180' : ''}`}
            aria-hidden="true"
          />
        )}
      </button>
    </th>
  );
}

// The determination date once decided; until then, when the current phase is
// due to end, in a quieter tone so the column still scans as "decided on".
function DeterminedCell({ merger }) {
  if (merger.determination_publication_date) {
    return formatDate(merger.determination_publication_date);
  }
  if (merger.end_of_determination_period && !merger.status?.toLowerCase().includes('suspended')) {
    return <span className="text-gray-500">Due {formatDate(merger.end_of_determination_period)}</span>;
  }
  return <span className="text-gray-500">—</span>;
}

/**
 * The /mergers compact view: one row per merger, for scanning many at once.
 * The card view stays the default; this is ?view=table.
 */
function MergerListTable({ mergers, selectedIndex, isTracked, sortField, sortDir, onSort }) {
  const navigate = useNavigate();
  const sortProps = { sortField, sortDir, onSort };

  return (
    // Scrolls sideways on its own rather than widening the page, should a
    // long name or narrow screen ever need it.
    <div className={`${CARD} overflow-x-auto`}>
      <table className="min-w-full text-sm">
        <caption className="sr-only">Mergers</caption>
        <thead className="bg-gray-50 text-left border-b border-gray-100">
          <tr>
            <SortableHeader field="name" label="Merger" {...sortProps} />
            <th scope="col" className={HEADER_CELL}>Outcome</th>
            <SortableHeader field="notification" label="Notified" className="hidden sm:table-cell" {...sortProps} />
            <SortableHeader field="determination" label="Determined" className="hidden sm:table-cell" {...sortProps} />
            <th scope="col" className={`${HEADER_CELL} hidden lg:table-cell`}>Stage</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {mergers.map((merger, idx) => {
            const path = mergerPath(merger.merger_id, merger.merger_name);
            const tracked = isTracked(merger.merger_id);
            return (
              <tr
                key={merger.merger_id}
                data-merger-index={idx}
                // The name is the row's link for keyboards and screen
                // readers; clicking anywhere else on the row is a pointer
                // convenience on top of it.
                onClick={(e) => {
                  if (e.target.closest('a, button')) return;
                  navigate(path);
                }}
                className={`align-top cursor-pointer transition-colors hover:bg-gray-50 ${
                  idx === selectedIndex ? 'bg-primary/5' : ''
                }`}
              >
                <td className="px-4 py-3 sm:min-w-[14rem]">
                  <div className="flex items-start gap-1.5">
                    {tracked && (
                      <FaStar className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-primary" aria-label="Tracked" role="img" />
                    )}
                    <div className="min-w-0">
                      <Link to={path} className="font-medium text-gray-900 hover:text-primary transition-colors">
                        {merger.merger_name}
                      </Link>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {merger.merger_id}
                        {/* Phones have room for two columns, so the date rides
                            here instead of in its own. */}
                        <span className="sm:hidden">
                          {' · '}<DeterminedCell merger={merger} />
                        </span>
                      </p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">
                  {/* Phones get symbols only, the worded chips don't fit;
                      their words stay in each symbol's accessible name and
                      tooltip. Only one of the two is ever displayed. */}
                  <div className="flex flex-wrap items-center gap-1 sm:hidden">
                    <StatusBadge
                      status={merger.status}
                      determination={merger.accc_determination}
                      hasConditions={merger.has_conditions}
                      appeal={merger.appeal}
                      glyph
                    />
                    {merger.under_appeal && <AppealBadge glyph />}
                    {merger.under_judicial_review && <JudicialReviewBadge glyph />}
                    {merger.is_waiver && <WaiverBadge glyph />}
                    {merger.is_refiled && <RefiledBadge glyph />}
                  </div>
                  {/* The solid form, as on the cards, so the two views of
                      the same list read the same. */}
                  <div className="hidden sm:flex flex-wrap items-center gap-1.5">
                    <StatusBadge
                      status={merger.status}
                      determination={merger.accc_determination}
                      hasConditions={merger.has_conditions}
                      appeal={merger.appeal}
                      solid
                    />
                    {merger.under_appeal && <AppealBadge solid />}
                    {merger.under_judicial_review && <JudicialReviewBadge solid />}
                    {merger.is_waiver && <WaiverBadge solid />}
                    {merger.is_refiled && <RefiledBadge solid />}
                  </div>
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-gray-700 hidden sm:table-cell">
                  {merger.effective_notification_datetime
                    ? formatDate(merger.effective_notification_datetime)
                    : <span className="text-gray-500">—</span>}
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-gray-700 hidden sm:table-cell">
                  <DeterminedCell merger={merger} />
                </td>
                <td className="px-4 py-3 text-gray-500 hidden lg:table-cell">{merger.stage || '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default MergerListTable;
