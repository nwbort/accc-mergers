import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Bar, Line } from 'react-chartjs-2';
import '../utils/chartSetup';
import LoadingSpinner from '../components/LoadingSpinner';
import SegmentedToggle from '../components/SegmentedToggle';
import ErrorMessage from '../components/ErrorMessage';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { formatDateMedium, formatMonthLabel } from '../utils/dates';
import { industryPath } from '../utils/slug';
import { CHART_PALETTE as COLORS } from '../constants/chartColors';
import { CARD, SECTION_HEADING } from '../utils/classNames';
import { STATIC_PAGE_META } from '../utils/pageMeta';
import { computeEcdf } from '../utils/durationEcdf';
import DurationEcdfChart from '../components/DurationEcdfChart';
import { PHASE_1_DEADLINE_BD, WAIVER_DEADLINE_BD } from '../constants/statutoryDeadlines';

// Title and description live in the shared table so this page and the
// build-time prerenderer emit the same <head>.
const PAGE_META = STATIC_PAGE_META['/analysis'];


function Analysis() {
  const { data, loading, error } = useFetchData(API_ENDPOINTS.analysis, {
    cacheKey: 'analysis-data',
  });
  const navigate = useNavigate();
  const [calendarDays, setCalendarDays] = useState(false);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;
  if (!data) return null;

  const { phase1_duration, waiver_duration, monthly_volume, industry_phase1_duration } = data;
  const phase1Stats = calendarDays ? phase1_duration.calendar_stats : phase1_duration.stats;
  const waiverStats = calendarDays ? waiver_duration.calendar_stats : waiver_duration.stats;

  const dayLabel = calendarDays ? 'calendar days' : 'business days';

  // --- Duration ECDFs ---
  // Both curves are drawn by the shared DurationEcdfChart, which /current-status
  // reuses over its rolling windows — the two pages have to stay comparable.
  const ecdfPoints = computeEcdf(phase1_duration.duration_histogram, calendarDays);
  const waiverEcdfPoints = computeEcdf(waiver_duration.duration_histogram, calendarDays);
  // The statutory clocks are counted in business days, so the reference line is
  // dropped rather than misplaced when the axis switches to calendar days.
  const phase1Deadline = calendarDays ? null : PHASE_1_DEADLINE_BD;
  const waiverDeadline = calendarDays ? null : WAIVER_DEADLINE_BD;

  // --- Monthly Volume ---
  const monthlyVolumeData = {
    labels: monthly_volume.labels.map(formatMonthLabel),
    datasets: [
      {
        label: 'Notifications',
        data: monthly_volume.notifications,
        backgroundColor: COLORS.primary,
        borderRadius: 4,
        maxBarThickness: 40,
      },
      {
        label: 'Waivers',
        data: monthly_volume.waivers,
        backgroundColor: COLORS.teal,
        borderRadius: 4,
        maxBarThickness: 40,
      },
    ],
  };

  const monthlyVolumeOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          usePointStyle: true,
          pointStyle: 'rectRounded',
          padding: 16,
          font: { size: 12, family: 'Inter, sans-serif' },
        },
      },
    },
    scales: {
      x: {
        stacked: true,
        grid: { display: false },
        ticks: { font: { size: 11 } },
      },
      y: {
        stacked: true,
        beginAtZero: true,
        ticks: { stepSize: 5, font: { size: 11 } },
        grid: { color: 'rgba(0,0,0,0.04)' },
        title: {
          display: true,
          text: 'Count',
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
      },
    },
  };

  // --- Open caseload (stock, not flow) ---
  // Guarded on presence: analysis.json is fetched from the deployed site, so a
  // build can be serving a payload generated before this series existed.
  const caseload = data.open_caseload;
  const hasCaseload = Boolean(caseload?.labels?.length);

  let caseloadData = null;
  let caseloadOptions = null;
  let caseloadLatest = null;
  let caseloadDelta = null;
  let caseloadDeltaFrom = null;
  let caseloadAsAtLabel = null;
  let caseloadPartialLast = false;

  if (hasCaseload) {
    const lastIndex = caseload.labels.length - 1;
    // The last point is measured at as_at rather than a month end, so it gets
    // a hollow marker: it's a reading mid-month, not a completed month.
    caseloadPartialLast = caseload.as_at?.slice(0, 7) === caseload.labels[lastIndex];
    caseloadLatest = caseload.notifications[lastIndex];
    caseloadAsAtLabel = caseload.as_at ? formatDateMedium(caseload.as_at) : null;

    // Six-month movement rather than a peak: the caseload has only ever
    // grown, so a peak stat would just restate the latest figure. Falls back
    // to the start of the series while less than six months of it exists.
    const compareIndex = Math.max(0, lastIndex - 6);
    if (compareIndex !== lastIndex) {
      caseloadDelta = caseloadLatest - caseload.notifications[compareIndex];
      caseloadDeltaFrom = formatMonthLabel(caseload.labels[compareIndex]);
    }

    caseloadData = {
      labels: caseload.labels.map(formatMonthLabel),
      datasets: [
        {
          label: 'Open notifications',
          data: caseload.notifications,
          borderColor: COLORS.primary,
          backgroundColor: COLORS.primaryLight,
          fill: true,
          tension: 0.3,
          borderWidth: 2,
          pointRadius: caseload.notifications.map((_, i) =>
            i === lastIndex && caseloadPartialLast ? 5 : 3),
          pointBackgroundColor: caseload.notifications.map((_, i) =>
            i === lastIndex && caseloadPartialLast ? '#ffffff' : COLORS.primary),
          pointBorderColor: COLORS.primary,
          pointBorderWidth: 2,
          pointHoverRadius: 6,
        },
      ],
    };

    caseloadOptions = {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => {
              const i = items[0].dataIndex;
              return i === lastIndex && caseloadPartialLast
                ? `As at ${caseloadAsAtLabel}`
                : `End of ${items[0].label}`;
            },
            label: (item) => {
              const count = item.parsed.y;
              return `${count} notification${count === 1 ? '' : 's'} still open`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { size: 11 } },
        },
        y: {
          beginAtZero: true,
          ticks: { precision: 0, font: { size: 11 } },
          grid: { color: 'rgba(0,0,0,0.04)' },
          title: {
            display: true,
            text: 'Open notifications',
            font: { size: 12, family: 'Inter, sans-serif' },
            color: '#6b7280',
          },
        },
      },
    };
  }

  // --- Industry Phase 1 Duration Comparison ---
  const industryDurationField = calendarDays ? 'average_calendar_days' : 'average_business_days';
  const industryDurations = industry_phase1_duration || [];

  // "Overall" reference bar, covering every industry, slotted in by value
  // alongside the rest rather than pinned to an end.
  const overallEntry = phase1_duration.stats.average != null ? {
    code: null,
    name: 'Overall',
    average_business_days: phase1_duration.stats.average,
    median_business_days: phase1_duration.stats.median,
    average_calendar_days: phase1_duration.calendar_stats.average,
    median_calendar_days: phase1_duration.calendar_stats.median,
    count: phase1_duration.stats.count,
  } : null;

  // Chart.js renders index 0 at the top of a horizontal bar chart, so sort
  // descending by the currently displayed metric to put the longest
  // durations at the top.
  const industryChartRows = (overallEntry ? [...industryDurations, overallEntry] : industryDurations)
    .slice()
    .sort((a, b) => b[industryDurationField] - a[industryDurationField]);

  const industryDurationData = {
    labels: industryChartRows.map(d => d.name),
    datasets: [
      {
        label: `Avg phase 1 duration (${dayLabel})`,
        data: industryChartRows.map(d => d[industryDurationField]),
        backgroundColor: industryChartRows.map(d => d.code === null ? COLORS.accent : COLORS.primary),
        borderRadius: 4,
        maxBarThickness: 22,
      },
    ],
  };

  const handleIndustryChartClick = (event, elements) => {
    if (elements.length > 0) {
      const { index } = elements[0];
      const industry = industryChartRows[index];
      if (industry && industry.code !== null) {
        navigate(industryPath(industry.code, industry.name));
      }
    }
  };

  const industryDurationOptions = {
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    onClick: handleIndustryChartClick,
    onHover: (event, elements) => {
      event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (item) => {
            const d = industryChartRows[item.dataIndex];
            return [
              `Avg: ${d.average_business_days} business days (${d.average_calendar_days} calendar)`,
              `Median: ${d.median_business_days} business days (${d.median_calendar_days} calendar)`,
              `${d.count} completed review${d.count === 1 ? '' : 's'}`,
            ];
          },
        },
      },
    },
    scales: {
      x: {
        beginAtZero: true,
        title: {
          display: true,
          text: calendarDays ? 'Average calendar days' : 'Average business days',
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
        grid: { color: 'rgba(0,0,0,0.04)' },
        ticks: { font: { size: 11 } },
      },
      y: {
        grid: { display: false },
        ticks: { font: { size: 11 } },
      },
    },
  };

  return (
    <>
      <SEO
        title={PAGE_META.title}
        description={PAGE_META.description}
        url="/analysis"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        {/* The page leads straight into content, so the document's h1 is
            visually hidden rather than dropped: it names the page for screen
            readers and keeps the heading outline starting at level 1. */}
        <h1 className="sr-only">Analysis</h1>

        {/* Summary Stat Cards */}
        <div className="mb-8">
          <div className="flex justify-end mb-3">
            <SegmentedToggle
              ariaLabel="Day count"
              options={[
                { value: false, label: 'Business days' },
                { value: true, label: 'Calendar days' },
              ]}
              value={calendarDays}
              onChange={setCalendarDays}
            />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {/* Notifications phase 1 */}
            <div className={`${CARD} overflow-hidden`}>
              <div className="px-5 py-3 bg-primary">
                <p className="text-sm font-semibold text-white">Notifications phase 1</p>
              </div>
              <div className="grid grid-cols-2 divide-x divide-gray-100">
                <div className="p-5">
                  <p className={SECTION_HEADING}>Avg duration</p>
                  <p className="text-2xl font-bold text-gray-900 mt-1.5 tracking-tight">
                    {phase1Stats.average ? `${phase1Stats.average} days` : 'N/A'}
                  </p>
                  {phase1Stats.count && (
                    <p className="text-sm text-gray-500 mt-0.5">{phase1Stats.count} completed</p>
                  )}
                </div>
                <div className="p-5">
                  <p className={SECTION_HEADING}>Median duration</p>
                  <p className="text-2xl font-bold text-gray-900 mt-1.5 tracking-tight">
                    {phase1Stats.median ? `${phase1Stats.median} days` : 'N/A'}
                  </p>
                  {phase1Stats.min && phase1Stats.max && (
                    <p className="text-sm text-gray-500 mt-0.5">Range {phase1Stats.min}–{phase1Stats.max} days</p>
                  )}
                </div>
              </div>
            </div>

            {/* Waivers */}
            <div className={`${CARD} overflow-hidden`}>
              <div className="px-5 py-3 bg-primary">
                <p className="text-sm font-semibold text-white">Waivers</p>
              </div>
              <div className="grid grid-cols-2 divide-x divide-gray-100">
                <div className="p-5">
                  <p className={SECTION_HEADING}>Avg duration</p>
                  <p className="text-2xl font-bold text-gray-900 mt-1.5 tracking-tight">
                    {waiverStats.average ? `${waiverStats.average} days` : 'N/A'}
                  </p>
                  {waiverStats.count && (
                    <p className="text-sm text-gray-500 mt-0.5">{waiverStats.count} completed</p>
                  )}
                </div>
                <div className="p-5">
                  <p className={SECTION_HEADING}>Median duration</p>
                  <p className="text-2xl font-bold text-gray-900 mt-1.5 tracking-tight">
                    {waiverStats.median ? `${waiverStats.median} days` : 'N/A'}
                  </p>
                  {waiverStats.min && waiverStats.max && (
                    <p className="text-sm text-gray-500 mt-0.5">Range {waiverStats.min}–{waiverStats.max} days</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Monthly Volume */}
        <div className="grid grid-cols-1 gap-6 mb-8">
          <div className={`${CARD} overflow-hidden`}>
            <div className="px-6 py-5 border-b border-gray-100">
              <h2 id="chart-monthly-volume-title" className="text-base font-semibold text-gray-900">Monthly notification volume</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Number of merger notifications and waiver applications per month
              </p>
            </div>
            <div className="p-6">
              <div
                className="h-72"
                role="img"
                aria-labelledby="chart-monthly-volume-title"
                aria-describedby="chart-monthly-volume-summary"
              >
                <Bar data={monthlyVolumeData} options={monthlyVolumeOptions} role="presentation" />
              </div>
              <div className="sr-only">
                <table id="chart-monthly-volume-summary">
                  <caption>Merger notifications and waiver applications per month</caption>
                  <thead><tr><th>Month</th><th>Notifications</th><th>Waivers</th></tr></thead>
                  <tbody>
                    {monthly_volume.labels.map((month, i) => (
                      <tr key={month}>
                        <td>{formatMonthLabel(month)}</td>
                        <td>{monthly_volume.notifications[i]}</td>
                        <td>{monthly_volume.waivers[i]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-gray-500 mt-3">
                Waivers are recorded on the ACCC's register when they are decided. This means the number of waiver applications in a month can rise for up to 25 business days after the month ends.
              </p>
            </div>
          </div>
        </div>

        {/* Open caseload */}
        {hasCaseload && (
          <section className="mb-8">
            <div className={`${CARD} overflow-hidden`}>
              <div className="px-6 py-5 border-b border-gray-100">
                <h2 id="chart-caseload-title" className="text-base font-semibold text-gray-900">
                  Open caseload &ndash; notifications
                </h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  Notifications still before the ACCC at each month end
                </p>
              </div>
              <div className="p-6">
                <div className="flex flex-wrap gap-x-10 gap-y-3 mb-5">
                  <div>
                    <p className={SECTION_HEADING}>Open now</p>
                    <p className="text-2xl font-bold text-gray-900 mt-1.5 tracking-tight">
                      {caseloadLatest}
                    </p>
                    {caseloadAsAtLabel && (
                      <p className="text-sm text-gray-500 mt-0.5">as at {caseloadAsAtLabel}</p>
                    )}
                  </div>
                  {caseloadDelta !== null && (
                    <div>
                      <p className={SECTION_HEADING}>Change</p>
                      <p className="text-2xl font-bold text-gray-900 mt-1.5 tracking-tight">
                        {caseloadDelta > 0 ? '+' : ''}{caseloadDelta}
                      </p>
                      <p className="text-sm text-gray-500 mt-0.5">since {caseloadDeltaFrom}</p>
                    </div>
                  )}
                </div>
                <div
                  className="h-72"
                  role="img"
                  aria-labelledby="chart-caseload-title"
                  aria-describedby="chart-caseload-summary"
                >
                  <Line data={caseloadData} options={caseloadOptions} role="presentation" />
                </div>
                <div className="sr-only">
                  <table id="chart-caseload-summary">
                    <caption>Open notifications at each month end</caption>
                    <thead><tr><th>Month</th><th>Open notifications</th></tr></thead>
                    <tbody>
                      {caseload.labels.map((month, i) => (
                        <tr key={month}>
                          <td>{formatMonthLabel(month)}</td>
                          <td>{caseload.notifications[i]}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Industry Phase 1 Duration Comparison */}
        {industryDurations.length > 0 && (
          <section className="mb-8">
            <div className={`${CARD} overflow-hidden`}>
              <div className="px-6 py-5 border-b border-gray-100">
                <h2 id="chart-industry-duration-title" className="text-base font-semibold text-gray-900">Phase 1 duration by industry</h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  Average phase 1 duration for completed reviews, by top-level industry. Click a bar to view that industry.
                </p>
              </div>
              <div className="p-6">
                <div
                  style={{ height: `${Math.max(320, industryChartRows.length * 32)}px` }}
                  role="img"
                  aria-labelledby="chart-industry-duration-title"
                  aria-describedby="chart-industry-duration-summary"
                >
                  <Bar data={industryDurationData} options={industryDurationOptions} role="presentation" />
                </div>
                <div className="sr-only">
                  <table id="chart-industry-duration-summary">
                    <caption>Average phase 1 duration by industry, in {dayLabel}</caption>
                    <thead><tr><th>Industry</th><th>Average duration ({dayLabel})</th><th>Completed reviews</th></tr></thead>
                    <tbody>
                      {industryChartRows.map((row) => (
                        <tr key={row.name}>
                          <td>{row.name}</td>
                          <td>{row[industryDurationField]}</td>
                          <td>{row.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Phase 1 Duration ECDF */}
        {ecdfPoints.length > 0 && (
          <section className="mb-8">
            <div className={`${CARD} overflow-hidden`}>
              <div className="px-6 py-5 border-b border-gray-100">
                <h2 id="chart-phase1-ecdf-title" className="text-base font-semibold text-gray-900">
                  Phase 1 duration: share of reviews concluded
                </h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  Proportion of phase 1 reviews completed by the given number of {dayLabel}.
                </p>
              </div>
              <div className="p-6">
                <DurationEcdfChart
                  points={ecdfPoints}
                  median={phase1Stats.median}
                  deadline={phase1Deadline}
                  dayLabel={dayLabel}
                  seriesLabel="% of reviews concluded"
                  color={COLORS.primary}
                  titleId="chart-phase1-ecdf-title"
                  summaryId="chart-phase1-ecdf-summary"
                  caption={`Cumulative share of completed phase 1 reviews concluded by ${dayLabel}`}
                  countHeading="Reviews concluded"
                  minAxisMax={PHASE_1_DEADLINE_BD}
                />
              </div>
            </div>
          </section>
        )}

        {/* Waiver Duration ECDF */}
        {waiverEcdfPoints.length > 0 && (
          <section className="mb-8">
            <div className={`${CARD} overflow-hidden`}>
              <div className="px-6 py-5 border-b border-gray-100">
                <h2 id="chart-waiver-ecdf-title" className="text-base font-semibold text-gray-900">
                  Waiver duration: share of applications concluded
                </h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  Proportion of waiver applications decided by the given number of {dayLabel}.
                </p>
              </div>
              <div className="p-6">
                <DurationEcdfChart
                  points={waiverEcdfPoints}
                  median={waiverStats.median}
                  deadline={waiverDeadline}
                  dayLabel={dayLabel}
                  seriesLabel="% of waivers concluded"
                  color={COLORS.teal}
                  titleId="chart-waiver-ecdf-title"
                  summaryId="chart-waiver-ecdf-summary"
                  caption={`Cumulative share of waiver applications decided by ${dayLabel}`}
                  countHeading="Waivers decided"
                  minAxisMax={WAIVER_DEADLINE_BD}
                />
              </div>
            </div>
          </section>
        )}

      </div>
    </>
  );
}

export default Analysis;
