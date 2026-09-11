import { useState } from 'react';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import SEO from '../components/SEO';
import TurnaroundTrendChart from '../components/TurnaroundTrendChart';
import DurationEcdfChart from '../components/DurationEcdfChart';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { formatMedian } from '../utils/formatMedian';
import { CARD, SECTION_HEADING } from '../utils/classNames';
import { STATIC_PAGE_META } from '../utils/pageMeta';
import { computeEcdfFromCounts } from '../utils/durationEcdf';
import { CHART_PALETTE as COLORS } from '../constants/chartColors';
import { PHASE_1_DEADLINE_BD, WAIVER_DEADLINE_BD } from '../constants/statutoryDeadlines';

// Title and description live in the shared table so this page and the
// build-time prerenderer emit the same <head>.
const PAGE_META = STATIC_PAGE_META['/current-status'];

/**
 * The comparison against the all-time median, split so only the part that
 * carries the direction takes the colour: "5 business days slower" is the
 * finding, "than usual" is just grammar and reads better left neutral.
 *
 * Returns null when there's no baseline to compare against.
 */
function deltaSentence(delta) {
  if (delta === null || delta === undefined) return null;
  if (delta === 0) return { lead: 'About the same as usual', tail: null };
  const magnitude = Math.abs(delta);
  const unit = magnitude === 1 ? 'business day' : 'business days';
  return {
    lead: `${formatMedian(magnitude)} ${unit} ${delta > 0 ? 'slower' : 'faster'}`,
    tail: 'than usual',
  };
}

/**
 * One headline duration, coloured by how it sits against the all-time median.
 *
 * Slower than usual is the adverse direction for a reader planning a deal, so
 * it takes the site's declined red and faster takes the cleared green — both
 * the `dark` shade, the one that clears 4.5:1 as text (see docs/accessibility).
 */
function Headline({ label, value, delta, footnote }) {
  const sentence = deltaSentence(delta);
  const tone = !delta ? 'text-gray-900' : delta > 0 ? 'text-declined-dark' : 'text-cleared-dark';

  return (
    <div className="p-6">
      <p className={SECTION_HEADING}>{label}</p>
      {value === null ? (
        <p className="text-sm text-gray-500 mt-3">Nothing decided in this window.</p>
      ) : (
        <>
          <div className="flex items-baseline gap-2 mt-2 flex-wrap">
            <p className={`text-5xl font-bold tracking-tight leading-none ${tone}`}>
              {formatMedian(value)}
            </p>
            <p className="text-sm text-gray-500">business days</p>
          </div>
          {sentence && (
            <p className="mt-3 text-sm">
              <span className={`font-medium ${tone}`}>{sentence.lead}</span>
              {sentence.tail && <span className="text-gray-500"> {sentence.tail}</span>}
            </p>
          )}
          {footnote && <p className="mt-2 text-sm text-gray-500">{footnote}</p>}
        </>
      )}
    </div>
  );
}

/**
 * One window's duration curve, in the same card frame as the trend chart.
 *
 * The /analysis page draws this curve over every matter ever decided; here it
 * is cut to the matters decided in the selected window, which is what makes it
 * worth showing twice. The median headline above says where the middle of that
 * window landed; this says how the rest of it was spread — whether the tail
 * ran past the statutory clock, and by how much.
 *
 * Renders nothing when the window holds no decisions, or when the payload
 * predates the per-window histogram.
 */
function EcdfCard({ title, stats, deadline, color, seriesLabel, caption, countHeading, id }) {
  const points = computeEcdfFromCounts(stats?.duration_histogram);
  if (points.length === 0) return null;

  return (
    <section className="mb-6">
      <div className={`${CARD} overflow-hidden`}>
        <div className="px-6 py-5 border-b border-gray-100">
          <h2 id={`${id}-title`} className="text-base font-semibold text-gray-900">
            {title}
          </h2>
        </div>
        <div className="p-6">
          <DurationEcdfChart
            points={points}
            median={stats.median}
            deadline={deadline}
            dayLabel="business days"
            seriesLabel={seriesLabel}
            color={color}
            titleId={`${id}-title`}
            summaryId={`${id}-summary`}
            caption={caption}
            countHeading={countHeading}
            minAxisMax={deadline}
          />
        </div>
      </div>
    </section>
  );
}

