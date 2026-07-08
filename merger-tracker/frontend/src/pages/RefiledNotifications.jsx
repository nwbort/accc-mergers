import { Link } from 'react-router-dom';
import { differenceInCalendarDays, parseISO, isValid } from 'date-fns';
import { FaArrowRightArrowLeft, FaHourglassHalf, FaCalendarDays } from 'react-icons/fa6';
import LoadingSpinner from '../components/LoadingSpinner';
import StatusBadge from '../components/StatusBadge';
import StatCard from '../components/StatCard';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { mergerPath } from '../utils/slug';
import { formatDateMedium, calculateDuration } from '../utils/dates';

// Position of `date` along the waiver-filed -> track-end axis, clamped to
// [0, 100] so a milestone landing outside the span (bad data) still renders
// inside the bar rather than breaking layout. Mirrors Phase2Timeline.
function percentAlong(dateStr, startStr, endStr) {
  if (!dateStr || !startStr || !endStr) return null;
  const date = parseISO(dateStr);
  const start = parseISO(startStr);
  const end = parseISO(endStr);
  if (!isValid(date) || !isValid(start) || !isValid(end)) return null;
  const total = differenceInCalendarDays(end, start);
  if (total <= 0) return null;
  const elapsed = differenceInCalendarDays(date, start);
  return Math.min(100, Math.max(0, (elapsed / total) * 100));
}

function median(values) {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0 ? sorted[mid] : Math.round((sorted[mid - 1] + sorted[mid]) / 2);
}

const ABOVE_LINE = 'absolute bottom-1/2 mb-2';
const BELOW_LINE = 'absolute top-1/2 mt-2';

// The "days to re-file" pill sits centred between the declined and re-filed
// dots, clamped to stay inside the track on narrow screens — the same
// technique Phase2Timeline uses for its NOCC label.
const GAP_HALF = '1.75rem';

function RefiledCard({ pair, showOutcome }) {
  const start = pair.waiver_filed_date;
  const end = showOutcome ? pair.notification_determination_date : new Date().toISOString();
  const declinedPercent = percentAlong(pair.waiver_declined_date, start, end);
  const filedPercent = percentAlong(pair.notification_filed_date, start, end);
  const daysToRefile = calculateDuration(pair.waiver_declined_date, pair.notification_filed_date);
  const gapPercent = declinedPercent !== null && filedPercent !== null
    ? (declinedPercent + filedPercent) / 2
    : null;
  const gapLabelStyle = gapPercent === null ? null : {
    left: `clamp(${GAP_HALF}, ${gapPercent}%, calc(100% - ${GAP_HALF}))`,
    transform: 'translate(-50%, -50%)',
  };

  return (
    <li className="py-4 first:pt-0 last:pb-0">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="min-w-0">
          <Link
            to={mergerPath(pair.notification_id, pair.notification_name)}
            className="block text-sm font-semibold text-gray-900 hover:text-primary transition-colors truncate"
          >
            {pair.notification_name}
          </Link>
          <p className="text-xs text-gray-500 mt-0.5">
            <Link to={mergerPath(pair.waiver_id, pair.waiver_name)} className="hover:text-primary transition-colors">
              {pair.waiver_id}
            </Link>
            {' → '}
            {pair.notification_id}
          </p>
        </div>
        <div className="flex-shrink-0">
          {showOutcome ? (
            <StatusBadge determination={pair.notification_determination} />
          ) : (
            <StatusBadge status={pair.notification_status} />
          )}
        </div>
      </div>

      <div className="flex items-stretch gap-2 sm:gap-4">
        <div className="relative w-14 sm:w-20 shrink-0 h-11">
          <span className={`${ABOVE_LINE} inset-x-0 text-right text-[11px] font-medium text-gray-500`}>Waiver filed</span>
          <span className={`${BELOW_LINE} inset-x-0 text-right text-xs font-medium text-gray-900`}>{formatDateMedium(start)}</span>
        </div>

        <div className="relative flex-1 min-w-0 h-11">
          <div
            className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-5 rounded-full bg-gray-100"
            role="img"
            aria-label={`Timeline for ${pair.notification_name}: waiver filed ${formatDateMedium(start)}, declined ${formatDateMedium(pair.waiver_declined_date)}, re-filed as a notification ${formatDateMedium(pair.notification_filed_date)}${showOutcome ? `, determined ${formatDateMedium(pair.notification_determination_date)}` : ', still under assessment'}`}
          >
            {declinedPercent !== null && (
              <div className="absolute inset-y-0 left-0 rounded-full bg-phase-1/50" style={{ width: `${declinedPercent}%` }} />
            )}
            {filedPercent !== null && (
              <div
                className={`absolute inset-y-0 right-0 rounded-full ${showOutcome ? 'bg-accent/60' : 'bg-accent/30'}`}
                style={{ left: `${filedPercent}%` }}
              />
            )}
            {gapPercent !== null && daysToRefile !== null && (
              <span
                className="absolute top-1/2 whitespace-nowrap text-[10px] font-semibold text-gray-800"
                style={gapLabelStyle}
              >
                {daysToRefile} day{daysToRefile !== 1 ? 's' : ''}
              </span>
            )}
            {declinedPercent !== null && (
              <div
                className="absolute top-1/2 h-3 w-3 rounded-full ring-2 ring-white bg-phase-1-dark"
                style={{ left: `${declinedPercent}%`, transform: 'translate(-50%, -50%)' }}
                title={`Waiver declined: ${formatDateMedium(pair.waiver_declined_date)}`}
              />
            )}
            {filedPercent !== null && (
              <div
                className="absolute top-1/2 h-3 w-3 rounded-full ring-2 ring-white bg-accent-dark"
                style={{ left: `${filedPercent}%`, transform: 'translate(-50%, -50%)' }}
                title={`Re-filed as notification: ${formatDateMedium(pair.notification_filed_date)}`}
              />
            )}
          </div>
        </div>

        <div className="relative w-14 sm:w-20 shrink-0 h-11">
          <span className={`${ABOVE_LINE} inset-x-0 text-left text-[11px] font-medium text-gray-500`}>
            {showOutcome ? 'Determined' : 'Today'}
          </span>
          <span className={`${BELOW_LINE} inset-x-0 text-left text-xs font-medium text-gray-900`}>
            {showOutcome ? formatDateMedium(pair.notification_determination_date) : 'Ongoing'}
          </span>
        </div>
      </div>
    </li>
  );
}

