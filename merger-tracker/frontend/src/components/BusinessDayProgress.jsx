import { getBusinessDayProgress } from '../utils/businessDayProgress';

/**
 * Slim progress bar + "Business day X of Y" label for the merger detail
 * header. Renders nothing when the merger isn't an in-progress non-waiver
 * assessment (see getBusinessDayProgress).
 */
function BusinessDayProgress({ merger }) {
  const progress = getBusinessDayProgress(merger);
  if (!progress) return null;

  const { elapsed, total, overdue } = progress;
  const pct = Math.min(100, (elapsed / total) * 100);

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className={`text-xs font-medium ${overdue ? 'text-amber-600' : 'text-gray-500'}`}>
          {overdue ? 'Determination overdue' : `Business day ${elapsed} of ${total}`}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div
          className={`h-full rounded-full ${overdue ? 'bg-amber-500' : 'bg-primary'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Compact "BD X/Y" text chip for list cards — no bar, to avoid clutter.
 */
export function BusinessDayChip({ merger, className = '' }) {
  const progress = getBusinessDayProgress(merger);
  if (!progress) return null;

  const { elapsed, total, overdue } = progress;

  return (
    <span
      className={`inline-flex items-center text-xs font-medium ${overdue ? 'text-amber-600' : 'text-gray-500'} ${className}`}
    >
      {overdue ? 'Overdue' : `BD ${elapsed}/${total}`}
    </span>
  );
}

export default BusinessDayProgress;
