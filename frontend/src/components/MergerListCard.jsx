import { FaStar } from 'react-icons/fa';
import { useNavigate } from 'react-router';
import StatusBadge from './StatusBadge';
import TrackButton from './TrackButton';
import WaiverBadge from './WaiverBadge';
import AppealBadge from './AppealBadge';
import RefiledBadge from './RefiledBadge';
import { formatDate } from '../utils/dates';
import { getBusinessDayProgress } from '../utils/businessDayProgress';
import { getOutcomeRail } from '../constants/outcomeRail';
import { mergerPath } from '../utils/slug';

// Caps how many ANZSIC chips a card shows before folding the rest into a
// "+N more" chip, so a multi-industry deal doesn't grow noticeably taller
// than its neighbours in the list.
const MAX_VISIBLE_INDUSTRY_CHIPS = 3;

/** One merger in the /mergers card view. */
function MergerListCard({ merger, index, selected, tracked, onToggleTracking }) {
  const navigate = useNavigate();
  const path = mergerPath(merger.merger_id, merger.merger_name);
  const businessDayProgress = getBusinessDayProgress(merger);
  const railColor = getOutcomeRail({
    status: merger.status,
    determination: merger.accc_determination,
    appeal: merger.appeal,
  });

  return (
    <div
      data-merger-index={index}
      role="link"
      tabIndex={0}
      aria-label={`View merger details for ${merger.merger_name}`}
      onClick={() => navigate(path)}
      onMouseDown={(e) => { if (e.button === 1) e.preventDefault(); }}
      onAuxClick={(e) => {
        if (e.button === 1) window.open(path, '_blank');
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          navigate(path);
        }
      }}
      className={`relative overflow-hidden bg-white rounded-2xl border shadow-card hover:shadow-card-hover hover:border-gray-200 transition-all duration-200 cursor-pointer ${
        selected ? 'border-primary/40 ring-2 ring-primary/20' : 'border-gray-100'
      }`}
    >
      {/* Outcome rail. Decoration only: the status badge below states
          the same outcome in words, so nothing is carried by colour
          alone. Clipped to the card's radius by overflow-hidden. */}
      <span
        className={`absolute inset-y-0 left-0 w-1.5 ${railColor}`}
        aria-hidden="true"
      />
      <div className="p-5 pl-6">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            {/* The outcome leads the card, above the name, the way it
                leads the detail page. In the top-right corner it sat
                the width of the card away from the matter it belongs
                to and read as chrome next to the Track button. An
                appeal, the waiver flag and the refiled flag all ride
                alongside it in the same solid style — "NOT APPROVED
                · UNDER APPEAL" or "APPROVED · WAIVER · REFILED" —
                rather than as separately-styled badges elsewhere on
                the card. */}
            <div className="flex flex-wrap items-center gap-1.5 mb-2">
              <StatusBadge
                status={merger.status}
                determination={merger.accc_determination}
                hasConditions={merger.has_conditions}
                appeal={merger.appeal}
                solid
              />
              {merger.under_appeal && <AppealBadge solid />}
              {merger.is_waiver && <WaiverBadge solid />}
              {merger.is_refiled && <RefiledBadge solid />}
            </div>
            <div className="flex items-center gap-2">
              {tracked && (
                <FaStar className="h-4 w-4 flex-shrink-0 text-primary" aria-hidden="true" />
              )}
              {/* h2, not h3: the results list sits directly under
                  the page h1, so an h3 would skip a level. min-w-0
                  keeps truncate working now that this row is just
                  the star + name — the other badges all sit beside
                  the outcome badge above so they can't eat into its
                  width. */}
              <h2 className="min-w-0 flex-1 text-base font-semibold text-gray-900 truncate hover:text-primary transition-colors">
                {merger.merger_name}
              </h2>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              {merger.merger_id} · {merger.stage || 'N/A'}
            </p>
          </div>
          {/* The same control the detail page's header carries, so
              tracking looks the same wherever it's offered. */}
          <div className="hidden md:flex items-center gap-2 flex-shrink-0">
            <TrackButton
              active={tracked}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onToggleTracking(merger.merger_id);
              }}
              activeLabel="Tracking"
              inactiveLabel="Track"
              activeAriaLabel="Stop tracking this merger"
              inactiveAriaLabel="Track this merger for updates"
            />
          </div>
        </div>

        <div className={`mt-4 grid gap-4 ${
          businessDayProgress ? 'grid-cols-2 md:grid-cols-3' : 'grid-cols-1 md:grid-cols-2'
        }`}>
          <div className={businessDayProgress ? 'order-1' : ''}>
            <p className="text-xs text-gray-500 mb-0.5">
              {merger.is_waiver ? 'Application date' : 'Notification date'}
            </p>
            <p className="text-sm font-medium text-gray-700">
              {!merger.effective_notification_datetime && merger.status?.toLowerCase().includes('suspended')
                ? 'None - assessment suspended'
                : formatDate(merger.effective_notification_datetime)}
            </p>
          </div>
          {(merger.determination_publication_date || (merger.end_of_determination_period && !merger.status?.toLowerCase().includes('suspended'))) && (
            <div className={businessDayProgress ? 'order-3 md:order-2 col-span-2 md:col-span-1' : ''}>
              <p className="text-xs text-gray-500 mb-0.5">
                {merger.determination_publication_date ? 'Determination date' : 'End of determination period'}
              </p>
              <p className="text-sm font-medium text-gray-700">
                {merger.determination_publication_date
                  ? formatDate(merger.determination_publication_date)
                  : formatDate(merger.end_of_determination_period)}
              </p>
            </div>
          )}
          {businessDayProgress && (
            <div className="order-2 md:order-3">
              <p className="text-xs text-gray-500 mb-0.5">Business days</p>
              <p className={`text-sm font-medium ${
                businessDayProgress.overdue ? 'text-amber-700' : 'text-gray-700'
              }`}>
                {businessDayProgress.overdue
                  ? 'Overdue'
                  : `${businessDayProgress.elapsed}/${businessDayProgress.total}`}
              </p>
            </div>
          )}
        </div>

        {merger.anzsic_codes && merger.anzsic_codes.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {merger.anzsic_codes.slice(0, MAX_VISIBLE_INDUSTRY_CHIPS).map((code) => (
              <span
                key={`${merger.merger_id}-anzsic-${code.code || code.name}`}
                className="inline-flex items-center px-2 py-1 rounded-md text-xs leading-none bg-gray-50 text-gray-500 border border-gray-100"
              >
                {code.name}
              </span>
            ))}
            {/* Capped rather than left to wrap freely — a multi-industry
                deal could otherwise grow a card several lines taller
                than its neighbours in the list. */}
            {merger.anzsic_codes.length > MAX_VISIBLE_INDUSTRY_CHIPS && (
              <span
                className="inline-flex items-center px-2 py-1 rounded-md text-xs leading-none bg-gray-50 text-gray-500 border border-gray-100"
                title={merger.anzsic_codes.slice(MAX_VISIBLE_INDUSTRY_CHIPS).map((code) => code.name).join(', ')}
              >
                +{merger.anzsic_codes.length - MAX_VISIBLE_INDUSTRY_CHIPS} more
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default MergerListCard;
