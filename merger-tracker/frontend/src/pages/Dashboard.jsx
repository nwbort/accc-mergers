import { useEffect } from 'react';
import { FaMagnifyingGlass, FaStopwatch, FaChartLine } from 'react-icons/fa6';
import { Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  ArcElement,
} from 'chart.js';
import StatCard from '../components/StatCard';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import UpcomingEventsTimeline from '../components/UpcomingEventsTimeline';
import RecentDeterminationsCards from '../components/RecentDeterminationsCards';
import RecentMergersCards from '../components/RecentMergersCards';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { getCalendarDaysUntil, isDatePast } from '../utils/dates';
import { useFetchData } from '../hooks/useFetchData';
import { markItemsAsSeen } from '../utils/lastVisit';
import { formatMedian } from '../utils/formatMedian';
import { CHART_PALETTE, CHART_PALETTE_ORDER, DETERMINATION_COLORS } from '../constants/chartColors';
import { MERGER_STATUS } from '../constants/mergerStatus';
import { STATIC_PAGE_META } from '../utils/pageMeta';

// Title and description live in the shared table so this page and the
// build-time prerenderer emit the same <head>.
const PAGE_META = STATIC_PAGE_META['/'];

ChartJS.register(
  Title,
  Tooltip,
  Legend,
  ArcElement
);

// Fixed segment order for the Phase 2 doughnut, running cleared → blocked, so
// the chart doesn't reshuffle as determinations land. "Assessment ceased" sits
// last because it isn't a determination at all — it's a Phase 2 review the
// parties withdrew from.
const PHASE_2_OUTCOME_ORDER = [
  MERGER_STATUS.APPROVED,
  MERGER_STATUS.APPROVED_WITH_CONDITIONS,
  MERGER_STATUS.NOT_OPPOSED,
  MERGER_STATUS.NOT_APPROVED,
  MERGER_STATUS.DECLINED,
  MERGER_STATUS.ASSESSMENT_CEASED,
];

