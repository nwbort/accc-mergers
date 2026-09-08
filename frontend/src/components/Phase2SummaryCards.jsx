import { FaLayerGroup, FaHourglassHalf } from 'react-icons/fa6';
import StatCard from './StatCard';
import { CHART_PALETTE_ORDER, DETERMINATION_COLORS } from '../constants/chartColors';
import { summarisePhase2 } from '../utils/phase2Summary';
import { CARD } from '../utils/classNames';

// The status cards above the Phase 2 tracker: how many matters have been
// referred, how long a review runs, and how the concluded reviews split by
// outcome. Everything is derived from phase2.json (see utils/phase2Summary.js)
// so the cards can never drift from the matters listed underneath them.
//
// The two figure cards carry a number and nothing else — the lists below are
// where a reader goes for the detail — so they drop StatCard's two-line label
// reserve, which would otherwise leave a gap under a one-line title.
//
// The split's segments and legend dots take the determination colours the
// dashboard's Phase 2 doughnut is drawn with — the same breakdown of the same
// matters, so the two should agree — rather than the fills of the cards
// further down this page. That table is the one with a colour for a clearance
// granted subject to conditions: a muted green a clear step off the outright
// approval green, so the two clearances read as distinct without reading as
// unrelated outcomes.
function Phase2SummaryCards({ current = [], completed = [] }) {
  const { total, completedCount, outcomes, averageDays } = summarisePhase2(current, completed);

  if (total === 0) return null;

  const colourFor = (label, i) =>
    DETERMINATION_COLORS[label] || CHART_PALETTE_ORDER[i % CHART_PALETTE_ORDER.length];

  return (
    <section aria-labelledby="phase2-summary-heading" className="mb-8">
      <h2 id="phase2-summary-heading" className="sr-only">
        Phase 2 at a glance
      </h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <StatCard
          title="Referred to Phase 2"
          value={total}
          icon={<FaLayerGroup />}
          reserveTitleLines={false}
        />
        <StatCard
          title="Average time in Phase 2"
          value={averageDays === null ? 'N/A' : `${averageDays} days`}
          icon={<FaHourglassHalf />}
          reserveTitleLines={false}
        />
      </div>

      <div className={`${CARD} mt-4 p-6`}>
        <p className="text-sm font-medium text-gray-500 leading-5">
          Outcomes of Phase 2 reviews
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
              {outcomes.map((outcome, i) => (
                <div
                  key={outcome.label}
                  className="h-full"
                  style={{
                    width: `${(outcome.count / completedCount) * 100}%`,
                    backgroundColor: colourFor(outcome.label, i),
                  }}
                />
              ))}
            </div>
            <ul className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-2">
              {outcomes.map((outcome, i) => (
                <li key={outcome.label} className="flex items-baseline gap-2 text-sm">
                  <span className="flex min-w-0 items-baseline gap-2 text-gray-700">
                    <span
                      className="h-2.5 w-2.5 flex-shrink-0 translate-y-px rounded-full"
                      style={{ backgroundColor: colourFor(outcome.label, i) }}
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
