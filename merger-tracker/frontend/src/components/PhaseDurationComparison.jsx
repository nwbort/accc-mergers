import { FaArrowUp, FaArrowDown } from 'react-icons/fa';

// A single metric (Average or Median) rendered as a pair of horizontal bars:
// this industry vs the parent in the ANZSIC hierarchy. Bars are scaled to the
// larger of the two so the comparison reads at a glance, with a delta chip
// spelling out how much longer/shorter this industry runs.
function MetricComparison({ label, current, parent, parentName }) {
  // No completed Phase 1 reviews here — nothing to plot.
  if (current == null) {
    return (
      <div>
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</p>
        <p className="text-sm text-gray-400 mt-2">No completed Phase 1 reviews</p>
      </div>
    );
  }

  const hasParent = parent != null && parentName;
  const max = Math.max(current, parent ?? 0) || 1;
  const currentWidth = (current / max) * 100;
  const parentWidth = hasParent ? (parent / max) * 100 : 0;

  // Delta vs parent: positive means this industry takes longer.
  const delta = hasParent ? current - parent : null;
  const pct = hasParent && parent > 0 ? Math.round((delta / parent) * 100) : null;

  let deltaChip = null;
  if (hasParent && delta !== 0) {
    const longer = delta > 0;
    deltaChip = (
      <span
        className={`inline-flex items-center gap-1 text-xs font-semibold ${
          longer ? 'text-amber-600' : 'text-emerald-600'
        }`}
      >
        {longer ? (
          <FaArrowUp className="w-2.5 h-2.5" aria-hidden="true" />
        ) : (
          <FaArrowDown className="w-2.5 h-2.5" aria-hidden="true" />
        )}
        {Math.abs(delta)} days {longer ? 'longer' : 'shorter'}
        {pct != null && pct !== 0 && <span className="text-gray-400">({Math.abs(pct)}%)</span>}
      </span>
    );
  } else if (hasParent) {
    deltaChip = <span className="text-xs font-medium text-gray-400">Same as parent</span>;
  }

  return (
    <div>
      <div className="flex items-center justify-between gap-2 mb-2.5">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</p>
        {deltaChip}
      </div>

      {/* This industry */}
      <div className="flex items-center gap-3">
        <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
          <div
            className="bg-primary h-2 rounded-full transition-all duration-300"
            style={{ width: `${currentWidth}%` }}
          />
        </div>
        <span className="text-sm font-bold text-gray-900 tabular-nums w-7 text-right">
          {current}
        </span>
      </div>
      <p className="text-[11px] text-gray-400 mt-1">This industry</p>

      {hasParent && (
        <>
          {/* Parent industry */}
          <div className="flex items-center gap-3 mt-3">
            <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
              <div
                className="bg-gray-300 h-2 rounded-full transition-all duration-300"
                style={{ width: `${parentWidth}%` }}
              />
            </div>
            <span className="text-sm font-semibold text-gray-500 tabular-nums w-7 text-right">
              {parent}
            </span>
          </div>
          <p className="text-[11px] text-gray-400 mt-1 truncate">{parentName}</p>
        </>
      )}
    </div>
  );
}

/**
 * Visual comparison of this industry's Phase 1 review durations against its
 * parent in the ANZSIC hierarchy. Values are business days, rounded.
 *
 * @param {object} props
 * @param {object|null} props.duration - this industry's `phase_duration`.
 * @param {object|null} props.parentDuration - the parent's `phase_duration`.
 * @param {string|null} props.parentName - parent display name (for labels).
 */
function PhaseDurationComparison({ duration, parentDuration, parentName }) {
  const round = (v) => (v != null ? Math.round(v) : null);

  const currentAvg = round(duration?.average_business_days);
  const currentMedian = round(duration?.median_business_days);
  const parentAvg = round(parentDuration?.average_business_days);
  const parentMedian = round(parentDuration?.median_business_days);

  const hasParent = parentName && (parentAvg != null || parentMedian != null);

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6">
      <div className="flex items-baseline justify-between gap-3 mb-5">
        <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider">
          Phase 1 duration
        </h2>
        <span className="text-[11px] text-gray-400">business days</span>
      </div>

      <div className="grid sm:grid-cols-2 gap-x-8 gap-y-6">
        <MetricComparison
          label="Average"
          current={currentAvg}
          parent={hasParent ? parentAvg : null}
          parentName={hasParent ? parentName : null}
        />
        <MetricComparison
          label="Median"
          current={currentMedian}
          parent={hasParent ? parentMedian : null}
          parentName={hasParent ? parentName : null}
        />
      </div>
    </div>
  );
}

export default PhaseDurationComparison;
