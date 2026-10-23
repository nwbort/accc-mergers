import { Link, useNavigate, useParams } from 'react-router';
import ReactMarkdown from 'react-markdown';
import { Bar } from 'react-chartjs-2';
import '../utils/chartSetup';
import LoadingSpinner from '../components/LoadingSpinner';
import SegmentedToggle from '../components/SegmentedToggle';
import ErrorMessage from '../components/ErrorMessage';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { formatDateLong, formatDateMedium } from '../utils/dates';
import { formatMedian } from '../utils/formatMedian';
import { industryPath, mergerPath } from '../utils/slug';
import { CARD, SECTION_HEADING } from '../utils/classNames';
import { STATIC_PAGE_META, quarterlyMeta } from '../utils/pageMeta';
import NotFound from './NotFound';
import { CHART_PALETTE as COLORS } from '../constants/chartColors';
import {
  bucketShares,
  findQuarter,
  formatRate,
  percentChange,
  previousQuarter,
} from '../utils/quarterlyReport';

// Title and description live in the shared table so this page and the
// build-time prerenderer emit the same <head>.
const PAGE_META = STATIC_PAGE_META['/quarterly'];

// How many quarters the selector offers. Older ones stay reachable by ?q=.
const SELECTOR_QUARTERS = 4;

// Milestones that mark a matter going against the parties, coloured as the
// rest of the site colours a refusal; everything else stays neutral.
const MILESTONE_DOTS = {
  referred: 'bg-phase-2-referral',
  phase_1_refused: 'bg-declined-dark',
  phase_2_outcome: 'bg-phase-2',
  ceased: 'bg-ceased',
  public_benefit_application: 'bg-phase-2-light',
  public_benefit_outcome: 'bg-phase-2',
  tribunal_application: 'bg-tribunal-appeal',
  judicial_review: 'bg-tribunal-appeal',
};

/**
 * Change against the previous quarter, coloured only where a direction is
 * plainly better or worse for a deal: slower is the declined red, faster the
 * cleared green. Volume moves are neither, so they stay grey.
 */
function Delta({ children, tone = 'neutral' }) {
  const colour =
    tone === 'worse' ? 'text-declined-dark' : tone === 'better' ? 'text-cleared-dark' : 'text-gray-600';
  return <p className={`mt-1 text-sm font-medium ${colour}`}>{children}</p>;
}

function VolumeTile({ label, value, previous, previousLabel, compare }) {
  const change = compare ? percentChange(value, previous) : null;
  return (
    <div className="p-5">
      <p className={SECTION_HEADING}>{label}</p>
      <p className="mt-1.5 text-3xl font-bold tracking-tight text-gray-900">{value}</p>
      {change !== null && (
        <Delta>
          {change === 0 ? 'Level' : `${change > 0 ? '+' : '−'}${Math.abs(change)}%`} on {previousLabel}
        </Delta>
      )}
    </div>
  );
}

function TimingTile({ label, value, previous, previousLabel }) {
  const delta = value != null && previous != null ? Math.round((value - previous) * 10) / 10 : null;
  return (
    <div className="p-5">
      <p className={SECTION_HEADING}>{label}</p>
      <p className="mt-1.5 text-3xl font-bold tracking-tight text-gray-900">
        {value == null ? '–' : formatMedian(value)}
        {value != null && <span className="ml-1.5 text-sm font-normal text-gray-500">business days</span>}
      </p>
      {delta !== null && (
        <Delta tone={delta > 0 ? 'worse' : delta < 0 ? 'better' : 'neutral'}>
          {delta === 0
            ? `Same as ${previousLabel}`
            : `${formatMedian(Math.abs(delta))} ${Math.abs(delta) === 1 ? 'day' : 'days'} ${
                delta > 0 ? 'slower' : 'faster'
              } than ${previousLabel}`}
        </Delta>
      )}
    </div>
  );
}

// Links into the rest of the site are set as plain text that underlines on
// hover, so a card heading goes somewhere without the page reading as a wall
// of links.
const QUIET_LINK = 'hover:text-primary hover:underline underline-offset-2';
const INLINE_LINK = 'text-primary hover:underline underline-offset-2';

