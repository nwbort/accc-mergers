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
import UpcomingEventsTimeline from '../components/UpcomingEventsTimeline';
import RecentDeterminationsCards from '../components/RecentDeterminationsCards';
import RecentMergersCards from '../components/RecentMergersCards';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { getDaysRemaining, isDatePast } from '../utils/dates';
import { useFetchData } from '../hooks/useFetchData';
import { markItemsAsSeen } from '../utils/lastVisit';

ChartJS.register(
  Title,
  Tooltip,
  Legend,
  ArcElement
);

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
  if (error) return <div role="alert" className="text-red-600 p-8 text-center">Error: {error}</div>;
  if (!stats) return null;

  const determinationData = {
    labels: Object.keys(stats.by_determination),
    datasets: [
      {
        data: Object.values(stats.by_determination),
        backgroundColor: ['#335145', '#e07a5f', '#6b8f7f', '#8cafa0'],
        borderWidth: 0,
        borderRadius: 4,
      },
    ],
  };

  const waiverLabels = ['Approved', 'Not approved'].filter(
    (label) => stats.by_waiver_determination && stats.by_waiver_determination[label]
  );
  const waiverDeterminationData = {
    labels: waiverLabels,
    datasets: [
      {
        data: waiverLabels.map((label) => stats.by_waiver_determination[label]),
        backgroundColor: waiverLabels.map((label) =>
          label === 'Approved' ? '#335145' : '#e07a5f'
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
        title="Australian Merger Tracker | ACCC Merger Reviews & M&A Data"
        description="Live stats on every ACCC merger review — recent clearances, upcoming deadlines, phase durations, and determination trends across Australian industries."
        url="/"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      <h1 className="sr-only">Australian merger tracker dashboard</h1>
      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 mb-8">
        <StatCard
          title="Mergers"
          value={`${stats.by_status['Under assessment'] || 0} under assessment`}
          subtitle={`${stats.total_mergers} notified${stats.total_waivers ? ` and ${stats.total_waivers} waiver${stats.total_waivers !== 1 ? 's' : ''}` : ''}`}
          icon={<FaMagnifyingGlass />}
          href="/mergers?status=Under assessment"
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
              ? `${stats.phase_duration.median_business_days} business days`
              : 'N/A'
          }
          subtitle={
            stats.phase_duration.median_days
              ? `${stats.phase_duration.median_days} calendar days`
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

      {/* Upcoming Events (within 7 days) */}
      {upcomingEvents && (() => {
        const eventsWithin7Days = upcomingEvents.filter(event => {
          if (isDatePast(event.date)) return false;
          const daysRemaining = getDaysRemaining(event.date);
          return daysRemaining !== null && daysRemaining <= 7;
        });
        return eventsWithin7Days.length > 0 ? (
          <div className="mb-8">
            <UpcomingEventsTimeline events={eventsWithin7Days} />
          </div>
        ) : null;
      })()}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
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
            <table id="chart-phase1-summary" className="sr-only">
              <caption>Phase 1 determination breakdown</caption>
              <thead><tr><th>Determination</th><th>Count</th></tr></thead>
              <tbody>
                {Object.entries(stats.by_determination).map(([det, count]) => (
                  <tr key={det}><td>{det}</td><td>{count}</td></tr>
                ))}
              </tbody>
            </table>
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
            <table id="chart-waiver-summary" className="sr-only">
              <caption>Waiver determination breakdown</caption>
              <thead><tr><th>Determination</th><th>Count</th></tr></thead>
              <tbody>
                {Object.entries(stats.by_waiver_determination).map(([det, count]) => (
                  <tr key={det}><td>{det}</td><td>{count}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
    </>
  );
}

export default Dashboard;