function RefiledList({ pairs, showOutcome, emptyMessage }) {
  if (pairs.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6">
        <p className="text-gray-500 text-sm">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-5 sm:p-6">
      <ul className="divide-y divide-gray-100">
        {pairs.map((pair) => (
          <RefiledCard key={pair.notification_id} pair={pair} showOutcome={showOutcome} />
        ))}
      </ul>
    </div>
  );
}

function RefiledNotifications() {
  const { data, loading, error } = useFetchData(API_ENDPOINTS.refiledNotifications, { cacheKey: 'refiled-notifications' });

  if (loading) return <LoadingSpinner />;
  if (error) return <div role="alert" className="text-red-600 p-8 text-center">Error: {error}</div>;

  const current = data?.current || [];
  const completed = data?.completed || [];
  const all = [...current, ...completed];
  const totalPairs = all.length;
  const medianDaysToRefile = median(
    all
      .map((p) => calculateDuration(p.waiver_declined_date, p.notification_filed_date))
      .filter((d) => d !== null)
  );

  return (
    <>
      <SEO
        title="Refiled notifications"
        description="Mergers originally filed with the ACCC as a waiver application, declined, and then re-filed as a formal notification."
        url="/refiled-notifications"
      />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <header className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
            Waivers re-filed as notifications
          </h1>
          <p className="mt-2 text-sm text-gray-500 max-w-3xl">
            Some mergers are first filed as a waiver application asking the ACCC to waive the need
            for formal review. When a waiver is declined, the parties sometimes re-file the same
            deal as a formal notification instead. This page tracks those pairs.
          </p>
        </header>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          <StatCard title="Waivers re-filed" value={totalPairs} icon={<FaArrowRightArrowLeft />} />
          <StatCard title="Awaiting a determination" value={current.length} icon={<FaHourglassHalf />} />
          <StatCard
            title="Median time to re-file"
            value={medianDaysToRefile !== null ? `${medianDaysToRefile} days` : 'N/A'}
            subtitle="From waiver decline to re-filing"
            icon={<FaCalendarDays />}
          />
        </div>

        <section aria-labelledby="refiled-current-heading" className="mb-8">
          <h2 id="refiled-current-heading" className="text-lg font-semibold text-gray-900 mb-4">
            Awaiting a determination
          </h2>
          <RefiledList
            pairs={current}
            showOutcome={false}
            emptyMessage="No waivers are currently awaiting a re-filed notification outcome."
          />
        </section>

        <section aria-labelledby="refiled-completed-heading">
          <h2 id="refiled-completed-heading" className="text-lg font-semibold text-gray-900 mb-4">
            Determined
          </h2>
          <RefiledList
            pairs={completed}
            showOutcome
            emptyMessage="No re-filed notifications have been determined yet."
          />
        </section>
      </div>
    </>
  );
}

export default RefiledNotifications;
