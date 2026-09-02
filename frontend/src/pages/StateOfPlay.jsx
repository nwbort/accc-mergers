import { useState } from 'react';
import { Link } from 'react-router';
import { FaFileImport, FaLayerGroup, FaGavel } from 'react-icons/fa6';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import StatCard from '../components/StatCard';
import SEO from '../components/SEO';
import TurnaroundTrendChart from '../components/TurnaroundTrendChart';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { formatDateMedium } from '../utils/dates';
import { formatMedian } from '../utils/formatMedian';
import { CARD, SECTION_HEADING } from '../utils/classNames';
import { STATIC_PAGE_META } from '../utils/pageMeta';

// Title and description live in the shared table so this page and the
// build-time prerenderer emit the same <head>.
const PAGE_META = STATIC_PAGE_META['/state-of-play'];

const PANELS = [
  {
    key: 'notifications',
    label: 'Notifications – phase 1',
    measured: 'Measured from notification to the end of phase 1 — the referral date for a matter sent to phase 2, so the phase 2 clock never inflates the figure.',
  },
  {
    key: 'waivers',
    label: 'Waivers',
    measured: 'Measured from application to determination. Waivers have no statutory clock.',
  },
];

/** One review type's recent turnaround, against its all-time median. */
function TurnaroundPanel({ label, measured, recent, baseline, days }) {
  if (recent.median === null) {
    return (
      <div className="p-6">
        <p className={SECTION_HEADING}>{label}</p>
        <p className="text-sm text-gray-500 mt-3">
          No matters decided in the last {days} days.
        </p>
      </div>
    );
  }

  const slower = recent.median_delta > 0;
  return (
    <div className="p-6">
      <p className={SECTION_HEADING}>{label}</p>
      <div className="flex items-baseline gap-2 mt-1.5 flex-wrap">
        <p className="text-4xl font-bold text-gray-900 tracking-tight">
          {formatMedian(recent.median)}
        </p>
        <p className="text-sm text-gray-500">median business days</p>
      </div>
      <p className="text-sm text-gray-600 mt-2">
        {recent.median_delta === null || recent.median_delta === 0 ? (
          <>In line with the all-time median of {formatMedian(baseline.median)} BD</>
        ) : (
          <>
            {/* Deltas render in plain dark text rather than red/green: a
                duration moving is not an approved/declined outcome, and
                borrowing that palette would imply a verdict. The words
                carry the direction. */}
            <span className="font-semibold text-gray-900">
              {slower ? '+' : '−'}{formatMedian(Math.abs(recent.median_delta))} BD
            </span>{' '}
            {slower ? 'slower' : 'faster'} than the all-time median of{' '}
            {formatMedian(baseline.median)} BD
          </>
        )}
      </p>
      <dl className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-2 gap-y-2 text-sm">
        <dt className="text-gray-500">9 in 10 within</dt>
        <dd className="text-gray-900 font-medium text-right">{recent.p90} BD</dd>
        <dt className="text-gray-500">Range</dt>
        <dd className="text-gray-900 font-medium text-right">{recent.min}–{recent.max} BD</dd>
        <dt className="text-gray-500">Decided in window</dt>
        <dd className="text-gray-900 font-medium text-right">{recent.count}</dd>
        <dt className="text-gray-500">All-time median</dt>
        <dd className="text-gray-900 font-medium text-right">
          {formatMedian(baseline.median)} BD <span className="text-gray-500 font-normal">({baseline.count})</span>
        </dd>
      </dl>
      <p className="text-xs text-gray-500 mt-4">{measured}</p>
    </div>
  );
}