function CurrentStatus() {
  const { data, loading, error } = useFetchData(API_ENDPOINTS.analysis, {
    cacheKey: 'analysis-data',
  });
  const [windowDays, setWindowDays] = useState(30);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;
  if (!data) return null;

  const play = data.current_status;

  // The whole page is this one block, so an analysis.json generated before it
  // existed gets a plain message rather than a broken render.
  if (!play?.windows?.length) {
    return (
      <>
        <SEO title={PAGE_META.title} description={PAGE_META.description} url="/current-status" />
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
            Current status
          </h1>
          <p className="mt-3 text-sm text-gray-600">
            This page is still being generated. Please check back shortly.
          </p>
        </div>
      </>
    );
  }

  const entry = play.windows.find(w => w.days === windowDays) || play.windows[0];
  const pre = play.pre_notification?.windows?.find(w => w.days === entry.days) ?? null;

  return (
    <>
      <SEO title={PAGE_META.title} description={PAGE_META.description} url="/current-status" />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
            Current status
          </h1>
          <div
            className="inline-flex items-center bg-gray-100 rounded-full p-0.5 text-sm"
            role="group"
            aria-label="Window"
          >
            {play.windows.map(w => (
              <button
                key={w.days}
                onClick={() => setWindowDays(w.days)}
                aria-pressed={entry.days === w.days}
                className={`px-3.5 py-1.5 rounded-full font-medium transition-all duration-150 ${entry.days === w.days ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
              >
                Last {w.days} days
              </button>
            ))}
          </div>
        </header>

        <div className={`${CARD} overflow-hidden mb-6`}>
          <div className="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-gray-100">
            <Headline
              label="Waiver"
              value={entry.waivers.median}
              delta={entry.waivers.median_delta}
              footnote={entry.waivers.p90 != null ? `90% within ${entry.waivers.p90} BD` : null}
            />
            <Headline
              label="Notification – phase 1"
              value={entry.notifications.median}
              delta={entry.notifications.median_delta}
              footnote={entry.notifications.p90 != null ? `90% within ${entry.notifications.p90} BD` : null}
            />
          </div>
          {pre && pre.median !== null && (
            <p className="border-t border-gray-100 bg-gray-50/60 px-6 py-4 text-sm text-gray-700">
              Average <strong>{formatMedian(pre.median)} business days</strong> in pre-notification
            </p>
          )}
        </div>

        <EcdfCard
          id="chart-window-waiver-ecdf"
          title={`Waiver duration \u2013 share of applications concluded \u2013 last ${entry.days} days \u2013 ${entry.waivers.count} applications`}
          stats={entry.waivers}
          deadline={WAIVER_DEADLINE_BD}
          color={COLORS.teal}
          seriesLabel="% of waivers concluded"
          caption={`Cumulative share of the waiver applications decided in the last ${entry.days} days, by business day`}
          countHeading="Waivers decided"
        />

        <EcdfCard
          id="chart-window-phase1-ecdf"
          title={`Phase 1 duration \u2013 share of reviews concluded \u2013 last ${entry.days} days \u2013 ${entry.notifications.count} reviews`}
          stats={entry.notifications}
          deadline={PHASE_1_DEADLINE_BD}
          color={COLORS.primary}
          seriesLabel="% of reviews concluded"
          caption={`Cumulative share of the phase 1 reviews completed in the last ${entry.days} days, by business day`}
          countHeading="Reviews concluded"
        />

        <section>
          <div className={`${CARD} overflow-hidden`}>
            <div className="px-6 py-5 border-b border-gray-100">
              <h2 id="chart-turnaround-trend-title" className="text-base font-semibold text-gray-900">
                ACCC decision times &ndash; phase 1 and waivers
              </h2>
            </div>
            <div className="p-6">
              <TurnaroundTrendChart monthly={play.monthly} />
            </div>
          </div>
        </section>
      </div>
    </>
  );
}

export default CurrentStatus;
