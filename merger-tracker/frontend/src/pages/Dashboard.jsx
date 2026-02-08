import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Doughnut } from 'react-chartjs-2';
import StatusBadge from '../components/StatusBadge';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
} from 'chart.js';
import StatCard from '../components/StatCard';
import LoadingSpinner from '../components/LoadingSpinner';
import UpcomingEventsTable from '../components/UpcomingEventsTable';
import RecentDeterminationsTable from '../components/RecentDeterminationsTable';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { formatDate, getDaysRemaining, isDatePast } from '../utils/dates';
import { dataCache } from '../utils/dataCache';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
);

function Dashboard() {
  const [stats, setStats] = useState(() => dataCache.get('dashboard-stats') || null);
  const [upcomingEvents, setUpcomingEvents] = useState(() => dataCache.get('dashboard-events') || null);
  const [loading, setLoading] = useState(() => !dataCache.has('dashboard-stats'));
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchStats();
    fetchUpcomingEvents();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.stats);
      if (!response.ok) throw new Error('Failed to fetch statistics');
      const data = await response.json();
      dataCache.set('dashboard-stats', data);
      setStats(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchUpcomingEvents = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.upcomingEvents);
      if (!response.ok) throw new Error('Failed to fetch upcoming events');
      const data = await response.json();
      dataCache.set('dashboard-events', data.events);
      setUpcomingEvents(data.events);
    } catch (err) {
      setUpcomingEvents([]);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;
  if (!stats) return null;

  const calculateDurationStats = () => {
    const businessDaysDurations = stats.phase_duration.all_business_durations || [];
    const total = businessDaysDurations.length;

    if (total === 0) return null;

    const day15Count = businessDaysDurations.filter(d => d <= 15).length;
    const day20Count = businessDaysDurations.filter(d => d <= 20).length;
    const day30Count = businessDaysDurations.filter(d => d <= 30).length;

    return {
      day15: { count: day15Count, percentage: ((day15Count / total) * 100).toFixed(1) },
      day20: { count: day20Count, percentage: ((day20Count / total) * 100).toFixed(1) },
      day30: { count: day30Count, percentage: ((day30Count / total) * 100).toFixed(1) },
    };
  };

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
    },
  };

  return (
    <>
      <SEO
        title="Australian Merger Tracker | ACCC Merger Reviews & M&A Data"
        description="Real-time database of Australian mergers reviewed by the ACCC. Search merger decisions, track review timelines, analyze industry trends, and explore public consultation documents."
        url="/"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 mb-8">
        <StatCard
          title="Mergers"
          value={`${stats.by_status['Under assessment'] || 0} under assessment`}
          subtitle={`${stats.total_mergers} notified${stats.total_waivers ? ` and ${stats.total_waivers} waiver${stats.total_waivers !== 1 ? 's' : ''}` : ''}`}
          icon="🔍"
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
          icon="⏱️"
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
          icon="📈"
        />
      </div>

      {/* Recent Determinations */}
      {stats.recent_determinations && (
        <div className="mb-8">
          <RecentDeterminationsTable determinations={stats.recent_determinations} />
        </div>
      )}

      {/* Recently Notified Mergers */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-card mb-8 overflow-hidden">
        <div className="px-6 py-5 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">
            Recently notified mergers
          </h2>
        </div>
        <ul className="divide-y divide-gray-50">
          {stats.recent_mergers.map((merger) => (
            <li key={merger.merger_id}>
              <Link
                to={`/mergers/${merger.merger_id}`}
                className="block hover:bg-gray-100/70 transition-colors duration-150"
                aria-label={`View merger details for ${merger.merger_name}`}
              >
                <div className="px-6 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-2 min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-900 break-words hover:text-primary transition-colors">
                        {merger.merger_name}
                      </p>
                      {merger.is_waiver && (
                        <span
                          className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200/60"
                          role="status"
                          aria-label="Merger type: waiver application"
                        >
                          Waiver
                        </span>
                      )}
                    </div>
                    <div className="ml-2 flex-shrink-0">
                      <StatusBadge
                        status={merger.status}
                        determination={merger.accc_determination}
                      />
                    </div>
                  </div>
                  <div className="mt-1.5 text-xs text-gray-400">
                    {merger.is_waiver ? 'Applied:' : 'Notified:'}{' '}
                    {formatDate(merger.effective_notification_datetime)}
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </div>

      {/* Upcoming Events (within 7 days) */}
      {upcomingEvents && (() => {
        const eventsWithin7Days = upcomingEvents.filter(event => {
          if (isDatePast(event.date)) return false;
          const daysRemaining = getDaysRemaining(event.date);
          return daysRemaining !== null && daysRemaining <= 7;
        });
        return eventsWithin7Days.length > 0 ? (
          <div className="mb-8">
            <UpcomingEventsTable events={eventsWithin7Days} />
          </div>
        ) : null;
      })()}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Phase 1 Duration Table */}
        {(() => {
          const durationStats = calculateDurationStats();
          return durationStats && (
            <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-card flex flex-col">
              <h2 className="text-base font-semibold text-gray-900 mb-5">
                Phase 1 duration
              </h2>
              <div className="flex flex-col flex-1 justify-around">
                {[
                  { label: 'By day 15', data: durationStats.day15 },
                  { label: 'By day 20', data: durationStats.day20 },
                  { label: 'By day 30', data: durationStats.day30 },
                ].map(({ label, data }, index) => (
                  <div key={label} className={`grid grid-cols-[auto_1fr_auto] items-center gap-4 py-3 ${index < 2 ? 'border-b border-gray-50' : ''}`}>
                    <span className="text-sm text-gray-600">{label}</span>
                    <div className="bg-gray-100 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-primary h-1.5 rounded-full transition-all duration-500"
                        style={{ width: `${data.percentage}%` }}
                      />
                    </div>
                    <span className="text-sm font-semibold text-gray-900 tabular-nums text-right">
                      {data.percentage}%
                      <span className="text-gray-400 font-normal ml-1">({data.count})</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          );
        })()}

        {/* Phase 1 Determination Distribution */}
        {Object.keys(stats.by_determination).length > 0 && (
          <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-card">
            <h2 className="text-base font-semibold text-gray-900 mb-5">
              Phase 1 determinations
            </h2>
            <div className="h-64" role="img" aria-label={`Doughnut chart showing distribution of Phase 1 determinations: ${Object.entries(stats.by_determination).map(([det, count]) => `${count} ${det}`).join(', ')}`}>
              <Doughnut data={determinationData} options={chartOptions} />
            </div>
          </div>
        )}

        {/* Waiver Determination Distribution */}
        {stats.by_waiver_determination && Object.keys(stats.by_waiver_determination).length > 0 && (
          <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-card">
            <h2 className="text-base font-semibold text-gray-900 mb-5">
              Waiver determinations
            </h2>
            <div className="h-64" role="img" aria-label={`Doughnut chart showing distribution of waiver determinations: ${Object.entries(stats.by_waiver_determination).map(([det, count]) => `${count} ${det}`).join(', ')}`}>
              <Doughnut data={waiverDeterminationData} options={chartOptions} />
            </div>
          </div>
        )}
      </div>
    </div>
    </>
  );
}

export default Dashboard;