function StateOfPlay() {
  const { data, loading, error } = useFetchData(API_ENDPOINTS.analysis, {
    cacheKey: 'analysis-data',
  });
  const [windowDays, setWindowDays] = useState(30);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;
  if (!data) return null;

  const play = data.state_of_play;
  const caseload = data.open_caseload;

  // The whole page is this one block, so an analysis.json generated before it
  // existed gets a plain message rather than a broken render.
  if (!play?.windows?.length) {
    return (
      <>
        <SEO title={PAGE_META.title} description={PAGE_META.description} url="/state-of-play" />
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
            State of play
          </h1>
          <p className="mt-3 text-sm text-gray-600">
            This page is still being generated. Please check back shortly.
          </p>
        </div>
      </>
    );
  }

  const entry = play.windows.find(w => w.days === windowDays) || play.windows[0];
  const asAtLabel = play.as_at ? formatDateMedium(play.as_at) : null;
  const decided = entry.notifications.count + entry.waivers.count;

  // Movement in the queue over roughly six months, matching the framing the
  // analysis page's caseload chart uses. Falls back to the start of the series
  // while less than six months of it exists.
  let caseloadNow = null;
  let caseloadDelta = null;
  if (caseload?.notifications?.length) {
    const last = caseload.notifications.length - 1;
    caseloadNow = caseload.notifications[last];
    const compare = Math.max(0, last - 6);
    if (compare !== last) caseloadDelta = caseloadNow - caseload.notifications[compare];
  }

  return (
    <>
      <SEO title={PAGE_META.title} description={PAGE_META.description} url="/state-of-play" />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <header className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
            State of play
          </h1>
          <p className="mt-3 max-w-3xl text-sm text-gray-600 leading-relaxed">
            How the ACCC&rsquo;s merger review is running <strong>right now</strong>, and how that
            compares to its all-time baseline. The medians published elsewhere on this site pool
            every matter ever decided — the right baseline, but not the number to quote at filing
            time, because the register only opened in 2026 and throughput has moved as the regime
            bedded in. Everything below is cut from matters <strong>decided</strong> in the last
            30 or 90 days.
            {asAtLabel && <> As at <strong>{asAtLabel}</strong>.</>}
          </p>
        </header>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          <StatCard
            title={`Notifications filed (last ${entry.days} days)`}
            value={entry.notifications_filed}
            subtitle="New matters arriving"
            icon={<FaFileImport />}
          />
          <StatCard
            title="Open caseload"
            value={caseloadNow ?? '—'}
            subtitle={
              caseloadDelta === null
                ? 'Notifications still before the ACCC'
                : `${caseloadDelta > 0 ? '+' : ''}${caseloadDelta} over ~6 months`
            }
            icon={<FaLayerGroup />}
            href="/analysis"
          />
          <StatCard
            title={`Decisions published (last ${entry.days} days)`}
            value={decided}
            subtitle={`${entry.notifications.count} notifications, ${entry.waivers.count} waivers`}
            icon={<FaGavel />}
          />
        </div>

        <section className="mb-8">
          <div className={`${CARD} overflow-hidden`}>
            <div className="px-6 py-5 border-b border-gray-100 flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-gray-900">Time to decide</h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  What matters decided recently actually took, against the all-time median
                </p>
              </div>
              <div
                className="inline-flex items-center bg-gray-100 rounded-full p-0.5 text-sm"
                role="group"
                aria-label="Turnaround window"
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
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-gray-100">
              {PANELS.map(({ key, label, measured }) => (
                <TurnaroundPanel
                  key={key}
                  label={label}
                  measured={measured}
                  recent={entry[key]}
                  baseline={play.all_time[key]}
                  days={entry.days}
                />
              ))}
            </div>
          </div>
        </section>

        <section className="mb-8">
          <div className={`${CARD} overflow-hidden`}>
            <div className="px-6 py-5 border-b border-gray-100">
              <h2 id="chart-turnaround-trend-title" className="text-base font-semibold text-gray-900">
                Turnaround against open caseload
              </h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Median time to decide, by the month the decision landed, plotted against the
                notifications still on the ACCC&rsquo;s books at each month end
              </p>
            </div>
            <div className="p-6">
              <TurnaroundTrendChart monthly={play.monthly} />
              <p className="text-xs text-gray-500 mt-3">
                Matters are counted in the month they were <em>decided</em>, not the month they
                were filed, so each point reflects what the ACCC was turning around at the time. A
                month with fewer than five decisions is left unplotted rather than charted off one
                or two matters.
              </p>
            </div>
          </div>
        </section>

        <div className={`${CARD} p-5 sm:p-6`}>
          <h2 className="text-base font-semibold text-gray-900">Reading these numbers</h2>
          <ul className="mt-3 space-y-2.5 text-sm text-gray-600 leading-relaxed list-disc pl-5">
            <li>
              <strong>The window is by decision date, not filing date.</strong> A matter counts
              towards the period it was decided in. Bucketing by filing date would leave recent
              months structurally incomplete, since matters filed in them that are still open have
              no duration yet — understating turnaround exactly where it matters most.
            </li>
            <li>
              <strong>The median is not the promise.</strong> Half of matters take longer. The
              &ldquo;9 in 10 within&rdquo; figure is the one to quote when a client needs a date
              they can rely on.
            </li>
            <li>
              <strong>Only notification inflow is shown.</strong> Waiver applications reach the
              register only once they have been decided, so a count of waivers
              <em> filed</em> recently would be missing every application still in front of the
              ACCC. For the same reason the caseload line covers notifications only.
            </li>
            <li>
              <strong>No correlation figure is published</strong> for turnaround against caseload.
              Both series trend over the register&rsquo;s short life, so any coefficient would
              largely be measuring that shared trend rather than a caseload effect — more
              authority than a dozen monthly points can carry. The paired axes let you judge it
              yourself.
            </li>
          </ul>
          <p className="mt-4 text-sm text-gray-600">
            For the all-time distributions, industry comparisons and referral rates, see the{' '}
            <Link to="/analysis" className="text-primary font-medium hover:underline">
              analysis page
            </Link>
            .
          </p>
        </div>
      </div>
    </>
  );
}

export default StateOfPlay;
