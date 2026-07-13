import { Link } from 'react-router-dom';
import { differenceInCalendarDays, parseISO, isValid } from 'date-fns';
import { mergerPath } from '../utils/slug';
import { formatDateMedium } from '../utils/dates';

// Position of `date` along the referral -> deadline axis, clamped to [0, 100]
// so a milestone that lands before/after the span (bad data, clock restarts)
// still renders inside the bar rather than breaking layout.
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

// The NOCC label sits in a fixed-width box centred on its dot — the same
// technique MergerTimeline uses for its mid-axis label: the box's centre is
// clamped to stay NOCC_HALF in from each track end, so it tracks the dot
// through the middle of the track and, near an edge, stops there while the
// dot keeps going — never overlapping the referred / determination-due end
// labels, and (unlike a width-relative translate) behaves the same on a
// narrow mobile track.
const NOCC_BOX = '9.5rem';
const NOCC_HALF = '4.75rem';
const NOCC_EDGE_ALIGN = 10; // within this % of an end, align text to that end

// Every label sits its bottom this far above the line; every date sits its
// top this far below it, shared across the start/track/end columns so they
// line up (mirrors MergerTimeline's aboveLine/belowLine).
const ABOVE_LINE = 'absolute bottom-1/2 mb-2';
const BELOW_LINE = 'absolute top-1/2 mt-2';

function MatterBar({ matter }) {
  const { merger_id, merger_name, referral_date, nocc_date, nocc_issued, end_of_determination_period } = matter;

  const todayPercent = percentAlong(new Date().toISOString(), referral_date, end_of_determination_period);
  const noccPercent = percentAlong(nocc_date, referral_date, end_of_determination_period);

  const noccLabelStyle = noccPercent === null ? null : {
    width: NOCC_BOX,
    maxWidth: '100%',
    left: `clamp(${NOCC_HALF}, ${noccPercent}%, calc(100% - ${NOCC_HALF}))`,
    transform: 'translateX(-50%)',
    textAlign: noccPercent < NOCC_EDGE_ALIGN ? 'left' : noccPercent > 100 - NOCC_EDGE_ALIGN ? 'right' : 'center',
  };

  return (
    <li className="group relative -mx-3 rounded-xl px-3 py-4 transition-colors hover:bg-gray-50/70 first:pt-0 last:pb-0">
      <Link
        to={mergerPath(merger_id, merger_name)}
        className="block text-sm font-semibold text-gray-900 transition-colors truncate mb-3 group-hover:text-primary after:absolute after:inset-0"
      >
        {merger_name}
      </Link>

      <div className="flex items-stretch gap-2 sm:gap-4">
        {/* Start endpoint — outside the track, hugging it from the left */}
        <div className="relative w-16 sm:w-20 shrink-0 h-11">
          <span className={`${ABOVE_LINE} inset-x-0 text-right text-[11px] font-medium text-gray-500`}>Referred</span>
          <span className={`${BELOW_LINE} inset-x-0 text-right text-xs font-medium text-gray-900`}>{formatDateMedium(referral_date)}</span>
        </div>

        {/* Track region — the NOCC label lives inside it, above the line */}
        <div className="relative flex-1 min-w-0 h-11">
          {noccPercent !== null && nocc_date && (
            <span
              className={`${ABOVE_LINE} text-[11px] text-gray-500 whitespace-nowrap`}
              style={noccLabelStyle}
            >
              {nocc_issued ? 'NOCC issued' : 'NOCC due'} {formatDateMedium(nocc_date)}
            </span>
          )}

          <div
            className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-3 rounded-full bg-phase-2-pale"
            role="img"
            aria-label={`Phase 2 timeline for ${merger_name}, from referral ${formatDateMedium(referral_date)} to determination ${formatDateMedium(end_of_determination_period)}`}
          >
            <div className="absolute inset-0 rounded-full bg-phase-2/25" />

            {todayPercent !== null && (
              <div
                className="absolute top-1/2 -translate-y-1/2 h-5 w-0.5 bg-gray-900"
                style={{ left: `${todayPercent}%` }}
                title="Today"
              />
            )}

            {noccPercent !== null && (
              <div
                className={`absolute top-1/2 h-2.5 w-2.5 rounded-full ring-2 ring-white ${nocc_issued ? 'bg-phase-2-dark' : 'bg-gray-400'}`}
                style={{ left: `${noccPercent}%`, transform: 'translate(-50%, -50%)' }}
                title={`${nocc_issued ? 'NOCC issued' : 'NOCC due'}: ${formatDateMedium(nocc_date)}`}
              />
            )}
          </div>
        </div>

        {/* End endpoint — outside the track, hugging it from the right */}
        <div className="relative w-16 sm:w-20 shrink-0 h-11">
          <span className={`${ABOVE_LINE} inset-x-0 text-left text-[11px] font-medium text-gray-500`}>Determination</span>
          <span className={`${BELOW_LINE} inset-x-0 text-left text-xs font-medium text-gray-900`}>{formatDateMedium(end_of_determination_period)}</span>
        </div>
      </div>
    </li>
  );
}

function Phase2Timeline({ matters }) {
  if (!matters || matters.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6">
        <p className="text-gray-500 text-sm">No matters are currently in Phase 2.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-5 sm:p-6">
      <ul className="divide-y divide-gray-100">
        {matters.map((matter) => (
          <MatterBar key={matter.merger_id} matter={matter} />
        ))}
      </ul>
    </div>
  );
}

export default Phase2Timeline;
