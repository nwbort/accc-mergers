import { Link } from 'react-router';
import { differenceInCalendarDays, parseISO, isValid } from 'date-fns';
import { FaArrowRightArrowLeft, FaHourglassHalf, FaCalendarDays, FaCircleCheck } from 'react-icons/fa6';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import StatusBadge from '../components/StatusBadge';
import StatCard from '../components/StatCard';
import PhaseDurationComparison from '../components/PhaseDurationComparison';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { mergerPath } from '../utils/slug';
import { formatDateMedium, calculateDuration } from '../utils/dates';
import { MERGER_STATUS } from '../constants/mergerStatus';
import { CARD } from '../utils/classNames';
import { STATIC_PAGE_META } from '../utils/pageMeta';

// Title and description live in the shared table so this page and the
// build-time prerenderer emit the same <head>.
const PAGE_META = STATIC_PAGE_META['/refiled-notifications'];

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
// technique Phase2Timeline uses for its NOCC label. The "Phase 2" label above
// the track is centred on its own leg the same way.
const GAP_HALF = '1.75rem';
const PHASE_2_HALF = '1.5rem';

// Centre `percent` along the track, clamped so a label sitting near either end
// stops at the edge instead of hanging off it.
function clampedLabelStyle(percent, half, translate) {
  return {
    left: `clamp(${half}, ${percent}%, calc(100% - ${half}))`,
    transform: translate,
  };
}

