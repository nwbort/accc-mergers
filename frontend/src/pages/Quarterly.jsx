import { Link, useSearchParams } from 'react-router';
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
import { STATIC_PAGE_META } from '../utils/pageMeta';
import { CHART_PALETTE as COLORS } from '../constants/chartColors';
import {
  MILESTONE_LABELS,
  bucketShares,
  formatRate,
  keyFindings,
  percentChange,
  pickQuarter,
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

function CardHeader({ id, title, subtitle }) {
  return (
    <div className="px-6 py-5 border-b border-gray-100">
      <h2 id={id} className="text-base font-semibold text-gray-900">
        {title}
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

function VolumeChart({ quarters, selected }) {
  const series = [
    { label: 'Notifications filed', key: (q) => q.notifications.filed, color: COLORS.primary },
    { label: 'Phase 1 reviews concluded', key: (q) => q.notifications.phase_1_decided, color: COLORS.sage },
    { label: 'Waivers decided', key: (q) => q.waivers.decided, color: COLORS.teal },
  ];
  const labels = quarters.map((q) => (q.complete ? q.label : `${q.label} (to date)`));
  const data = {
    labels,
    datasets: series.map((s) => ({
      label: s.label,
      data: quarters.map(s.key),
      // The selected quarter in full colour, the rest faded behind it.
      backgroundColor: quarters.map((q) => (q.quarter === selected.quarter ? s.color : `${s.color}66`)),
      borderRadius: 4,
      maxBarThickness: 40,
    })),
  };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: { ...LEGEND, labels: { ...LEGEND.labels, generateLabels: (chart) =>
        chart.data.datasets.map((ds, i) => ({
          text: ds.label,
          fillStyle: series[i].color,
          strokeStyle: series[i].color,
          pointStyle: 'rectRounded',
          datasetIndex: i,
          hidden: !chart.isDatasetVisible(i),
        })) } },
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
          {rows.map(({ label, value }) => (
            <div key={label} className="flex items-baseline justify-between gap-4 py-2.5">
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

function TimingChart({ id, title, buckets, current, previous, color }) {
  const currentShares = bucketShares(current.buckets);
  const previousShares = previous ? bucketShares(previous.buckets) : null;
  const datasets = [];
  if (previousShares) {
    datasets.push({
      label: previous.label,
      data: previousShares,
      backgroundColor: `${color}55`,
      borderRadius: 4,
      maxBarThickness: 28,
    });
  }
  datasets.push({
    label: current.label,
    data: currentShares,
    backgroundColor: color,
    borderRadius: 4,
    maxBarThickness: 28,
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
    <div className={`${CARD} overflow-hidden`}>
      <CardHeader
        id={`${id}-title`}
        title={title}
        subtitle={`Share of decisions by business days taken – median ${days(current.median)}, 90% within ${days(current.p90)}`}
      />
      <div className="p-6">
        <div className="h-64" role="img" aria-labelledby={`${id}-title`} aria-describedby={`${id}-summary`}>
          <Bar data={{ labels: buckets, datasets }} options={options} role="presentation" />
        </div>
        <div className="sr-only">
          <table id={`${id}-summary`}>
            <caption>{title}: share of decisions by business days taken</caption>
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
      </div>
    </div>
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
      {quarter.matters > 0 && (
        <p className="border-t border-gray-100 bg-gray-50/60 px-6 py-4 text-sm text-gray-700">
          <strong>{formatRate(quarter.overseas_party / quarter.matters)}</strong> involved an
          overseas-registered acquirer or target ({quarter.overseas_party} of {quarter.matters})
          <span className="block mt-1 text-gray-500">
            A party counts when the register gives it a foreign registration number, or no ABN or
            ACN and an overseas legal form (Inc, GmbH, S.p.A.&hellip;). Unclear cases are left out,
            so this is a floor.
          </span>
        </p>
      )}
    </div>
  );
}

function MilestonesCard({ quarter }) {
  return (
    <section className="mb-6">
      <div className={`${CARD} overflow-hidden`}>
        <CardHeader
          id="quarterly-milestones-title"
          title="Beyond phase 1"
          subtitle="Phase 2 referrals and outcomes, public benefit applications, and Tribunal and court reviews"
        />
        {quarter.milestones.length === 0 ? (
          <p className="p-6 text-sm text-gray-500">Nothing went beyond phase 1 this quarter.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {quarter.milestones.map((m) => (
              <li
                key={`${m.merger_id}-${m.kind}-${m.date}-${m.detail ?? ''}`}
                className="flex flex-col gap-1 px-6 py-3.5 sm:flex-row sm:items-baseline sm:gap-4"
              >
                <span className="w-28 flex-shrink-0 text-sm text-gray-500 tabular-nums">
                  {formatDateMedium(m.date)}
                </span>
                <span className="flex items-center gap-2 sm:w-60 flex-shrink-0 text-sm font-medium text-gray-900">
                  <span className={`h-2 w-2 flex-shrink-0 rounded-full ${MILESTONE_DOTS[m.kind] || 'bg-gray-400'}`} aria-hidden="true" />
                  {MILESTONE_LABELS[m.kind] || m.kind}
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

function Quarterly() {
  const { data, loading, error } = useFetchData(API_ENDPOINTS.quarterly, { cacheKey: 'quarterly-data' });
  const [searchParams, setSearchParams] = useSearchParams();

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;
  if (!data) return null;

  const quarters = data.quarters || [];
  const quarter = pickQuarter(quarters, searchParams.get('q'));
  const seo = <SEO title={PAGE_META.title} description={PAGE_META.description} url="/quarterly" />;

  if (!quarter) {
    return (
      <>
        {seo}
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">Quarterly report</h1>
          <p className="mt-3 text-sm text-gray-600">This page is still being generated. Please check back shortly.</p>
        </div>
      </>
    );
  }

  const previous = previousQuarter(quarters, quarter);
  const prevLabel = previous?.label;
  const compareVolume = Boolean(previous) && quarter.complete;
  const n = quarter.notifications;
  const w = quarter.waivers;
  const findings = keyFindings(quarter, previous);
  const selectorQuarters = quarters.slice(-SELECTOR_QUARTERS);
  // A quarter reached by ?q= that has dropped off the selector still shows as
  // selected, rather than leaving the toggle with nothing pressed.
  if (!selectorQuarters.includes(quarter)) selectorQuarters.unshift(quarter);

  const selectQuarter = (key) => setSearchParams(key ? { q: key } : {}, { replace: true });

  return (
    <>
      {seo}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
              Quarterly report
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              {quarter.label} &middot; {formatDateLong(quarter.start)} &ndash; {formatDateLong(quarter.end)}
              {!quarter.complete && <> &middot; quarter to date, as at {formatDateLong(data.as_at)}</>}
            </p>
          </div>
          <SegmentedToggle
            ariaLabel="Quarter"
            options={selectorQuarters.map((q) => ({ value: q.quarter, label: q.label }))}
            value={quarter.quarter}
            onChange={selectQuarter}
          />
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
          {findings.length > 0 && (
            <div className="border-t border-gray-100 bg-gray-50/60 px-6 py-5">
              <h2 className={SECTION_HEADING}>The quarter in brief</h2>
              <ul className="mt-3 space-y-2 text-sm text-gray-800 list-disc pl-5 marker:text-primary">
                {findings.map((finding) => (
                  <li key={finding}>{finding}</li>
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
                  ? `${w.refused_refiled} of ${w.refused} refused waivers have since been re-filed as a notification.`
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
                { label: 'Referred to phase 2', value: n.referred_to_phase_2 },
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

        <section className="mb-6">
          <IndustriesCard quarter={quarter} />
        </section>

        <MilestonesCard quarter={quarter} />
      </div>
    </>
  );
}

export default Quarterly;
