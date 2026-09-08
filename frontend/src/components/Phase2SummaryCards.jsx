import { FaLayerGroup, FaHourglassHalf } from 'react-icons/fa6';
import StatCard from './StatCard';
import { getOutcomeDot } from '../constants/outcomeDotColors';
import { summarisePhase2 } from '../utils/phase2Summary';
import { CARD } from '../utils/classNames';

// The status cards above the Phase 2 tracker: how many matters have been
// referred, how long a review runs, and how the concluded reviews split by
// outcome. Everything is derived from phase2.json (see utils/phase2Summary.js)
// so the cards can never drift from the matters listed underneath them.
//
// The split's segments and legend dots take the site-wide outcome colours, the
// same families as the determination-coloured cards further down the page.
function Phase2SummaryCards({ current = [], completed = [] }) {
  const {
    total,
    currentCount,
    completedCount,
    outcomes,
    averageDays,
    averageBasis,
    ceasedCount,
  } = summarisePhase2(current, completed);

  if (total === 0) return null;

  const averageSubtitle = averageDays === null
    ? 'No determination has been handed down yet'
    : `Referral to determination, across ${averageBasis} matter${averageBasis === 1 ? '' : 's'}${
        ceasedCount > 0 ? ` · ${ceasedCount} ceased excluded` : ''
      }`;

  return (
    <section aria-labelledby="phase2-summary-heading" className="mb-8">
      <h2 id="phase2-summary-heading" className="sr-only">
        Phase 2 at a glance
      </h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <StatCard
          title="Referred to Phase 2"
          value={total}
          subtitle={`${currentCount} still running · ${completedCount} completed`}
          icon={<FaLayerGroup />}
        />
        <StatCard
          title="Average time in Phase 2"
          value={averageDays === null ? 'N/A' : `${averageDays} days`}
          subtitle={averageSubtitle}
          icon={<FaHourglassHalf />}
        />
      </div>

      <div className={`${CARD} mt-4 p-6`}>
        <p className="text-sm font-medium text-gray-500 leading-5">
          Outcomes of completed reviews
        </p>
        {completedCount === 0 ? (
          <p className="mt-2 text-sm text-gray-500">No Phase 2 review has concluded yet.</p>
        ) : (
          <>
            {/* Decorative: every segment is spelled out in the list below, so
                the bar would only repeat it to a screen reader. */}
            <div
              className="mt-3 flex h-2.5 w-full overflow-hidden rounded-full bg-gray-100"
              aria-hidden="true"
            >
              {outcomes.map((outcome) => (
                <div
                  key={outcome.label}
                  className={`h-full ${getOutcomeDot({ determination: outcome.label }).dot}`}
                  style={{ width: `${(outcome.count / completedCount) * 100}%` }}
                />
              ))}
            </div>
            <ul className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-2">
              {outcomes.map((outcome) => (
                <li key={outcome.label} className="flex items-baseline gap-2 text-sm">
                  <span className="flex min-w-0 items-baseline gap-2 text-gray-700">
                    <span
                      className={`h-2.5 w-2.5 flex-shrink-0 translate-y-px rounded-full ${
                        getOutcomeDot({ determination: outcome.label }).dot
                      }`}
                    />
                    <span className="truncate">{outcome.label}</span>
                  </span>
                  <span className="whitespace-nowrap tabular-nums text-gray-500">
                    {outcome.count} · {outcome.share}%
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </section>
  );
}

export default Phase2SummaryCards;
