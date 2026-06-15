import { parseISO, isValid } from 'date-fns';
import {
  formatDateMedium,
  calculateDuration,
  calculateBusinessDays,
  getDaysRemaining,
  getBusinessDaysRemaining,
  addBusinessDays,
} from '../utils/dates';
import { MERGER_STATUS } from '../constants/mergerStatus';

// Statutory window the ACCC works to for merger waiver applications. Waivers
// aren't published with an explicit end-of-determination date, so we derive the
// deadline as this many business days after the application.
const WAIVER_BUSINESS_DAYS = 25;

// Determination outcome -> Tailwind background for the end node, so a glance at
// the timeline endpoint conveys the result. Anything unmapped falls back to the
// primary colour.
const OUTCOME_DOT = {
  [MERGER_STATUS.APPROVED]: 'bg-emerald-500',
  [MERGER_STATUS.NOT_OPPOSED]: 'bg-emerald-500',
  [MERGER_STATUS.DECLINED]: 'bg-red-500',
  [MERGER_STATUS.NOT_APPROVED]: 'bg-red-500',
  [MERGER_STATUS.REFERRED_TO_PHASE_2]: 'bg-amber-500',
};

// Position of `date` along the start -> end axis, clamped to [0, 100].
const axisPct = (date, start, end) =>
  Math.min(100, Math.max(0, ((date - start) / (end - start)) * 100));

// Shown when we can't draw a proportional axis: a suspended assessment with no
// effective notification, or a pending waiver/notification with no end date yet.
function MergerTimelineFallback({ merger, startStr }) {
  const suspended = merger.status?.toLowerCase().includes('suspended');
  const startLabel = merger.is_waiver ? 'Waiver application' : 'Notified';

  return (
    <dl className="flex flex-wrap gap-x-12 gap-y-4">
      <div>
        <dt className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">
          {startLabel}
        </dt>
        <dd className="text-sm font-medium text-gray-900">
          {suspended && !merger.effective_notification_datetime ? (
            <>
              None &ndash; assessment suspended
              {merger.original_notification_datetime && (
                <span className="text-gray-500 font-normal">
                  {' '}(originally {formatDateMedium(merger.original_notification_datetime)})
                </span>
              )}
            </>
          ) : (
            formatDateMedium(startStr)
          )}
        </dd>
      </div>
      <div>
        <dt className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">
          Status
        </dt>
        <dd className="text-sm font-medium text-gray-900">{merger.status || 'N/A'}</dd>
      </div>
    </dl>
  );
}

/**
 * Horizontal timeline for the merger detail header. Plots the assessment from
 * its start (notification or waiver application) to its end (the published
 * determination once decided, otherwise the statutory decision deadline), with
 * a "today" marker and progress fill while the assessment is still running.
 */
