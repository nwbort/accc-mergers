import { Link } from 'react-router-dom';
import { differenceInCalendarDays, parseISO, isValid } from 'date-fns';
import { mergerPath } from '../utils/slug';
import { formatDateMedium } from '../utils/dates';

// Clamp a milestone's position to a [0, 100] percentage of the referral →
// deadline span, so a milestone that lands before/after the span (bad data,
// clock restarts) still renders inside the bar rather than breaking layout.
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

function InferredBadge() {
  return (
    <span
      className="inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-medium bg-amber-50 text-amber-700 border-amber-200/60"
      title="Inferred from Phase 2 notice — the ACCC register hasn't updated the stage field yet"
    >
      Inferred
    </span>
  );
}

function MatterBar({ matter }) {
  const { merger_id, merger_name, referral_date, nocc_date, nocc_issued, end_of_determination_period, phase_2_inferred } = matter;

  const todayPercent = percentAlong(new Date().toISOString(), referral_date, end_of_determination_period);
  const noccPercent = percentAlong(nocc_date, referral_date, end_of_determination_period);

  return (
    <li className="py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 mb-2">
        <Link
          to={mergerPath(merger_id, merger_name)}
          className="text-sm font-semibold text-gray-900 hover:text-primary transition-colors truncate"
        >
          {merger_name}
        </Link>
        <div className="flex items-center gap-2 shrink-0">
          {phase_2_inferred && <InferredBadge />}
          <span className="text-xs text-gray-500">{merger_id}</span>
        </div>
      </div>

      <div className="relative h-3 rounded-full bg-phase-2-pale" role="img" aria-label={`Phase 2 timeline for ${merger_name}, from referral ${formatDateMedium(referral_date)} to determination due ${formatDateMedium(end_of_determination_period)}`}>
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
            className={`absolute top-1/2 -translate-y-1/2 h-2.5 w-2.5 rounded-full ring-2 ring-white ${nocc_issued ? 'bg-phase-2-dark' : 'bg-gray-400'}`}
            style={{ left: `calc(${noccPercent}% - 5px)` }}
            title={`${nocc_issued ? 'NOCC issued' : 'NOCC due'}: ${formatDateMedium(nocc_date)}`}
          />
        )}
      </div>

      <div className="mt-1.5 flex flex-wrap justify-between gap-x-3 text-xs text-gray-500">
        <span>Referred {formatDateMedium(referral_date)}</span>
        {nocc_date && (
          <span>{nocc_issued ? 'NOCC issued' : 'NOCC due'} {formatDateMedium(nocc_date)}</span>
        )}
        <span>Determination due {formatDateMedium(end_of_determination_period)}</span>
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
