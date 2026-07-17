import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Scatter, Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { industryPath } from '../utils/slug';
import { CHART_PALETTE as COLORS, THEME_HEXES } from '../constants/chartColors';
import { CARD, SECTION_HEADING } from '../utils/classNames';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend
);

function formatMonthLabel(yyyymm) {
  const [year, month] = yyyymm.split('-');
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${months[parseInt(month, 10) - 1]} ${year}`;
}

// ECDF of completed-matter durations: "X% of reviews conclude by day N".
// Right-continuous — the cumulative percentage jumps at each distinct
// duration and holds flat until the next one (Chart.js stepped: 'after').
function computeEcdf(scatterData, dayField) {
  const durations = scatterData
    .filter(d => d.in_progress !== true)
    .map(d => d[dayField])
    .sort((a, b) => a - b);

  const total = durations.length;
  if (total === 0) return [];

  const points = [{ x: 0, y: 0, n: 0, total }];
  let cumulative = 0;
  let i = 0;
  while (i < durations.length) {
    const value = durations[i];
    let count = 0;
    while (i < durations.length && durations[i] === value) {
      count += 1;
      i += 1;
    }
    cumulative += count;
    points.push({ x: value, y: Math.round((cumulative / total) * 1000) / 10, n: cumulative, total });
  }
  return points;
}

function Analysis() {
  const { data, loading, error } = useFetchData(API_ENDPOINTS.analysis, {
    cacheKey: 'analysis-data',
  });
  const navigate = useNavigate();
  const [calendarDays, setCalendarDays] = useState(false);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;
  if (!data) return null;

  const { phase1_duration, waiver_duration, monthly_volume, industry_phase1_duration, clearance_by_duration } = data;
  const phase1Stats = calendarDays ? phase1_duration.calendar_stats : phase1_duration.stats;
  const waiverStats = calendarDays ? waiver_duration.calendar_stats : waiver_duration.stats;

  const dayField = calendarDays ? 'calendar_days' : 'business_days';
  const dayLabel = calendarDays ? 'calendar days' : 'business days';

  // --- Phase 1 Duration ECDF ---
  const ecdfPoints = computeEcdf(phase1_duration.durations, dayField);
  const ecdfMedian = phase1Stats.median;
  const ecdfMaxX = ecdfPoints.length > 0
    ? Math.max(ecdfPoints[ecdfPoints.length - 1].x, 30) + 2
    : 30;

  const phase1EcdfData = {
    datasets: [
      ...(!calendarDays ? [{
        label: 'BD 30 deadline',
        data: [{ x: 30, y: 0 }, { x: 30, y: 100 }],
        borderColor: COLORS.accent,
        borderDash: [6, 4],
        borderWidth: 1.5,
        pointRadius: 0,
        showLine: true,
      }] : []),
      ...(ecdfMedian != null ? [{
        label: `Median (${ecdfMedian} ${dayLabel})`,
        data: [{ x: ecdfMedian, y: 0 }, { x: ecdfMedian, y: 100 }],
        borderColor: '#9ca3af',
        borderDash: [4, 4],
        borderWidth: 1.5,
        pointRadius: 0,
        showLine: true,
      }] : []),
      {
        label: '% of reviews concluded',
        data: ecdfPoints,
        borderColor: COLORS.primary,
        backgroundColor: COLORS.primary,
        stepped: 'before',
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 5,
        showLine: true,
      },
    ],
  };

  const phase1EcdfOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          usePointStyle: true,
          padding: 16,
          font: { size: 12, family: 'Inter, sans-serif' },
        },
      },
      tooltip: {
        callbacks: {
          label: (item) => {
            if (item.dataset.label !== '% of reviews concluded') return item.dataset.label;
            const { x, y, n, total } = item.raw;
            return `by BD ${x}: ${y}% (${n} of ${total})`;
          },
        },
      },
    },
    scales: {
      x: {
        type: 'linear',
        min: 0,
        max: ecdfMaxX,
        title: {
          display: true,
          text: calendarDays ? 'Calendar days' : 'Business days',
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
        grid: { color: 'rgba(0,0,0,0.04)' },
        ticks: { font: { size: 11 } },
      },
      y: {
        min: 0,
        max: 100,
        title: {
          display: true,
          text: '% of reviews concluded',
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
        grid: { color: 'rgba(0,0,0,0.04)' },
        ticks: { font: { size: 11 }, callback: (value) => `${value}%` },
      },
    },
  };

  // --- Waiver Duration ECDF ---
  const waiverEcdfPoints = computeEcdf(waiver_duration.durations, dayField);
  const waiverEcdfMedian = waiverStats.median;
  const waiverEcdfMaxX = waiverEcdfPoints.length > 0
    ? Math.max(waiverEcdfPoints[waiverEcdfPoints.length - 1].x, 25) + 2
    : 25;

  const waiverEcdfData = {
    datasets: [
      ...(!calendarDays ? [{
        label: 'BD 25 deadline',
        data: [{ x: 25, y: 0 }, { x: 25, y: 100 }],
        borderColor: COLORS.accent,
        borderDash: [6, 4],
        borderWidth: 1.5,
        pointRadius: 0,
        showLine: true,
      }] : []),
      ...(waiverEcdfMedian != null ? [{
        label: `Median (${waiverEcdfMedian} ${dayLabel})`,
        data: [{ x: waiverEcdfMedian, y: 0 }, { x: waiverEcdfMedian, y: 100 }],
        borderColor: '#9ca3af',
        borderDash: [4, 4],
        borderWidth: 1.5,
        pointRadius: 0,
        showLine: true,
      }] : []),
      {
        label: '% of waivers concluded',
        data: waiverEcdfPoints,
        borderColor: COLORS.teal,
        backgroundColor: COLORS.teal,
        stepped: 'before',
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 5,
        showLine: true,
      },
    ],
  };

  const waiverEcdfOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          usePointStyle: true,
          padding: 16,
          font: { size: 12, family: 'Inter, sans-serif' },
        },
      },
      tooltip: {
        callbacks: {
          label: (item) => {
            if (item.dataset.label !== '% of waivers concluded') return item.dataset.label;
            const { x, y, n, total } = item.raw;
            return `by day ${x}: ${y}% (${n} of ${total})`;
          },
        },
      },
    },
    scales: {
      x: {
        type: 'linear',
        min: 0,
        max: waiverEcdfMaxX,
        title: {
          display: true,
          text: calendarDays ? 'Calendar days' : 'Business days',
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
        grid: { color: 'rgba(0,0,0,0.04)' },
        ticks: { font: { size: 11 } },
      },
      y: {
        min: 0,
        max: 100,
        title: {
          display: true,
          text: '% of waivers concluded',
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
        grid: { color: 'rgba(0,0,0,0.04)' },
        ticks: { font: { size: 11 }, callback: (value) => `${value}%` },
      },
    },
  };

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

  // --- Phase 1 outcome by review length ---
  // Always measured in business days: the framing is the 30-business-day Phase 1
  // statutory clock, so this chart ignores the calendar/business toggle above.
  const clearanceBuckets = clearance_by_duration?.buckets || [];
  const clearanceHasReferrals = clearanceBuckets.some(b => b.referred > 0);
  const REFERRED_COLOR = THEME_HEXES.phase2Referral;

  const clearanceData = {
    labels: clearanceBuckets.map(b => b.label),
    datasets: [
      {
        label: 'Cleared in phase 1',
        data: clearanceBuckets.map(b => b.cleared),
        backgroundColor: COLORS.primary,
        borderRadius: 4,
        maxBarThickness: 56,
      },
      {
        label: 'Referred to phase 2',
        data: clearanceBuckets.map(b => b.referred),
        backgroundColor: REFERRED_COLOR,
        borderRadius: 4,
        maxBarThickness: 56,
      },
    ],
  };

  const clearanceOptions = {
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
      tooltip: {
        callbacks: {
          afterBody: (items) => {
            const bucket = clearanceBuckets[items[0].dataIndex];
            if (!bucket || bucket.total === 0) return '';
            const pct = Math.round((bucket.referral_rate ?? 0) * 100);
            return `Referred to phase 2: ${pct}% (${bucket.referred} of ${bucket.total})`;
          },
        },
      },
    },
    scales: {
      x: {
        stacked: true,
        grid: { display: false },
        ticks: { font: { size: 11 } },
        title: {
          display: true,
          text: 'Phase 1 duration (business days)',
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
      },
      y: {
        stacked: true,
        beginAtZero: true,
        ticks: { precision: 0, font: { size: 11 } },
        grid: { color: 'rgba(0,0,0,0.04)' },
        title: {
          display: true,
          text: 'Completed reviews',
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
      },
    },
  };

  const clearedMedian = clearance_by_duration?.cleared?.median_business_days;
  const referredMedian = clearance_by_duration?.referred?.median_business_days;
  const overallReferralPct = clearance_by_duration?.overall_referral_rate != null
    ? Math.round(clearance_by_duration.overall_referral_rate * 100)
    : null;

  return (
    <>
      <SEO
        title="Analysis"
        description="Data-driven analysis of ACCC merger reviews: Phase 1 and Phase 2 durations, waiver processing times, clearance rates, and year-on-year determination trends."
        url="/analysis"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        {/* Summary Stat Cards */}
        <div className="mb-8">
          <div className="flex justify-end mb-3">
            <div className="inline-flex items-center bg-gray-100 rounded-full p-0.5 text-sm">
              <button
                onClick={() => setCalendarDays(false)}
                className={`px-3.5 py-1.5 rounded-full font-medium transition-all duration-150 ${!calendarDays ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
              >
                Business days
              </button>
              <button
                onClick={() => setCalendarDays(true)}
                className={`px-3.5 py-1.5 rounded-full font-medium transition-all duration-150 ${calendarDays ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
              >
                Calendar days
              </button>
            </div>
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
              <h2 className="text-base font-semibold text-gray-900">Monthly notification volume</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Number of merger notifications and waiver applications per month
              </p>
            </div>
            <div className="p-6">
              <div className="h-72">
                <Bar data={monthlyVolumeData} options={monthlyVolumeOptions} />
              </div>
              <p className="text-xs text-gray-500 mt-3">
                Waivers are recorded on the ACCC's register when they are decided. This means the number of waiver applications in a month can rise for up to 25 business days after the month ends.
              </p>
            </div>
          </div>
        </div>

        {/* Industry Phase 1 Duration Comparison */}
        {industryDurations.length > 0 && (
          <section className="mb-8">
            <div className={`${CARD} overflow-hidden`}>
              <div className="px-6 py-5 border-b border-gray-100">
                <h2 className="text-lg font-semibold text-gray-900">Phase 1 duration by industry</h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  Average phase 1 duration for completed reviews, by top-level industry. Click a bar to view that industry.
                </p>
              </div>
              <div className="p-6">
                <div style={{ height: `${Math.max(320, industryChartRows.length * 32)}px` }}>
                  <Bar data={industryDurationData} options={industryDurationOptions} />
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
                <h2 id="chart-phase1-ecdf-title" className="text-lg font-semibold text-gray-900">
                  Phase 1 duration: share of reviews concluded
                </h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  Proportion of phase 1 reviews completed by the given number of {dayLabel}.
                </p>
              </div>
              <div className="p-6">
                <div
                  className="h-80"
                  role="img"
                  aria-labelledby="chart-phase1-ecdf-title"
                  aria-describedby="chart-phase1-ecdf-summary"
                >
                  <Scatter data={phase1EcdfData} options={phase1EcdfOptions} />
                </div>
                <div className="sr-only">
                  <table id="chart-phase1-ecdf-summary">
                    <caption>Cumulative share of completed phase 1 reviews concluded by {dayLabel}</caption>
                    <thead><tr><th>By {dayLabel === 'calendar days' ? 'calendar day' : 'business day'}</th><th>% concluded</th><th>Reviews concluded</th></tr></thead>
                    <tbody>
                      {ecdfPoints.filter(p => p.x > 0).map(p => (
                        <tr key={p.x}>
                          <td>{p.x}</td>
                          <td>{p.y}%</td>
                          <td>{p.n} of {p.total}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Phase 1 outcome by review length */}
        {clearanceBuckets.length > 0 && clearance_by_duration.total_completed > 0 && (
          <section className="mb-8">
            <div className={`${CARD} overflow-hidden`}>
              <div className="px-6 py-5 border-b border-gray-100">
                <h2 id="chart-clearance-title" className="text-lg font-semibold text-gray-900">
                  Clearance vs phase 2 referral, by review length
                </h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  Completed phase 1 reviews grouped by how long they ran, split between matters cleared in phase 1 and matters referred to phase 2.
                </p>
              </div>
              <div className="p-6">
                {(clearedMedian != null || overallReferralPct != null) && (
                  <p className="text-sm text-gray-600 mb-4">
                    Reviews cleared in phase 1 conclude in a median of{' '}
                    <span className="font-semibold text-gray-900">{clearedMedian} business days</span>
                    {referredMedian != null && (
                      <>
                        , while those referred to phase 2 run to a median of{' '}
                        <span className="font-semibold text-gray-900">{referredMedian} business days</span>
                      </>
                    )}
                    . Overall,{' '}
                    <span className="font-semibold text-gray-900">{overallReferralPct}%</span>{' '}
                    of the {clearance_by_duration.total_completed} completed reviews were referred — but that risk is concentrated in the reviews that run to the end of the 30-business-day statutory clock and beyond.
                  </p>
                )}
                <div
                  className="h-80"
                  role="img"
                  aria-labelledby="chart-clearance-title"
                  aria-describedby="chart-clearance-summary"
                >
                  <Bar data={clearanceData} options={clearanceOptions} />
                </div>
                <div className="sr-only">
                  <table id="chart-clearance-summary">
                    <caption>Phase 1 outcome by review length in business days</caption>
                    <thead><tr><th>Duration</th><th>Cleared in phase 1</th><th>Referred to phase 2</th><th>Referral rate</th></tr></thead>
                    <tbody>
                      {clearanceBuckets.map(b => (
                        <tr key={b.label}>
                          <td>{b.label}</td>
                          <td>{b.cleared}</td>
                          <td>{b.referred}</td>
                          <td>{b.total > 0 ? `${Math.round((b.referral_rate ?? 0) * 100)}%` : 'n/a'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="text-xs text-gray-500 mt-3">
                  A referral to phase 2 is decided at the end of the phase 1 clock, so referred matters have longer phase 1 durations by construction. The pattern still shows that clearances land well before the deadline, while reviews still open near or past day 30 are increasingly likely to be referred.
                  {clearanceHasReferrals && clearance_by_duration.referred?.count != null && (
                    <> Phase 2 referrals remain rare ({clearance_by_duration.referred.count} to date), so bucket rates are based on small numbers.</>
                  )}
                </p>
              </div>
            </div>
          </section>
        )}

        {/* Waiver Duration ECDF */}
        {waiverEcdfPoints.length > 0 && (
          <section className="mb-8">
            <div className={`${CARD} overflow-hidden`}>
              <div className="px-6 py-5 border-b border-gray-100">
                <h2 id="chart-waiver-ecdf-title" className="text-lg font-semibold text-gray-900">
                  Waiver duration: share of applications concluded
                </h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  Proportion of waiver applications decided by the given number of {dayLabel}.
                </p>
              </div>
              <div className="p-6">
                <div
                  className="h-80"
                  role="img"
                  aria-labelledby="chart-waiver-ecdf-title"
                  aria-describedby="chart-waiver-ecdf-summary"
                >
                  <Scatter data={waiverEcdfData} options={waiverEcdfOptions} />
                </div>
                <div className="sr-only">
                  <table id="chart-waiver-ecdf-summary">
                    <caption>Cumulative share of waiver applications decided by {dayLabel}</caption>
                    <thead><tr><th>By {dayLabel === 'calendar days' ? 'calendar day' : 'business day'}</th><th>% concluded</th><th>Waivers decided</th></tr></thead>
                    <tbody>
                      {waiverEcdfPoints.filter(p => p.x > 0).map(p => (
                        <tr key={p.x}>
                          <td>{p.x}</td>
                          <td>{p.y}%</td>
                          <td>{p.n} of {p.total}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </section>
        )}

      </div>
    </>
  );
}

export default Analysis;
