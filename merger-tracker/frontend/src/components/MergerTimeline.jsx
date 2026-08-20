import { useLayoutEffect, useRef, useState } from 'react';
import { isValid } from 'date-fns';
import {
  formatDateMedium,
  calculateDuration,
  calculateBusinessDays,
  getDaysRemaining,
  getBusinessDaysRemaining,
  addBusinessDays,
  parseDateOnly,
  toDateString,
  australianToday,
} from '../utils/dates';
import { MERGER_STATUS } from '../constants/mergerStatus';
import { getOutcomeDot } from '../constants/outcomeDotColors';
import { SECTION_HEADING } from '../utils/classNames';

// Statutory window the ACCC works to for merger waiver applications. Waivers
// aren't published with an explicit end-of-determination date, so we derive the
// deadline as this many business days after the application.
const WAIVER_BUSINESS_DAYS = 25;

// Position of `date` along the start -> end axis, clamped to [0, 100].
const axisPct = (date, start, end) =>
  Math.min(100, Math.max(0, ((date - start) / (end - start)) * 100));

// The mid-axis label/value sits in a fixed-width box centred on its marker, but
// its centre is clamped to stay MID_HALF in from each track end. So it tracks
// the marker (centred) through the middle of the track and, as the marker nears
// an edge, the box stops at the edge while the marker slides toward its side —
// keeping it centred most of the time, never overflowing onto the endpoint
// labels, and (unlike a width-relative translate) always monotonic, so it
// behaves the same on a narrow mobile track. Text aligns toward whichever edge
// the marker is approaching so it stays under the marker.
const MID_BOX = '7.5rem';
const MID_HALF = '3.75rem'; // half of MID_BOX
const MID_EDGE_ALIGN = 5; // within this % of an end, align text to that end

// Pixel widths of the two label boxes that can compete for the same stretch of
// track, used to decide whether they'd collide. These mirror MID_BOX and
// EXPECTED_BOX below at a 16px root font size; they only drive the
// hide-on-overlap check, so a non-default root size costs a little precision
// there and nothing else.
const MID_BOX_PX = 120;
const EXPECTED_BOX = '9rem';
const EXPECTED_BOX_PX = 144;
// Clear space the two labels must keep between them to count as not colliding.
const LABEL_GUTTER_PX = 8;

// Narrowest the prediction band may be drawn. A p25-p75 band can be a single
// business day wide (or zero, when there's no band at all), which would
// otherwise render as an invisible sliver.
const MIN_BAND_PX = 4;

// The "soon" pip: once the forecast window has closed but the matter is still
// running, the band is replaced by a short nub sitting just clear of the today
// marker. It's no longer pointing at a stretch of the axis — the window it
// described is behind us — so it's drawn at a fixed size rather than scaled to
// dates that no longer mean anything.
const SOON_PIP_PX = 24;
const SOON_PIP_GAP_PX = 10;

// Centre of a fixed-width label box, in px along the track, clamped to keep the
// box inside the track exactly as the CSS clamp() on midStyle does.
const clampedLabelCentre = (pct, boxPx, trackPx) => {
  const half = Math.min(boxPx / 2, trackPx / 2);
  return Math.min(Math.max((pct / 100) * trackPx, half), trackPx - half);
};