function CardHeader({ id, title, subtitle, to }) {
  return (
    <div className="px-6 py-5 border-b border-gray-100">
      <h2 id={id} className="text-base font-semibold text-gray-900">
        {to ? <Link to={to} className={QUIET_LINK}>{title}</Link> : title}
      </h2>
      {subtitle && <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}
    </div>
  );
}

const LEGEND = {
  position: 'bottom',
  labels: {
    usePointStyle: true,
    pointStyle: 'rectRounded',
    padding: 16,
    font: { size: 12, family: 'Inter, sans-serif' },
  },
};

/**
 * A quarter's bar colour in the volume chart: the selected quarter in full
 * primary, the others faded behind it, older ones fainter, so each group reads
 * left to right as a trend.
 */
function volumeQuarterColor(index, count, isSelected) {
  if (isSelected) return COLORS.primary;
  const alpha = count > 1 ? 0.2 + (0.35 * index) / (count - 1) : 0.4;
  return `rgba(51, 81, 69, ${alpha.toFixed(2)})`;
}

function VolumeChart({ quarters, selected }) {
  const series = [
    { label: 'Notifications filed', key: (q) => q.notifications.filed },
    { label: 'Phase 1 reviews concluded', key: (q) => q.notifications.phase_1_decided },
    { label: 'Waivers decided', key: (q) => q.waivers.decided },
  ];
  const labels = quarters.map((q) => q.label);
  // Grouped by measure, one bar per quarter within each, so a measure's change
  // over time sits side by side.
  const colours = quarters.map((q, i) => volumeQuarterColor(i, quarters.length, q.quarter === selected.quarter));
  const data = {
    labels: series.map((s) => s.label),
    datasets: quarters.map((q, i) => ({
      label: q.label,
      data: series.map((s) => s.key(q)),
      backgroundColor: colours[i],
      borderRadius: 4,
      maxBarThickness: 40,
    })),
  };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: LEGEND,
    },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 11 } } },
      y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' }, ticks: { font: { size: 11 } } },
    },
  };

  return (
    <section className="mb-6">
      <div className={`${CARD} overflow-hidden`}>
        <CardHeader
          id="chart-quarterly-volume-title"
          title="Volume by quarter"
          to="/analysis"
          subtitle="Waivers reach the ACCC's register only once decided, so they are counted when decided"
        />
        <div className="p-6">
          <div
            className="h-72"
            role="img"
            aria-labelledby="chart-quarterly-volume-title"
            aria-describedby="chart-quarterly-volume-summary"
          >
            <Bar data={data} options={options} role="presentation" />
          </div>
          <div className="sr-only">
            <table id="chart-quarterly-volume-summary">
              <caption>Notifications filed, phase 1 reviews concluded and waivers decided, per quarter</caption>
              <thead>
                <tr>
                  <th>Quarter</th>
                  {series.map((s) => <th key={s.label}>{s.label}</th>)}
                </tr>
              </thead>
              <tbody>
                {quarters.map((q, i) => (
                  <tr key={q.quarter}>
                    <td>{labels[i]}</td>
                    {series.map((s) => <td key={s.label}>{s.key(q)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
}

/**
 * One review type's outcomes for the quarter: the clearance rate the eye goes
 * to first, then the split and the average time each outcome took.
 */
function OutcomeCard({ title, rate, granted, decided, rows, footnote }) {
  return (
    <div className={`${CARD} overflow-hidden`}>
      <div className="px-5 py-3 bg-primary">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
      </div>
      <div className="p-5">
        <p className={SECTION_HEADING}>Clearance rate</p>
        <p className="mt-1.5 text-5xl font-bold tracking-tight leading-none text-gray-900">{formatRate(rate)}</p>
        <p className="mt-2 text-sm text-gray-500">
          {granted} of {decided} approved
        </p>
        <dl className="mt-5 divide-y divide-gray-100 border-t border-gray-100 text-sm">
          {rows.map(({ label, key, value }) => (
            <div key={key ?? label} className="flex items-baseline justify-between gap-4 py-2.5">
              <dt className="text-gray-600">{label}</dt>
              <dd className="font-semibold text-gray-900 text-right">{value}</dd>
            </div>
          ))}
        </dl>
        {footnote && <p className="mt-3 text-sm text-gray-500">{footnote}</p>}
      </div>
    </div>
  );
}

function days(value) {
  return value == null ? '–' : `${formatMedian(value)} business days`;
}

/**
 * Two quarters' distributions as side-by-side bars, each bucket's share of
 * its quarter's total so a busy quarter and a quiet one compare on shape. The
 * canvas is presentational; the sr-only table beside it carries the numbers.
 *
 * A bucket's two bars sit flush, sized by `categoryPercentage` (the share of
 * the bucket's slot they fill) rather than capped at a thickness: a capped bar
 * stays centred in its half of a wide slot, opening a gap between the pair.
 */
function ShareChart({ id, caption, buckets, current, previous, color, height = 'h-64', categoryPercentage = 0.8 }) {
  const bar = { borderRadius: 4, barPercentage: 0.94, categoryPercentage };
  const currentShares = bucketShares(current.buckets);
  const previousShares = previous ? bucketShares(previous.buckets) : null;
  const datasets = [];
  if (previousShares) {
    datasets.push({
      label: previous.label,
      data: previousShares,
      backgroundColor: `${color}55`,
      ...bar,
    });
  }
  datasets.push({
    label: current.label,
    data: currentShares,
    backgroundColor: color,
    ...bar,
  });
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: LEGEND,
      tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y}%` } },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { font: { size: 11 } },
        title: { display: true, text: 'Business days', font: { size: 12 }, color: '#6b7280' },
      },
      y: {
        beginAtZero: true,
        grid: { color: 'rgba(0,0,0,0.04)' },
        ticks: { font: { size: 11 }, callback: (v) => `${v}%` },
      },
    },
  };

  return (
    <>
      <div className={height} role="img" aria-labelledby={`${id}-title`} aria-describedby={`${id}-summary`}>
        <Bar data={{ labels: buckets, datasets }} options={options} role="presentation" />
      </div>
      <div className="sr-only">
        <table id={`${id}-summary`}>
          <caption>{caption}</caption>
          <thead>
            <tr>
              <th>Business days</th>
              {previousShares && <th>{previous.label}</th>}
              <th>{current.label}</th>
            </tr>
          </thead>
          <tbody>
            {buckets.map((bucket, i) => (
              <tr key={bucket}>
                <td>{bucket}</td>
                {previousShares && <td>{previousShares[i]}%</td>}
                <td>{currentShares[i]}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function TimingChart({ id, title, buckets, current, previous, color }) {
  return (
    <div className={`${CARD} overflow-hidden`}>
      <CardHeader
        id={`${id}-title`}
        title={title}
        to="/current-status"
        subtitle={`Share of decisions by business days taken \u2013 median ${days(current.median)}, 90% within ${days(current.p90)}`}
      />
      <div className="p-6">
        <ShareChart
          id={id}
          caption={`${title}: share of decisions by business days taken`}
          buckets={buckets}
          current={current}
          previous={previous}
          color={color}
        />
      </div>
    </div>
  );
}

/**
 * How long the quarter's notifications spent in pre-notification before they
 * were filed. A longer stage is the adverse direction for a deal timetable, so
 * a longer median takes the same red as a slower review.
 */
function PreNotificationCard({ quarter, previous, buckets }) {
  const pre = quarter.pre_notification;
  if (!pre?.count) return null;
  const before = previous?.pre_notification;
  const delta = before?.median != null ? Math.round((pre.median - before.median) * 10) / 10 : null;
  const stats = [
    { label: 'Median', value: pre.median },
    { label: 'Average', value: pre.average },
    { label: '90% within', value: pre.p90 },
  ];
  const id = 'chart-quarterly-pre-notification';

  return (
    <section className="mb-6">
      <div className={`${CARD} overflow-hidden`}>
        <CardHeader
          id={`${id}-title`}
          title="Pre-notification"
          to="/current-status"
          subtitle={`Estimated time notifications filed this quarter spent with the ACCC before filing \u2013 ${pre.count} notifications`}
        />
        <div className="grid grid-cols-3 divide-x divide-gray-100 border-b border-gray-100">
          {stats.map(({ label, value }) => (
            <div key={label} className="p-5">
              <p className={SECTION_HEADING}>{label}</p>
              <p className="mt-1.5 text-2xl font-bold tracking-tight text-gray-900">
                {value == null ? '\u2013' : formatMedian(value)}
                {value != null && <span className="ml-1 text-sm font-normal text-gray-500">BD</span>}
              </p>
              {label === 'Median' && delta !== null && (
                <Delta tone={delta > 0 ? 'worse' : delta < 0 ? 'better' : 'neutral'}>
                  {delta === 0
                    ? `Same as ${previous.label}`
                    : `${formatMedian(Math.abs(delta))} ${delta > 0 ? 'longer' : 'shorter'} than ${previous.label}`}
                </Delta>
              )}
            </div>
          ))}
        </div>
        <div className="p-6">
          <ShareChart
            id={id}
            caption="Share of notifications filed by estimated business days in pre-notification"
            buckets={buckets}
            current={{ label: quarter.label, ...pre }}
            previous={before?.count ? { label: previous.label, ...before } : null}
            color={COLORS.accent}
            // A full-width card with few buckets: a narrower group keeps the
            // bars about as thick as the half-width timing charts'.
            categoryPercentage={0.5}
          />
        </div>
      </div>
    </section>
  );
}

function IndustriesCard({ quarter }) {
  const top = quarter.industries;
  const max = top.length ? top[0].count : 0;
  return (
    <div className={`${CARD} overflow-hidden`}>
      <CardHeader
        id="quarterly-industries-title"
        title="Where the deals were"
        to="/industries"
        subtitle="Notifications filed and waivers decided, by ANZSIC division"
      />
      <div className="p-6">
        {top.length === 0 ? (
          <p className="text-sm text-gray-500">No matters this quarter.</p>
        ) : (
          <ol className="space-y-3">
            {top.map((industry) => (
              <li key={industry.code}>
                <div className="flex items-baseline justify-between gap-4 text-sm">
                  <Link
                    to={industryPath(industry.code, industry.name)}
                    className="font-medium text-gray-900 hover:text-primary hover:underline"
                  >
                    {industry.name}
                  </Link>
                  <span className="text-gray-600 tabular-nums">{industry.count}</span>
                </div>
                <div className="mt-1.5 h-2 rounded-full bg-gray-100" aria-hidden="true">
                  <div className="h-2 rounded-full bg-primary" style={{ width: `${(industry.count / max) * 100}%` }} />
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

const SITE_ORIGIN = 'https://mergers.fyi';
const COMMENTARY_LINK = 'text-primary underline underline-offset-2 hover:no-underline';

/**
 * A link in hand-written commentary. One into this site — a bare path, or a
 * full mergers.fyi URL, which is what the PDF needs — routes in the app
 * rather than reloading the page; anything else is an ordinary link.
 */
function CommentaryLink({ href = '', children }) {
  const path = href.startsWith(SITE_ORIGIN) ? href.slice(SITE_ORIGIN.length) || '/' : href;
  if (path.startsWith('/')) {
    return <Link to={path} className={COMMENTARY_LINK}>{children}</Link>;
  }
  return <a href={href} className={COMMENTARY_LINK}>{children}</a>;
}

/**
 * Applications to the Australian Competition Tribunal live during the quarter.
 * Each matter links out to the Tribunal's own page and in to the merger; the
 * one-line status is written by the generator so it matches the PDF.
 */
function AppealsCard({ quarter }) {
  const appeals = quarter.appeals;
  if (!appeals) return null;
  const counts = [
    { label: 'Lodged', value: appeals.lodged },
    { label: 'Concluded', value: appeals.concluded },
    { label: 'Open at quarter end', value: appeals.open_at_end },
  ];
  return (
    <section className="mb-6">
      <div className={`${CARD} overflow-hidden`}>
        <CardHeader
          id="quarterly-appeals-title"
          title="Tribunal reviews"
          subtitle="Applications to the Australian Competition Tribunal for review of an ACCC determination, live at some point in the quarter"
        />
        {appeals.matters.length === 0 ? (
          <p className="p-6 text-sm text-gray-500">No Tribunal reviews were live this quarter.</p>
        ) : (
          <>
            <dl className="grid grid-cols-3 divide-x divide-gray-100 border-b border-gray-100">
              {counts.map(({ label, value }) => (
                // Bottom-aligned so the counts line up when a long label wraps.
                <div key={label} className="flex flex-col justify-between p-5">
                  <dt className={SECTION_HEADING}>{label}</dt>
                  <dd className="mt-1.5 text-2xl font-bold tracking-tight text-gray-900">{value}</dd>
                </div>
              ))}
            </dl>
            <ul className="divide-y divide-gray-100">
              {appeals.matters.map((m) => (
                <li key={m.tribunal_number} className="px-6 py-4">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                    <p className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                      <span className="h-2 w-2 flex-shrink-0 rounded-full bg-tribunal-appeal" aria-hidden="true" />
                      {m.tribunal_url ? (
                        <a href={m.tribunal_url} target="_blank" rel="noopener noreferrer" className={QUIET_LINK}>
                          {m.tribunal_number}
                          <span className="sr-only"> (opens the Tribunal&apos;s site in a new tab)</span>
                        </a>
                      ) : (
                        m.tribunal_number
                      )}
                      {m.appellant && <span className="font-normal text-gray-600">&middot; {m.appellant}</span>}
                    </p>
                    <span className="text-sm text-gray-500 tabular-nums">Lodged {formatDateMedium(m.filed_date)}</span>
                  </div>
                  <Link to={mergerPath(m.merger_id, m.merger_name)} className={`mt-1 block text-sm ${INLINE_LINK}`}>
                    {m.merger_name}
                  </Link>
                  <p className="mt-1 text-sm text-gray-600">{m.note}</p>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </section>
  );
}

function MilestonesCard({ quarter }) {
  return (
    <section className="mb-6">
      <div className={`${CARD} overflow-hidden`}>
        <CardHeader
          id="quarterly-milestones-title"
          title="Beyond phase 1"
          to="/phase-2"
          subtitle="Phase 2 referrals and outcomes, public benefit applications, and Tribunal and court reviews"
        />
        {quarter.milestones.length === 0 ? (
          <p className="p-6 text-sm text-gray-500">Nothing went beyond phase 1 this quarter.</p>
        ) : (
          // The list comes grouped by matter, so a rule marks where one
          // matter's run ends rather than separating every row.
          <ul>
            {quarter.milestones.map((m, i) => (
              <li
                key={`${m.merger_id}-${m.kind}-${m.date}-${m.detail ?? ''}`}
                className={`flex flex-col gap-1 px-6 sm:flex-row sm:items-baseline sm:gap-4 ${
                  i > 0 && quarter.milestones[i - 1].merger_id === m.merger_id
                    ? 'pb-3.5'
                    : `py-3.5${i > 0 ? ' border-t border-gray-100' : ''}`
                }`}
              >
                <span className="w-28 flex-shrink-0 text-sm text-gray-500 tabular-nums">
                  {formatDateMedium(m.date)}
                </span>
                <span className="flex items-center gap-2 sm:w-60 flex-shrink-0 text-sm font-medium text-gray-900">
                  <span className={`h-2 w-2 flex-shrink-0 rounded-full ${MILESTONE_DOTS[m.kind] || 'bg-gray-400'}`} aria-hidden="true" />
                  {m.label}
                </span>
                <span className="min-w-0 text-sm">
                  <Link to={mergerPath(m.merger_id, m.merger_name)} className="text-primary hover:underline">
                    {m.merger_name}
                  </Link>
                  {m.detail && <span className="text-gray-600"> &middot; {m.detail}</span>}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

/**
 * /quarterly/26Q3 is one quarter's report; /quarterly is the latest quarter.
 *
 * The bare URL renders the latest quarter in place rather than redirecting, so
 * it stays a stable link to "the current report", but it declares the dated
 * URL as its canonical: search engines index each report once, at an address
 * that never changes what it shows, and the canonical moves on by itself each
 * quarter. The sitemap lists only the dated pages (see generate_sitemap.py).
 */
function Quarterly() {
  const { data, loading, error } = useFetchData(API_ENDPOINTS.quarterly, { cacheKey: 'quarterly-data' });
  const { quarter: quarterParam } = useParams();
  const navigate = useNavigate();

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;
  if (!data) return null;

  const quarters = data.quarters || [];
  // quarterly.json publishes complete quarters only, oldest first, so the bare
  // URL's quarter is the last one to have ended. A dated URL naming no
  // published quarter is a 404, not the latest report under a wrong address.
  const quarter = quarterParam ? findQuarter(quarters, quarterParam) : quarters[quarters.length - 1] || null;
  if (quarterParam && !quarter) return <NotFound />;

  if (!quarter) {
    return (
      <>
        <SEO title={PAGE_META.title} description={PAGE_META.description} url="/quarterly" />
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">Quarterly report</h1>
          <p className="mt-3 text-sm text-gray-600">This page is still being generated. Please check back shortly.</p>
        </div>
      </>
    );
  }

  const previous = previousQuarter(quarters, quarter);
  const prevLabel = previous?.label;
  const compareVolume = Boolean(previous);
  const n = quarter.notifications;
  const w = quarter.waivers;
  const findings = quarter.findings || [];
  const commentary = quarter.commentary || [];
  const selectorQuarters = quarters.slice(-SELECTOR_QUARTERS);
  // A quarter reached by its URL that has dropped off the selector still shows as
  // selected, rather than leaving the toggle with nothing pressed.
  if (!selectorQuarters.includes(quarter)) selectorQuarters.unshift(quarter);

  const selectQuarter = (key) => navigate(`/quarterly/${key}`);
  const meta = quarterlyMeta(quarter);

  return (
    <>
      <SEO title={meta.title} description={meta.description} url={meta.path} structuredData={meta.structuredData} />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
              Quarterly report
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              {quarter.label} &middot; {formatDateLong(quarter.start)} &ndash; {formatDateLong(quarter.end)}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <a
                href={API_ENDPOINTS.quarterlyReportPdf(quarter.report_pdf)}
                download={quarter.report_pdf}
                className="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-white px-3.5 py-1.5 text-sm font-medium text-gray-700 hover:border-primary hover:text-primary"
              >
                <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M10 2a1 1 0 011 1v8.59l2.3-2.3a1 1 0 111.4 1.42l-4 4a1 1 0 01-1.4 0l-4-4a1 1 0 111.4-1.42L9 11.59V3a1 1 0 011-1zM4 15a1 1 0 011 1v1h10v-1a1 1 0 112 0v2a1 1 0 01-1 1H4a1 1 0 01-1-1v-2a1 1 0 011-1z" />
                </svg>
                Download PDF
              </a>
            <SegmentedToggle
              ariaLabel="Quarter"
              options={selectorQuarters.map((q) => ({ value: q.url_key, label: q.label }))}
              value={quarter.url_key}
              onChange={selectQuarter}
            />
          </div>
        </header>

        <div className={`${CARD} overflow-hidden mb-6`}>
          <div className="grid grid-cols-2 lg:grid-cols-4 divide-x divide-y lg:divide-y-0 divide-gray-100">
            <VolumeTile
              label="Notifications filed"
              value={n.filed}
              previous={previous?.notifications.filed}
              previousLabel={prevLabel}
              compare={compareVolume}
            />
            <VolumeTile
              label="Waivers decided"
              value={w.decided}
              previous={previous?.waivers.decided}
              previousLabel={prevLabel}
              compare={compareVolume}
            />
            <TimingTile
              label="Phase 1 median"
              value={n.timing.median}
              previous={previous?.notifications.timing.median}
              previousLabel={prevLabel}
            />
            <TimingTile
              label="Waiver median"
              value={w.timing.median}
              previous={previous?.waivers.timing.median}
              previousLabel={prevLabel}
            />
          </div>
          {(findings.length > 0 || commentary.length > 0) && (
            <div className="border-t border-gray-100 bg-gray-50/60 px-6 py-5">
              <h2 className={SECTION_HEADING}>The quarter in brief</h2>
              <ul className="mt-3 space-y-2 text-sm text-gray-800 list-disc pl-5 marker:text-primary">
                {findings.map((finding) => (
                  <li key={finding}>{finding}</li>
                ))}
                {/* Hand-written points (quarterly_commentary.json), after the
                    generated ones. Markdown, rendered inline so a point stays
                    one bullet. */}
                {commentary.map((entry) => (
                  <li key={entry.commentary}>
                    <ReactMarkdown
                      components={{
                        p: ({ children }) => <>{children}</>,
                        a: ({ href, children }) => <CommentaryLink href={href}>{children}</CommentaryLink>,
                      }}
                    >
                      {entry.commentary}
                    </ReactMarkdown>
                    {entry.author && <span className="text-gray-500"> &mdash; {entry.author}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <VolumeChart quarters={quarters} selected={quarter} />

        <section className="mb-6" aria-labelledby="quarterly-outcomes-title">
          <h2 id="quarterly-outcomes-title" className="sr-only">Outcomes</h2>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <OutcomeCard
              title="Waivers"
              rate={w.clearance_rate}
              granted={w.granted}
              decided={w.decided}
              rows={[
                { label: 'Average when granted', value: days(w.average_granted) },
                { label: 'Average when refused', value: days(w.average_refused) },
                { label: 'Refused', value: w.refused },
              ]}
              footnote={
                w.refused
                  ? (
                    <>
                      {w.refused_refiled} of {w.refused} refused waivers have since been{' '}
                      <Link to="/refiled-notifications" className={INLINE_LINK}>re-filed as a notification</Link>.
                    </>
                  )
                  : null
              }
            />
            <OutcomeCard
              title={'Notifications \u2013 phase 1'}
              rate={n.clearance_rate}
              granted={n.cleared}
              decided={n.phase_1_decided}
              rows={[
                { label: 'Average when approved', value: days(n.average_cleared) },
                { label: 'Average when referred', value: days(n.average_referred) },
                {
                  label: <Link to="/phase-2" className={QUIET_LINK}>Referred to phase 2</Link>,
                  key: 'referred',
                  value: n.referred_to_phase_2,
                },
                ...(n.refused ? [{ label: 'Not approved', value: n.refused }] : []),
                ...(n.ceased ? [{ label: 'Ceased in phase 1', value: n.ceased }] : []),
              ]}
            />
          </div>
        </section>

        <section className="mb-6" aria-labelledby="quarterly-timing-title">
          <h2 id="quarterly-timing-title" className="sr-only">Timing</h2>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <TimingChart
              id="chart-quarterly-waiver-timing"
              title="Waiver timing"
              buckets={data.duration_buckets}
              current={{ label: quarter.label, ...w.timing }}
              previous={previous ? { label: previous.label, ...previous.waivers.timing } : null}
              color={COLORS.teal}
            />
            <TimingChart
              id="chart-quarterly-phase1-timing"
              title="Phase 1 timing"
              buckets={data.duration_buckets}
              current={{ label: quarter.label, ...n.timing }}
              previous={previous ? { label: previous.label, ...previous.notifications.timing } : null}
              color={COLORS.primary}
            />
          </div>
        </section>

        <PreNotificationCard
          quarter={quarter}
          previous={previous}
          buckets={data.pre_notification_buckets || []}
        />

        <section className="mb-6">
          <IndustriesCard quarter={quarter} />
        </section>

        <AppealsCard quarter={quarter} />

        <MilestonesCard quarter={quarter} />
      </div>
    </>
  );
}

export default Quarterly;
