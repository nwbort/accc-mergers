import { useState } from 'react';
import { Link } from 'react-router';
import { FaCircleInfo } from 'react-icons/fa6';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import CollapsibleCard from '../components/CollapsibleCard';
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

/** "+4 BD slower" / "−1 day faster" / "about the same", in plain words. */
function deltaSentence(delta, baseline, unit) {
  if (delta === null || delta === undefined || baseline === null) return null;
  const noun = unit === 'BD' ? 'BD' : Math.abs(delta) === 1 ? 'day' : 'days';
  if (delta === 0) return `Same as the all-time ${formatMedian(baseline)}`;
  return `${delta > 0 ? '+' : '−'}${formatMedian(Math.abs(delta))} ${noun} vs all-time ${formatMedian(baseline)}`;
}

/** One headline duration: the number, its unit, and how it sits against baseline. */
function Headline({ label, value, unit, delta, baseline, footnote }) {
  const sentence = deltaSentence(delta, baseline, unit);
  const slower = delta > 0;
  return (
    <div className="p-6">
      <p className={SECTION_HEADING}>{label}</p>
      {value === null ? (
        <p className="text-sm text-gray-500 mt-3">Nothing decided in this window.</p>
      ) : (
        <>
          <div className="flex items-baseline gap-2 mt-2 flex-wrap">
            <p className="text-5xl font-bold text-gray-900 tracking-tight leading-none">
              {formatMedian(value)}
            </p>
            <p className="text-sm text-gray-500">
              {unit === 'BD' ? 'business days' : 'calendar days'}
            </p>
          </div>
          {sentence && (
            <p className="mt-3 text-sm text-gray-600">
              <span className="font-semibold text-gray-900">{sentence}</span>
              {delta !== 0 && <span className="text-gray-500"> ({slower ? 'slower' : 'faster'})</span>}
            </p>
          )}
          {footnote && <p className="mt-2 text-sm text-gray-500">{footnote}</p>}
        </>
      )}
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
  const pre = play.pre_notification?.windows?.find(w => w.days === entry.days) ?? null;
  const preBaseline = play.pre_notification?.all_time ?? null;
  const caseloadNow = caseload?.notifications?.length
    ? caseload.notifications[caseload.notifications.length - 1]
    : null;

  return (
    <>
      <SEO title={PAGE_META.title} description={PAGE_META.description} url="/state-of-play" />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <header className="mb-5 sm:flex sm:items-end sm:justify-between sm:gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
              State of play
            </h1>
            <p className="mt-2 text-sm text-gray-600">
              How long the ACCC is taking right now, against its all-time median.
              {asAtLabel && <> As at {asAtLabel}.</>}
            </p>
          </div>
          <div
            className="mt-4 sm:mt-0 inline-flex items-center bg-gray-100 rounded-full p-0.5 text-sm flex-shrink-0"
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

        {/* The headlines. Everything a reader came for is above the fold; the
            method that produces them is in "More information" at the bottom. */}
        <div className={`${CARD} overflow-hidden mb-4`}>
          <div className="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-gray-100">
            <Headline
              label="Waiver"
              value={entry.waivers.median}
              unit="BD"
              delta={entry.waivers.median_delta}
              baseline={play.all_time.waivers.median}
              footnote={entry.waivers.p90 != null
                ? `9 in 10 within ${entry.waivers.p90} BD · ${entry.waivers.count} decided`
                : null}
            />
            <Headline
              label="Notification – phase 1"
              value={entry.notifications.median}
              unit="BD"
              delta={entry.notifications.median_delta}
              baseline={play.all_time.notifications.median}
              footnote={entry.notifications.p90 != null
                ? `9 in 10 within ${entry.notifications.p90} BD · ${entry.notifications.count} decided`
                : null}
            />
          </div>
          {pre && pre.median !== null && (
            <div className="border-t border-gray-100 bg-gray-50/60 px-6 py-4 sm:flex sm:items-baseline sm:gap-3">
              <p className="text-sm text-gray-600">
                <span className="font-semibold text-gray-900">
                  Before filing: about {formatMedian(pre.median)} calendar days
                </span>{' '}
                in pre-notification
                {preBaseline?.median != null && <> (all-time {formatMedian(preBaseline.median)})</>}
                .
              </p>
              <p className="text-sm text-gray-500 mt-1 sm:mt-0">
                Estimated — the ACCC doesn&rsquo;t publish it.
              </p>
            </div>
          )}
        </div>

        <p className="text-sm text-gray-600 mb-8">
          In the last {entry.days} days: <strong>{entry.notifications_filed}</strong> notifications
          filed, <strong>{entry.notifications.count + entry.waivers.count}</strong> decisions
          published
          {caseloadNow !== null && <>, <strong>{caseloadNow}</strong> notifications still open</>}
          .
        </p>

        <section className="mb-6">
          <div className={`${CARD} overflow-hidden`}>
            <div className="px-6 py-5 border-b border-gray-100">
              <h2 id="chart-turnaround-trend-title" className="text-base font-semibold text-gray-900">
                Is it getting slower?
              </h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Median time to decide each month, against the ACCC&rsquo;s open caseload
              </p>
            </div>
            <div className="p-6">
              <TurnaroundTrendChart monthly={play.monthly} />
            </div>
          </div>
        </section>

        <CollapsibleCard
          icon={<FaCircleInfo className="text-gray-500" aria-hidden="true" />}
          title="More information"
          subtitle="How these numbers are measured, and what they can and can't tell you"
        >
          <div className="pt-5 space-y-4 text-sm text-gray-600 leading-relaxed">
            <div>
              <h3 className="font-semibold text-gray-900">What&rsquo;s counted</h3>
              <p className="mt-1">
                A matter counts towards the window it was <em>decided</em> in, not the one it was
                filed in — so these figures track what the ACCC is actually clearing now.
                Notifications are measured from filing to the end of phase 1 (for a matter sent to
                phase 2, that&rsquo;s the referral date, so the phase 2 clock never inflates the
                figure). Waivers run from application to determination; they have no statutory
                clock. Pre-notification is the exception and is counted by filing month, since
                that&rsquo;s the event that ends it.
              </p>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">The median isn&rsquo;t the promise</h3>
              <p className="mt-1">
                Half of all matters take longer than the median. The &ldquo;9 in 10 within&rdquo;
                figure is the one to quote when a client needs a date they can rely on.
              </p>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Pre-notification is an estimate</h3>
              <p className="mt-1">
                The stage before filing never appears on the register. It&rsquo;s inferred from the
                order ACCC case numbers were issued in — a waiver application is lodged the day its
                case is opened, so waivers date the counter that notifications are measured
                against. Treat movement in the figure as sound and the absolute level as carrying a
                common offset: every matter is measured from the same unobservable zero, so a small
                error there shifts them all together rather than adding noise. Matters filed before
                the regime became mandatory are excluded. It&rsquo;s in calendar days, not business
                days — it isn&rsquo;t a statutory clock. A single matter&rsquo;s estimate carries a
                confidence rating on its own page; the figure here pools all of them, because
                narrowing it to the better-evidenced ones moves the median by less than a day.
              </p>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Waivers and the caseload line</h3>
              <p className="mt-1">
                A waiver application only reaches the register once it has been decided, so the
                ACCC&rsquo;s pending waivers are invisible to us. That&rsquo;s why the filing count
                and the caseload line cover notifications only — a waiver figure there would be
                missing every application still in front of the ACCC.
              </p>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Reading the chart</h3>
              <p className="mt-1">
                A month with fewer than five decisions is left unplotted rather than charted off
                one or two matters. No correlation figure is published against the caseload: both
                lines trend over the register&rsquo;s short life, so any coefficient would largely
                be measuring that shared trend rather than a caseload effect. The paired axes let
                you judge it yourself.
              </p>
            </div>
            <p className="pt-1">
              For all-time distributions, industry comparisons and referral rates, see the{' '}
              <Link to="/analysis" className="text-primary font-medium hover:underline">
                analysis page
              </Link>
              .
            </p>
          </div>
        </CollapsibleCard>
      </div>
    </>
  );
}

export default StateOfPlay;