function Dashboard() {
  const { data: stats, loading, error } = useFetchData(API_ENDPOINTS.stats, {
    cacheKey: 'dashboard-stats',
  });
  // A failed upcoming-events fetch shouldn't block the page — we just omit the
  // section. Errors are logged by the hook.
  const { data: upcomingEventsData } = useFetchData(API_ENDPOINTS.upcomingEvents, {
    cacheKey: 'dashboard-events',
  });
  const upcomingEvents = upcomingEventsData?.events ?? null;

  // Mark items as seen after user has viewed them for 2 seconds
  // This ensures the "New" badge persists across refreshes
  useEffect(() => {
    if (!stats) return;

    const timer = setTimeout(() => {
      const itemIds = [];
      if (stats.recent_mergers) {
        itemIds.push(...stats.recent_mergers.map(m => m.merger_id));
      }
      if (stats.recent_determinations) {
        itemIds.push(...stats.recent_determinations.map(d => d.merger_id));
      }
      markItemsAsSeen(itemIds);
    }, 2000); // 2 second delay to ensure user actually viewed the content

    return () => clearTimeout(timer);
  }, [stats]);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;
  if (!stats) return null;

  const determinationLabels = Object.keys(stats.by_determination);
  const determinationData = {
    labels: determinationLabels,
    datasets: [
      {
        data: Object.values(stats.by_determination),
        backgroundColor: determinationLabels.map((label, i) =>
          DETERMINATION_COLORS[label] || CHART_PALETTE_ORDER[i % CHART_PALETTE_ORDER.length]
        ),
        borderWidth: 0,
        borderRadius: 4,
      },
    ],
  };

  // Concluded Phase 2 reviews only — matters still in Phase 2 have no outcome
  // to chart yet. Any outcome the fixed order doesn't know about is appended
  // rather than dropped.
  const phase2Counts = stats.by_phase_2_determination || {};
  const phase2Labels = [
    ...PHASE_2_OUTCOME_ORDER.filter((label) => phase2Counts[label]),
    ...Object.keys(phase2Counts).filter((label) => !PHASE_2_OUTCOME_ORDER.includes(label)),
  ];
  const phase2DeterminationData = {
    labels: phase2Labels,
    datasets: [
      {
        data: phase2Labels.map((label) => phase2Counts[label]),
        backgroundColor: phase2Labels.map((label, i) =>
          DETERMINATION_COLORS[label] || CHART_PALETTE_ORDER[i % CHART_PALETTE_ORDER.length]
        ),
        borderWidth: 0,
        borderRadius: 4,
      },
    ],
  };

  const waiverLabels = [MERGER_STATUS.APPROVED, MERGER_STATUS.NOT_APPROVED].filter(
    (label) => stats.by_waiver_determination && stats.by_waiver_determination[label]
  );
  const waiverDeterminationData = {
    labels: waiverLabels,
    datasets: [
      {
        data: waiverLabels.map((label) => stats.by_waiver_determination[label]),
        backgroundColor: waiverLabels.map((label) =>
          DETERMINATION_COLORS[label] || CHART_PALETTE.accent
        ),
        borderWidth: 0,
        borderRadius: 4,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    cutout: '65%',
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          padding: 16,
          usePointStyle: true,
          pointStyle: 'circle',
          font: {
            size: 12,
            family: 'Inter, sans-serif',
          },
        },
      },
      tooltip: {
        callbacks: {
          label: (item) => {
            const total = item.dataset.data.reduce((sum, val) => sum + val, 0);
            const pct = total > 0 ? Math.round((item.parsed / total) * 100) : 0;
            return ` ${item.parsed} (${pct}%)`;
          },
        },
      },
    },
  };

  return (
    <>
      <SEO
        title={PAGE_META.title}
        description={PAGE_META.description}
        url="/"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      <h1 className="sr-only">Australian merger tracker dashboard</h1>
      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 mb-8">
        <StatCard
          title="Mergers"
          value={`${stats.by_status[MERGER_STATUS.UNDER_ASSESSMENT] || 0} under assessment`}
          subtitle={`${stats.total_mergers} notified${stats.total_waivers ? ` and ${stats.total_waivers} waiver${stats.total_waivers !== 1 ? 's' : ''}` : ''}`}
          icon={<FaMagnifyingGlass />}
          href={`/mergers?status=${MERGER_STATUS.UNDER_ASSESSMENT}`}
        />
        <StatCard
          title="Average phase 1 duration"
          value={
            stats.phase_duration.average_business_days
              ? `${Math.round(stats.phase_duration.average_business_days)} business days`
              : 'N/A'
          }
          subtitle={
            stats.phase_duration.average_days
              ? `${Math.round(stats.phase_duration.average_days)} calendar days`
              : null
          }
          icon={<FaStopwatch />}
          href="/analysis"
        />
        <StatCard
          title="Median phase 1 duration"
          value={
            stats.phase_duration.median_business_days
              ? `${formatMedian(stats.phase_duration.median_business_days)} business days`
              : 'N/A'
          }
          subtitle={
            stats.phase_duration.median_days
              ? `${formatMedian(stats.phase_duration.median_days)} calendar days`
              : null
          }
          icon={<FaChartLine />}
          href="/analysis"
        />
      </div>

      {/* Recent Determinations */}
      {stats.recent_determinations && (
        <div className="mb-8">
          <RecentDeterminationsCards
            determinations={stats.recent_determinations}
          />
        </div>
      )}

      {/* Recently Notified Mergers */}
      {stats.recent_mergers && (
        <div className="mb-8">
          <RecentMergersCards mergers={stats.recent_mergers} />
        </div>
      )}

      {/* Upcoming Events: the next 7 days broken out day by day, plus the
          week after bundled into a single trailing "Later" entry (handled
          inside UpcomingEventsTimeline). Calendar-day counts so the cutoff
          agrees with the day counts the timeline renders for the same
          events. */}
      {upcomingEvents && (() => {
        const eventsWithin14Days = upcomingEvents.filter(event => {
          if (isDatePast(event.date)) return false;
          const daysRemaining = getCalendarDaysUntil(event.date);
          return daysRemaining !== null && daysRemaining <= 14;
        });
        return eventsWithin14Days.length > 0 ? (
          <div className="mb-8">
            <UpcomingEventsTimeline events={eventsWithin14Days} />
          </div>
        ) : null;
      })()}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-6">
        {/* Phase 1 Duration Table */}
        {stats.phase_duration.percentiles && (
          <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-card flex flex-col">
            <h2 className="text-base font-semibold text-gray-900 mb-5">
              Phase 1 duration
            </h2>
            <div className="grid grid-cols-[auto_1fr_auto] items-center gap-x-4 flex-1 content-around">
              {[
                { label: 'By day 15', data: stats.phase_duration.percentiles.day15 },
                { label: 'By day 20', data: stats.phase_duration.percentiles.day20 },
                { label: 'By day 30', data: stats.phase_duration.percentiles.day30 },
              ].flatMap(({ label, data }, index) => [
                <span key={`${label}-label`} className={`text-sm text-gray-600 py-3 ${index < 2 ? 'border-b border-gray-50' : ''}`}>{label}</span>,
                <div key={`${label}-bar`} className="bg-gray-100 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-primary h-1.5 rounded-full transition-all duration-500"
                    style={{ width: `${data.percentage}%` }}
                  />
                </div>,
                <span key={`${label}-pct`} className={`text-sm font-semibold text-gray-900 tabular-nums text-right py-3 whitespace-nowrap ${index < 2 ? 'border-b border-gray-50' : ''}`}>
                  {data.percentage}%
                  <span className="text-gray-500 font-normal ml-1">({data.count})</span>
                </span>,
              ])}
            </div>
          </div>
        )}

        {/* Phase 1 Determination Distribution */}
        {Object.keys(stats.by_determination).length > 0 && (
          <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-card">
            <h2 id="chart-phase1-title" className="text-base font-semibold text-gray-900 mb-5">
              Phase 1 determinations
            </h2>
            <div className="h-64" role="img" aria-labelledby="chart-phase1-title" aria-describedby="chart-phase1-summary">
              <Doughnut data={determinationData} options={chartOptions} />
            </div>
            {/* The sr-only wrapper has to be a div: `sr-only`'s width: 1px is
                only a minimum for a table box, so a bare sr-only table lays
                out at its full content width and — being absolutely
                positioned against the viewport — widens the whole page on
                mobile. The div clips it for real. */}
            <div className="sr-only">
              <table id="chart-phase1-summary">
                <caption>Phase 1 determination breakdown</caption>
                <thead><tr><th>Determination</th><th>Count</th></tr></thead>
                <tbody>
                  {Object.entries(stats.by_determination).map(([det, count]) => (
                    <tr key={det}><td>{det}</td><td>{count}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Phase 2 Determination Distribution */}
        {phase2Labels.length > 0 && (
          <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-card">
            <h2 id="chart-phase2-title" className="text-base font-semibold text-gray-900 mb-5">
              Phase 2 determinations
            </h2>
            <div className="h-64" role="img" aria-labelledby="chart-phase2-title" aria-describedby="chart-phase2-summary">
              <Doughnut data={phase2DeterminationData} options={chartOptions} />
            </div>
            <div className="sr-only">
              <table id="chart-phase2-summary">
                <caption>Phase 2 determination breakdown, including ceased assessments</caption>
                <thead><tr><th>Outcome</th><th>Count</th></tr></thead>
                <tbody>
                  {phase2Labels.map((det) => (
                    <tr key={det}><td>{det}</td><td>{phase2Counts[det]}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Waiver Determination Distribution */}
        {stats.by_waiver_determination && Object.keys(stats.by_waiver_determination).length > 0 && (
          <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-card">
            <h2 id="chart-waiver-title" className="text-base font-semibold text-gray-900 mb-5">
              Waiver determinations
            </h2>
            <div className="h-64" role="img" aria-labelledby="chart-waiver-title" aria-describedby="chart-waiver-summary">
              <Doughnut data={waiverDeterminationData} options={chartOptions} />
            </div>
            <div className="sr-only">
              <table id="chart-waiver-summary">
                <caption>Waiver determination breakdown</caption>
                <thead><tr><th>Determination</th><th>Count</th></tr></thead>
                <tbody>
                  {Object.entries(stats.by_waiver_determination).map(([det, count]) => (
                    <tr key={det}><td>{det}</td><td>{count}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
    </>
  );
}

export default Dashboard;