function RefiledCard({ pair, showOutcome }) {
  // A re-filed notification can itself be referred to Phase 2 (MN-40017 was),
  // so the track carries a third leg: waiver → notification's Phase 1 →
  // Phase 2. phase_1_determination is the referral for referred matters, the
  // Phase 1 determination for the rest, so it is what tells the two apart.
  const referred = pair.notification_phase_1_determination === MERGER_STATUS.REFERRED_TO_PHASE_2;
  const referralDate = referred ? pair.notification_phase_1_end_date : null;
  // While a referred matter is still running, the track runs on to the
  // statutory Phase 2 deadline — otherwise the Phase 2 leg would have nowhere
  // to go, and the deadline is the more useful endpoint than "today".
  const phase2Deadline = referred && !showOutcome
    ? pair.notification_end_of_determination_period
    : null;

  const start = pair.waiver_filed_date;
  const end = showOutcome
    ? pair.notification_determination_date
    : phase2Deadline || new Date().toISOString();
  const declinedPercent = percentAlong(pair.waiver_declined_date, start, end);
  const filedPercent = percentAlong(pair.notification_filed_date, start, end);
  const referralPercent = percentAlong(referralDate, start, end);
  // Only worth marking while the track extends past today, i.e. out to a
  // pending Phase 2 deadline.
  const todayPercent = phase2Deadline ? percentAlong(new Date().toISOString(), start, end) : null;
  const daysToRefile = calculateDuration(pair.waiver_declined_date, pair.notification_filed_date);
  const gapPercent = declinedPercent !== null && filedPercent !== null
    ? (declinedPercent + filedPercent) / 2
    : null;
  const gapLabelStyle = gapPercent === null
    ? null
    : clampedLabelStyle(gapPercent, GAP_HALF, 'translate(-50%, -50%)');
  const phase2LabelStyle = referralPercent === null
    ? null
    : clampedLabelStyle((referralPercent + 100) / 2, PHASE_2_HALF, 'translateX(-50%)');

  const endLabel = showOutcome ? 'Determined' : phase2Deadline ? 'Due by' : 'Today';
  const endValue = showOutcome
    ? formatDateMedium(pair.notification_determination_date)
    : phase2Deadline ? formatDateMedium(phase2Deadline) : 'Ongoing';

  const trackDescription = [
    `Timeline for ${pair.notification_name}`,
    `waiver filed ${formatDateMedium(start)}`,
    `declined ${formatDateMedium(pair.waiver_declined_date)}`,
    `re-filed as a notification ${formatDateMedium(pair.notification_filed_date)}`,
    ...(referralDate ? [`referred to Phase 2 ${formatDateMedium(referralDate)}`] : []),
    showOutcome
      ? `determined ${formatDateMedium(pair.notification_determination_date)}`
      : phase2Deadline
        ? `determination due by ${formatDateMedium(phase2Deadline)}`
        : 'still under assessment',
  ].join(', ');

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
        {(showOutcome || referred) && (
          <div className="flex-shrink-0">
            <StatusBadge
              determination={showOutcome ? pair.notification_determination : MERGER_STATUS.REFERRED_TO_PHASE_2}
            />
          </div>
        )}
      </div>

      <div className="flex items-stretch gap-2 sm:gap-4">
        <div className="relative w-14 sm:w-20 shrink-0 h-11">
          <span className={`${ABOVE_LINE} inset-x-0 text-right text-[11px] font-medium text-gray-500`}>Waiver filed</span>
          <span className={`${BELOW_LINE} inset-x-0 text-right text-xs font-medium text-gray-900`}>{formatDateMedium(start)}</span>
        </div>

        <div className="relative flex-1 min-w-0 h-11">
          {referralPercent !== null && (
            <span
              className={`${ABOVE_LINE} whitespace-nowrap text-[10px] font-semibold text-phase-2-dark`}
              style={phase2LabelStyle}
            >
              Phase 2
            </span>
          )}

          <div
            className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-5 rounded-full bg-gray-100"
            role="img"
            aria-label={trackDescription}
          >
            {declinedPercent !== null && (
              <div className="absolute inset-y-0 left-0 rounded-full bg-phase-1/50" style={{ width: `${declinedPercent}%` }} />
            )}
            {filedPercent !== null && (
              <div
                className={`absolute inset-y-0 rounded-full ${showOutcome ? 'bg-accent/60' : 'bg-accent/30'}`}
                // Stops at the referral when there is one, so the notification's
                // Phase 1 and its Phase 2 read as separate legs.
                style={{ left: `${filedPercent}%`, right: `${100 - (referralPercent ?? 100)}%` }}
              />
            )}
            {referralPercent !== null && (
              <div
                className={`absolute inset-y-0 right-0 rounded-full ${showOutcome ? 'bg-phase-2/60' : 'bg-phase-2/30'}`}
                style={{ left: `${referralPercent}%` }}
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
            {referralPercent !== null && (
              <div
                className="absolute top-1/2 h-3 w-3 rounded-full ring-2 ring-white bg-phase-2-dark"
                style={{ left: `${referralPercent}%`, transform: 'translate(-50%, -50%)' }}
                title={`Referred to Phase 2: ${formatDateMedium(referralDate)}`}
              />
            )}
            {todayPercent !== null && (
              <div
                className="absolute top-1/2 -translate-y-1/2 h-7 w-0.5 bg-gray-900"
                style={{ left: `${todayPercent}%` }}
                title="Today"
              />
            )}
          </div>
        </div>

        <div className="relative w-14 sm:w-20 shrink-0 h-11">
          <span className={`${ABOVE_LINE} inset-x-0 text-left text-[11px] font-medium text-gray-500`}>
            {endLabel}
          </span>
          <span className={`${BELOW_LINE} inset-x-0 text-left text-xs font-medium text-gray-900`}>
            {endValue}
          </span>
        </div>
      </div>
    </li>
  );
}

function RefiledList({ pairs, showOutcome, emptyMessage }) {
  if (pairs.length === 0) {
    return (
      <div className={`${CARD} p-6`}>
        <p className="text-gray-500 text-sm">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className={`${CARD} p-5 sm:p-6`}>
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
  if (error) return <ErrorMessage error={error} />;

  const current = data?.current || [];
  const completed = data?.completed || [];
  const all = [...current, ...completed];
  const totalPairs = all.length;
  const medianDaysToRefile = median(
    all
      .map((p) => calculateDuration(p.waiver_declined_date, p.notification_filed_date))
      .filter((d) => d !== null)
  );

  // Share of concluded Phase 1 reviews that cleared rather than being referred
  // to Phase 2, alongside the same figure for notifications that were never
  // waivers — the comparison the duration chart below draws too.
  const clearanceRate = data?.phase_1_clearance_rate;
  const straightClearanceRate = data?.straight_phase_1_clearance_rate;
  const clearancePct = clearanceRate?.rate != null ? Math.round(clearanceRate.rate * 100) : null;
  const straightClearancePct = straightClearanceRate?.rate != null
    ? Math.round(straightClearanceRate.rate * 100)
    : null;

  const phaseDuration = data?.phase_duration;
  const straightPhaseDuration = data?.straight_phase_duration;

  return (
    <>
      <SEO
        title={PAGE_META.title}
        description={PAGE_META.description}
        url="/refiled-notifications"
      />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <header className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
            Waivers re-filed as notifications
          </h1>
        </header>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            title="Waivers re-filed"
            value={totalPairs}
            subtitle="Waiver declined, then notified"
            icon={<FaArrowRightArrowLeft />}
          />
          <StatCard
            title="Awaiting a determination"
            value={current.length}
            subtitle={`${completed.length} already determined`}
            icon={<FaHourglassHalf />}
          />
          <StatCard
            title="Median time to re-file"
            value={medianDaysToRefile !== null ? `${medianDaysToRefile} days` : 'N/A'}
            subtitle="From decline to re-filing"
            icon={<FaCalendarDays />}
          />
          <StatCard
            title="Phase 1 clearance rate"
            value={clearancePct !== null ? `${clearancePct}%` : 'N/A'}
            subtitle={
              clearancePct !== null && straightClearancePct !== null
                ? `${straightClearancePct}% filed as Phase 1 from the outset`
                : undefined
            }
            icon={<FaCircleCheck />}
          />
        </div>

        {phaseDuration && (
          <div className="mb-8">
            <PhaseDurationComparison
              duration={phaseDuration}
              comparisons={
                straightPhaseDuration ? [{ name: 'Filed as Phase 1 from the outset', duration: straightPhaseDuration }] : []
              }
              subjectLabel="Refiled from a waiver"
            />
          </div>
        )}

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
            Completed
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
