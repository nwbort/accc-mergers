import { useState } from 'react';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import SEO from '../components/SEO';
import TurnaroundTrendChart from '../components/TurnaroundTrendChart';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { formatMedian } from '../utils/formatMedian';
import { CARD, SECTION_HEADING } from '../utils/classNames';
import { STATIC_PAGE_META } from '../utils/pageMeta';

// Title and description live in the shared table so this page and the
// build-time prerenderer emit the same <head>.
const PAGE_META = STATIC_PAGE_META['/current-status'];

/** "5 business days slower than usual", or null when there's no baseline. */
function deltaSentence(delta) {
  if (delta === null || delta === undefined) return null;
  if (delta === 0) return 'About the same as usual';
  const magnitude = Math.abs(delta);
  const unit = magnitude === 1 ? 'business day' : 'business days';
  return `${formatMedian(magnitude)} ${unit} ${delta > 0 ? 'slower' : 'faster'} than usual`;
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
          {sentence && <p className={`mt-3 text-sm font-medium ${tone}`}>{sentence}</p>}
          {footnote && <p className="mt-2 text-sm text-gray-500">{footnote}</p>}
        </>
      )}
    </div>
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
              Average <strong>{formatMedian(pre.median)} calendar days</strong> in pre-notification
            </p>
          )}
        </div>

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