// Shown when we can't draw a proportional axis: a suspended assessment with no
// effective notification, or a pending waiver/notification with no end date yet.
function MergerTimelineFallback({ merger, startStr }) {
  const suspended = merger.status?.toLowerCase().includes('suspended');
  const startLabel = merger.is_waiver ? 'Waiver application' : 'Notified';

  return (
    <dl className="flex flex-wrap gap-x-12 gap-y-4">
      <div>
        <dt className={`${SECTION_HEADING} mb-1.5`}>
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
        <dt className={`${SECTION_HEADING} mb-1.5`}>
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
  // Measured so the prediction label can stand down when it would collide with
  // the "Today" label: both are fixed-width boxes on a fluid track, so whether
  // they overlap depends on the rendered width and can't be decided in
  // percentages alone. Declared before any early return so the hook order
  // holds for the fallback view too. Width stays 0 where ResizeObserver and
  // layout are unavailable, which reads as "can't tell" and shows the label.
  const trackRef = useRef(null);
  const [trackWidth, setTrackWidth] = useState(0);

  useLayoutEffect(() => {
    const el = trackRef.current;
    if (!el) return undefined;

    const measure = () => setTrackWidth(el.getBoundingClientRect().width);
    measure();

    if (typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const startStr = merger.effective_notification_datetime || merger.original_notification_datetime;
  const isCeased = merger.status === MERGER_STATUS.ASSESSMENT_CEASED;
  // For ceased mergers the cessation date stands in for the determination date.
  const effectiveDeterminationDate = merger.determination_publication_date
    || (isCeased ? merger.ceased_date : null);
  const isComplete = Boolean(effectiveDeterminationDate);

  const start = startStr ? parseDateOnly(startStr) : null;

  // Use the published end-of-determination date when present; for waivers
  // (which have none) fall back to the statutory 25-business-day window.
  let deadlineStr = merger.end_of_determination_period;
  if (!deadlineStr && merger.is_waiver && start && isValid(start)) {
    const derived = addBusinessDays(start, WAIVER_BUSINESS_DAYS);
    deadlineStr = derived ? toDateString(derived) : null;
  }
  const deadline = deadlineStr ? parseDateOnly(deadlineStr) : null;
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
    endStr = effectiveDeterminationDate;
    end = parseDateOnly(endStr);
    endLabel = isCeased ? 'Ceased' : 'Determination';
    endIsOutcome = true;
  }

  const hasRange = start && end && isValid(start) && isValid(end) && end > start;
  if (!hasRange) {
    return <MergerTimelineFallback merger={merger} startStr={startStr} />;
  }

  const startLabel = merger.is_waiver ? 'Waiver application' : 'Notified';
  const outcomeDot = getOutcomeDot({ determination: merger.accc_determination, status: merger.status }).dot;

  const duration = calculateDuration(startStr, effectiveDeterminationDate);
  const businessDuration = calculateBusinessDays(startStr, effectiveDeterminationDate);
  const daysRemaining = getDaysRemaining(deadlineStr);
  const businessDaysRemaining = getBusinessDaysRemaining(deadlineStr);

  // Mid-axis "determination" marker for decided mergers whose endpoint is the
  // deadline.
  const decisionPct = isComplete && hasDeadline
    ? axisPct(parseDateOnly(effectiveDeterminationDate), start, end)
    : null;

  // For mergers referred to Phase 2, mark the Phase 1 determination date with a
  // small unlabelled dot (details on hover).
  const wentToPhase2 = merger.phase_1_determination === MERGER_STATUS.REFERRED_TO_PHASE_2
    || Boolean(merger.phase_2_determination_date);
  let phase1Pct = null;
  if (wentToPhase2 && merger.phase_1_determination_date) {
    const phase1 = parseDateOnly(merger.phase_1_determination_date);
    if (isValid(phase1) && phase1 > start && phase1 < end) {
      phase1Pct = axisPct(phase1, start, end);
    }
  }

  // Progress + "today" marker, only while the assessment is still running.
  // Overdue is judged on calendar days (ACCC's Australian "today") rather than
  // the raw current instant, so the deadline's own day reads as "due today"
  // instead of "overdue" from the moment it ticks over at local midnight.
  let todayPct = null;
  let overdue = false;
  let dueToday = false;
  if (!isComplete) {
    const now = new Date();
    const today = australianToday();
    if (today > end) {
      overdue = true;
    } else if (today.getTime() === end.getTime()) {
      dueToday = true;
      todayPct = axisPct(now, start, end);
    } else if (now > start) {
      todayPct = axisPct(now, start, end);
    }
  }

  // Expected determination: the at-filing estimate of how long this matter's
  // phase 1 will run (frozen per merger by the pipeline), converted back to
  // dates. It has two states, both dependent on the matter still running and a
  // today marker being on the axis to anchor them.
  //
  //  - While the forecast window is still open, it's shaded across its p25-p75
  //    range with the left edge held at today, so it reads as "the window still
  //    ahead in which we expect the determination", narrowing as time passes.
  //  - Once today is past the far end of that window, the window is behind us
  //    and the shading would be describing the past. It collapses to a short
  //    pip just right of today, reading "expected determination soon" — the
  //    matter is overdue against the forecast but still inside its statutory
  //    clock.
  const estimate = merger.phase_1_estimate;
  let expectedLeftPct = null;
  let expectedWidthPct = null;
  let expectedCentrePct = null;
  let expectedTitle = null;
  let expectedSoon = false;
  if (
    estimate?.expected_business_days != null
    && !isComplete
    && !merger.phase_1_determination_date
    && todayPct !== null
  ) {
    const today = australianToday();
    const expected = addBusinessDays(start, estimate.expected_business_days);

    // An estimate landing on or past the statutory deadline says nothing useful
    // about where on this axis the determination falls, so it's dropped rather
    // than pinned to the end.
    if (expected && isValid(expected) && expected < end) {
      const [low, high] = estimate.range_business_days || [];
      // Fall back to the point estimate if either edge failed to resolve, so a
      // malformed range degrades to a marker rather than dropping the forecast.
      const rangeStart = addBusinessDays(start, low ?? estimate.expected_business_days);
      const rangeEnd = addBusinessDays(start, high ?? estimate.expected_business_days);
      const windowStart = rangeStart && isValid(rangeStart) ? rangeStart : expected;
      let windowEnd = rangeEnd && isValid(rangeEnd) ? rangeEnd : expected;
      // A range that ends before its own median is malformed; the median is the
      // figure we trust, so it sets the floor for where the window closes.
      if (windowEnd < expected) windowEnd = expected;

      if (today > windowEnd) {
        expectedSoon = true;
      } else {
        const left = Math.max(axisPct(windowStart, start, end), axisPct(today, start, end));
        const right = Math.min(axisPct(windowEnd, start, end), 100);
        expectedLeftPct = left;
        expectedWidthPct = Math.max(right - left, 0);
        expectedCentrePct = left + expectedWidthPct / 2;
      }

      const band = low != null && high != null && low !== high
        ? `${low}-${high} business days`
        : `${estimate.expected_business_days} business days`;
      expectedTitle = `Expected determination \u00b7 ${formatDateMedium(toDateString(expected))} \u00b7 ${band}`;
    }
  }

  let fillPct;
  if (decisionPct !== null) fillPct = decisionPct;
  else if (isComplete || overdue) fillPct = 100;
  else fillPct = todayPct ?? 0;

  // A single mid-axis marker: the determination (decided) or "today" (running).
  // These are mutually exclusive.
  const midPct = decisionPct !== null ? decisionPct : todayPct;
  const midIsDetermination = decisionPct !== null;
  const midLabel = midIsDetermination ? (isCeased ? 'Ceased' : 'Determination') : 'Today';
  // Shared positioning for the mid label and value so they stay aligned.
  const midStyle = midPct === null ? null : {
    width: MID_BOX,
    maxWidth: '100%',
    left: `clamp(${MID_HALF}, ${midPct}%, calc(100% - ${MID_HALF}))`,
    transform: 'translateX(-50%)',
    textAlign: midPct < MID_EDGE_ALIGN ? 'left' : midPct > 100 - MID_EDGE_ALIGN ? 'right' : 'center',
  };

  // Where the "Today" label's box ends, in px along the track — the point both
  // prediction labels have to stay clear of. Mirrors the CSS clamp() on
  // midStyle. Null when the track hasn't been measured, which reads as "can't
  // tell" everywhere it's used.
  const midLabelRight = midPct !== null && trackWidth > 0
    ? clampedLabelCentre(midPct, MID_BOX_PX, trackWidth) + MID_BOX_PX / 2
    : null;

  // The prediction label stands down whenever it would collide with the "Today"
  // label — the actual state of the matter outranks a forecast about it. Both
  // are fixed-width boxes clamped inside the track, so the test is done in
  // measured pixels; an unmeasured track can't show a collision, so the label
  // shows.
  let showExpectedLabel = expectedCentrePct !== null;
  if (showExpectedLabel && midLabelRight !== null) {
    const midCentre = clampedLabelCentre(midPct, MID_BOX_PX, trackWidth);
    const expectedCentre = clampedLabelCentre(expectedCentrePct, EXPECTED_BOX_PX, trackWidth);
    const clearance = (MID_BOX_PX + EXPECTED_BOX_PX) / 2 + LABEL_GUTTER_PX;
    if (Math.abs(midCentre - expectedCentre) < clearance) {
      showExpectedLabel = false;
    }
  }

  // The "soon" label sits immediately right of the "Today" label rather than
  // over its own pip: the pip is deliberately alongside the today marker, so a
  // centred label would always collide. Placed by the same clamp the "Today"
  // label uses, and dropped when the remaining track can't fit its box.
  const showSoonLabel = expectedSoon
    && (midLabelRight === null || trackWidth - midLabelRight - LABEL_GUTTER_PX >= EXPECTED_BOX_PX);

  const expectedStyle = expectedCentrePct === null ? null : {
    width: EXPECTED_BOX,
    maxWidth: '100%',
    left: `clamp(${EXPECTED_BOX_PX / 2}px, ${expectedCentrePct}%, calc(100% - ${EXPECTED_BOX_PX / 2}px))`,
    transform: 'translateX(-50%)',
    textAlign: 'center',
  };

  const soonLabelStyle = !expectedSoon ? null : {
    width: EXPECTED_BOX,
    left: `calc(clamp(${MID_HALF}, ${midPct}%, calc(100% - ${MID_HALF})) + ${MID_HALF} + ${LABEL_GUTTER_PX}px)`,
    textAlign: 'left',
  };

  const durationStr = duration !== null && businessDuration !== null
    ? `${duration} cal / ${businessDuration} bus. days`
    : null;
  const remainingStr = daysRemaining !== null && businessDaysRemaining !== null
    ? `${daysRemaining} cal / ${businessDaysRemaining} bus. days left`
    : null;

  // Note under the end date: total duration when the axis ends on the
  // determination itself, or an overdue/due-today flag when the deadline has
  // arrived.
  let endNote = null;
  let endNoteClass = 'text-gray-500';
  if (endIsOutcome && durationStr) {
    endNote = durationStr;
  } else if (overdue) {
    endNote = 'Overdue';
    endNoteClass = 'font-medium text-amber-600';
  } else if (dueToday) {
    endNote = 'Due today';
    endNoteClass = 'font-medium text-amber-600';
  }

  // No nowrap on labels so multi-word endpoint labels wrap within the fixed
  // column width on small screens instead of squeezing the track.
  const labelClass = SECTION_HEADING;
  const dateClass = 'text-xs sm:text-sm font-medium text-gray-900 whitespace-nowrap';
  // Every label sits its bottom this far above the line; every value sits its
  // top this far below it. Shared across endpoints and mid markers so the three
  // columns line up, with clear breathing room around the bar.
  const aboveLine = 'absolute bottom-1/2 mb-3';
  const belowLine = 'absolute top-1/2 mt-3';

  return (
    <div role="group" aria-label="Merger assessment timeline" className="flex items-stretch gap-2 sm:gap-4">
      {/* Start endpoint — outside the track, hugging it from the left */}
      <div className="relative w-20 sm:w-24 shrink-0 h-24">
        <span className={`${aboveLine} inset-x-0 text-right ${labelClass}`}>{startLabel}</span>
        <span className={`${belowLine} inset-x-0 text-right ${dateClass}`}>{formatDateMedium(startStr)}</span>
      </div>

      {/* Track region — the mid marker's label and value live inside it */}
      <div ref={trackRef} className="relative flex-1 min-w-0 h-24">
        {/* Mid marker label, above the line */}
        {midPct !== null && (
          <span
            className={`${aboveLine} ${
              midIsDetermination ? labelClass : 'text-xs font-semibold text-primary uppercase tracking-wider'
            }`}
            style={midStyle}
          >
            {midLabel}
          </span>
        )}

        {/* Expected-determination label. Suppressed when it would collide with
            the "Today" label above. */}
        {showExpectedLabel && (
          <span
            className={`${aboveLine} text-[10px] font-semibold text-phase-1-dark uppercase tracking-wider leading-tight`}
            style={expectedStyle}
          >
            Expected determination
          </span>
        )}

        {/* Same label once the forecast window has closed, tucked in beside the
            "Today" label. */}
        {showSoonLabel && (
          <span
            className={`${aboveLine} text-[10px] font-semibold text-phase-1-dark uppercase tracking-wider leading-tight`}
            style={soonLabelStyle}
          >
            Expected determination soon
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

          {/* Expected-determination band — a forecast, so it's shaded rather
              than marked with a dot, keeping actual events (which are dots)
              visually distinct from a prediction. Carries the phase 1 colour
              the rest of the site uses for that stage. */}
          {expectedLeftPct !== null && (
            <span
              className="absolute top-1/2 -translate-y-1/2 h-3 rounded-full bg-phase-1/50 cursor-help"
              style={{
                left: `${expectedLeftPct}%`,
                width: `${expectedWidthPct}%`,
                minWidth: `${MIN_BAND_PX}px`,
              }}
              title={expectedTitle}
              aria-label={expectedTitle}
            />
          )}

          {/* The same forecast once its window has closed: a pip just clear of
              the today marker, held inside the track's right edge. The forecast
              window is in the past at this point, so the date/band detail in
              expectedTitle would be describing a window we're already past —
              the hover just confirms the "soon" label instead. */}
          {expectedSoon && (
            <span
              className="absolute top-1/2 -translate-y-1/2 h-3 rounded-full bg-phase-1/50 cursor-help"
              style={{
                left: `min(calc(${midPct}% + ${SOON_PIP_GAP_PX}px), calc(100% - ${SOON_PIP_PX}px))`,
                width: `${SOON_PIP_PX}px`,
              }}
              title="Determination expected soon"
              aria-label="Determination expected soon"
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
            style={midStyle}
          >
            {midIsDetermination ? (
              <>
                <span className={`block ${dateClass}`}>{formatDateMedium(effectiveDeterminationDate)}</span>
                {durationStr && (
                  <span className="block text-[11px] font-normal text-gray-500">{durationStr}</span>
                )}
              </>
            ) : (
              remainingStr && (
                <span className="block text-[11px] font-normal text-gray-500">{remainingStr}</span>
              )
            )}
          </span>
        )}
      </div>

      {/* End endpoint — outside the track, hugging it from the right */}
      <div className="relative w-20 sm:w-24 shrink-0 h-24">
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