function MergerTimeline({ merger }) {
  const startStr = merger.effective_notification_datetime || merger.original_notification_datetime;
  const isComplete = Boolean(merger.determination_publication_date);

  const start = startStr ? parseISO(startStr) : null;

  // Use the published end-of-determination date when present; for waivers
  // (which have none) fall back to the statutory 25-business-day window.
  let deadlineStr = merger.end_of_determination_period;
  if (!deadlineStr && merger.is_waiver && start && isValid(start)) {
    const derived = addBusinessDays(start, WAIVER_BUSINESS_DAYS);
    deadlineStr = derived ? derived.toISOString() : null;
  }
  const deadline = deadlineStr ? parseISO(deadlineStr) : null;
  const hasDeadline = start && deadline && isValid(start) && isValid(deadline) && deadline > start;

  // The right-hand endpoint is the statutory decision deadline whenever there
  // is one — including for decided mergers, where the actual determination is
  // shown as a marker along the axis so you can see how early it landed. Only
  // when there's no deadline (e.g. waivers) does a completed merger end on its
  // determination date.
  let endStr;
  let end;
  let endLabel;
  let endIsOutcome = false;
  if (hasDeadline) {
    endStr = deadlineStr;
    end = deadline;
    endLabel = 'Deadline';
  } else if (isComplete) {
    endStr = merger.determination_publication_date;
    end = parseISO(endStr);
    endLabel = 'Determination';
    endIsOutcome = true;
  }

  const hasRange = start && end && isValid(start) && isValid(end) && end > start;
  if (!hasRange) {
    return <MergerTimelineFallback merger={merger} startStr={startStr} />;
  }

  const startLabel = merger.is_waiver ? 'Waiver application' : 'Notified';
  const outcomeDot = OUTCOME_DOT[merger.accc_determination] || 'bg-primary';

  const duration = calculateDuration(startStr, merger.determination_publication_date);
  const businessDuration = calculateBusinessDays(startStr, merger.determination_publication_date);
  const daysRemaining = getDaysRemaining(deadlineStr);
  const businessDaysRemaining = getBusinessDaysRemaining(deadlineStr);

  // Mid-axis "determination" marker for decided mergers whose endpoint is the
  // deadline.
  const decisionPct = isComplete && hasDeadline
    ? axisPct(parseISO(merger.determination_publication_date), start, end)
    : null;

  // For mergers referred to Phase 2, mark the Phase 1 determination date with a
  // small unlabelled dot (details on hover).
  const wentToPhase2 = merger.phase_1_determination === MERGER_STATUS.REFERRED_TO_PHASE_2
    || Boolean(merger.phase_2_determination_date);
  let phase1Pct = null;
  if (wentToPhase2 && merger.phase_1_determination_date) {
    const phase1 = parseISO(merger.phase_1_determination_date);
    if (isValid(phase1) && phase1 > start && phase1 < end) {
      phase1Pct = axisPct(phase1, start, end);
    }
  }

  // Progress + "today" marker, only while the assessment is still running.
  let todayPct = null;
  let overdue = false;
  if (!isComplete) {
    const now = new Date();
    if (now >= end) {
      overdue = true;
    } else if (now > start) {
      todayPct = axisPct(now, start, end);
    }
  }

  let fillPct;
  if (decisionPct !== null) fillPct = decisionPct;
  else if (isComplete || overdue) fillPct = 100;
  else fillPct = todayPct ?? 0;

  // A single mid-axis marker: the determination (decided) or "today" (running).
  // These are mutually exclusive. The label/value are anchored to the marker
  // with translateX(-pct%) so they swing from left-aligned at the start of the
  // track, through centred, to right-aligned at the end — never spilling over
  // the endpoints, which sit outside the track.
  const midPct = decisionPct !== null ? decisionPct : todayPct;
  const midIsDetermination = decisionPct !== null;
  const midAlign = midPct === null ? null : midPct < 33 ? 'left' : midPct > 67 ? 'right' : 'center';

  const durationStr = duration !== null && businessDuration !== null
    ? `${duration} cal / ${businessDuration} bus. days`
    : null;
  const remainingStr = daysRemaining !== null && businessDaysRemaining !== null
    ? `${daysRemaining} cal / ${businessDaysRemaining} bus. days left`
    : null;

  // Note under the end date: total duration when the axis ends on the
  // determination itself, or an overdue flag when the deadline has passed.
  let endNote = null;
  let endNoteClass = 'text-gray-500';
  if (endIsOutcome && durationStr) {
    endNote = durationStr;
  } else if (overdue) {
    endNote = 'Overdue';
    endNoteClass = 'font-medium text-amber-600';
  }

  // No nowrap on labels so multi-word endpoint labels wrap within the fixed
  // column width on small screens instead of squeezing the track.
  const labelClass = 'text-xs font-medium text-gray-500 uppercase tracking-wider';
  const dateClass = 'text-sm font-medium text-gray-900 whitespace-nowrap';
  // Every label sits its bottom this far above the line; every value sits its
  // top this far below it. Shared across endpoints and mid markers so the three
  // columns line up, with clear breathing room around the bar.
  const aboveLine = 'absolute bottom-1/2 mb-3';
  const belowLine = 'absolute top-1/2 mt-3';

  return (
    <div role="group" aria-label="Merger assessment timeline" className="flex items-stretch gap-2 sm:gap-4">
      {/* Start endpoint — outside the track, hugging it from the left */}
      <div className="relative w-24 shrink-0 h-24">
        <span className={`${aboveLine} inset-x-0 text-right ${labelClass}`}>{startLabel}</span>
        <span className={`${belowLine} inset-x-0 text-right ${dateClass}`}>{formatDateMedium(startStr)}</span>
      </div>

      {/* Track region — the mid marker's label and value live inside it */}
      <div className="relative flex-1 min-w-0 h-24">
        {/* Mid marker label, above the line */}
        {midPct !== null && (
          <span
            className={`${aboveLine} whitespace-nowrap ${
              midIsDetermination ? labelClass : 'text-xs font-semibold text-primary uppercase tracking-wider'
            }`}
            style={{ left: `${midPct}%`, transform: `translateX(-${midPct}%)`, textAlign: midAlign }}
          >
            {midIsDetermination ? 'Determination' : 'Today'}
          </span>
        )}

        {/* The line */}
        <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-3.5">
          <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1.5 rounded-full bg-gray-100" />
          <div
            className="absolute left-0 top-1/2 -translate-y-1/2 h-1.5 rounded-full bg-primary transition-[width] duration-500"
            style={{ width: `${fillPct}%` }}
          />
          {/* Phase 1 determination marker (referred to Phase 2). Smaller and
              unlabelled — details shown on hover via the title tooltip. */}
          {phase1Pct !== null && (
            <span
              className="absolute top-1/2 h-2.5 w-2.5 rounded-full bg-amber-500 ring-2 ring-white cursor-help"
              style={{ left: `${phase1Pct}%`, transform: 'translate(-50%, -50%)' }}
              title={`Referred to Phase 2 · ${formatDateMedium(merger.phase_1_determination_date)}`}
              aria-label={`Referred to Phase 2 on ${formatDateMedium(merger.phase_1_determination_date)}`}
            />
          )}

          {/* Start node */}
          <span className="absolute left-0 top-1/2 -translate-x-1/2 -translate-y-1/2 h-3.5 w-3.5 rounded-full bg-primary ring-2 ring-white" />
          {/* End node */}
          <span
            className={`absolute right-0 top-1/2 translate-x-1/2 -translate-y-1/2 h-3.5 w-3.5 rounded-full ring-2 ring-white ${
              endIsOutcome ? outcomeDot : 'bg-white border-2 border-gray-300'
            }`}
          />
          {/* Determination marker — rendered after the end node so it stays
              visible if the determination landed on or past the deadline */}
          {decisionPct !== null && (
            <span
              className={`absolute top-1/2 h-3.5 w-3.5 rounded-full ring-2 ring-white shadow-sm ${outcomeDot}`}
              style={{ left: `${decisionPct}%`, transform: 'translate(-50%, -50%)' }}
              aria-label="Determination"
            />
          )}
          {/* Today marker */}
          {todayPct !== null && (
            <span
              className="absolute top-1/2 h-3.5 w-3.5 rounded-full bg-white ring-2 ring-primary shadow-sm"
              style={{ left: `${todayPct}%`, transform: 'translate(-50%, -50%)' }}
              aria-label="Today"
            />
          )}
        </div>

        {/* Mid marker value, below the line */}
        {midPct !== null && (
          <span
            className={`${belowLine} leading-tight`}
            style={{ left: `${midPct}%`, transform: `translateX(-${midPct}%)`, textAlign: midAlign }}
          >
            {midIsDetermination ? (
              <>
                <span className={`block ${dateClass}`}>{formatDateMedium(merger.determination_publication_date)}</span>
                {durationStr && (
                  <span className="block max-w-[7rem] text-[11px] font-normal text-gray-500">{durationStr}</span>
                )}
              </>
            ) : (
              remainingStr && (
                <span className="block max-w-[7rem] text-[11px] font-normal text-gray-500">{remainingStr}</span>
              )
            )}
          </span>
        )}
      </div>

      {/* End endpoint — outside the track, hugging it from the right */}
      <div className="relative w-24 shrink-0 h-24">
        <span className={`${aboveLine} inset-x-0 text-left ${labelClass}`}>{endLabel}</span>
        <span className={`${belowLine} inset-x-0 text-left`}>
          <span className={`block ${dateClass}`}>{formatDateMedium(endStr)}</span>
          {endNote && <span className={`block text-[11px] ${endNoteClass}`}>{endNote}</span>}
        </span>
      </div>
    </div>
  );
}

export default MergerTimeline;
