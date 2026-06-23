import { FaArrowUp, FaArrowDown } from 'react-icons/fa';

// A single horizontal bar with its value to the right and a caption (plus an
// optional delta chip) underneath.
function Bar({ widthPct, value, barClass, valueClass, caption, delta }) {
  return (
    <>
      <div className="flex items-center gap-3">
        <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
          <div
            className={`${barClass} h-2 rounded-full transition-all duration-300`}
            style={{ width: `${widthPct}%` }}
          />
        </div>
        <span className={`text-sm tabular-nums w-7 text-right ${valueClass}`}>
          {value}
        </span>
      </div>
      <div className="flex items-center justify-between gap-2 mt-1">
        <p className="text-[11px] text-gray-400 truncate">{caption}</p>
        {delta}
      </div>
    </>
  );
}

// Delta of this industry vs a baseline, as a small coloured chip. Positive
// means this industry runs longer than the baseline.
function DeltaChip({ current, comparison }) {
  if (comparison == null) return null;
  const delta = current - comparison;
  if (delta === 0) {
    return <span className="text-[11px] font-medium text-gray-400 shrink-0">Same</span>;
  }
  const longer = delta > 0;
  const pct = comparison > 0 ? Math.round((delta / comparison) * 100) : null;
  return (
    <span
      className={`inline-flex items-center gap-1 text-[11px] font-semibold shrink-0 ${
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
}

// A single metric (Average or Median) rendered as a stack of horizontal bars:
// this industry on top, then one bar per comparison baseline (its parent in the
// ANZSIC hierarchy and/or all industries). Bars are scaled to the largest value
// so the comparison reads at a glance, and each baseline carries a delta chip
// spelling out how much longer/shorter this industry runs.
function MetricComparison({ label, current, comparisons }) {
  // No completed Phase 1 reviews here — nothing to plot.
  if (current == null) {
    return (
      <div>
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</p>
        <p className="text-sm text-gray-400 mt-2">No completed Phase 1 reviews</p>
      </div>
    );
  }

  const active = comparisons.filter((c) => c.value != null);
  const max = Math.max(current, ...active.map((c) => c.value)) || 1;

  // Distinct shades so stacked baseline bars read apart from one another.
  const barShades = ['bg-gray-400', 'bg-gray-300'];

  return (
    <div>
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2.5">
        {label}
      </p>

      {/* This industry */}
      <Bar
        widthPct={(current / max) * 100}
        value={current}
        barClass="bg-primary"
        valueClass="font-bold text-gray-900"
        caption="This industry"
      />

      {/* One bar per baseline (parent industry, all industries). */}
      {active.map((c, i) => (
        <div key={c.name} className="mt-3">
          <Bar
            widthPct={(c.value / max) * 100}
            value={c.value}
            barClass={barShades[i] || 'bg-gray-300'}
            valueClass="font-semibold text-gray-500"
            caption={c.name}
            delta={<DeltaChip current={current} comparison={c.value} />}
          />
        </div>
      ))}
    </div>
  );
}

/**
 * Visual comparison of this industry's Phase 1 review durations against one or
 * more baselines — its parent in the ANZSIC hierarchy and/or all industries.
 * Values are business days, rounded.
 *
 * @param {object} props
 * @param {object|null} props.duration - this industry's `phase_duration`.
 * @param {Array<{name: string, duration: object|null}>} [props.comparisons] -
 *   ordered baselines to plot beneath this industry (e.g. parent then overall).
 */
function PhaseDurationComparison({ duration, comparisons = [] }) {
  const round = (v) => (v != null ? Math.round(v) : null);

  const currentAvg = round(duration?.average_business_days);
  const currentMedian = round(duration?.median_business_days);

  // Project the baselines onto each metric, dropping any without a usable value.
  const toMetric = (key) =>
    comparisons
      .filter((c) => c.name)
      .map((c) => ({ name: c.name, value: round(c.duration?.[key]) }));

  const avgComparisons = toMetric('average_business_days');
  const medianComparisons = toMetric('median_business_days');

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
          comparisons={avgComparisons}
        />
        <MetricComparison
          label="Median"
          current={currentMedian}
          comparisons={medianComparisons}
        />
      </div>
    </div>
  );
}

export default PhaseDurationComparison;
