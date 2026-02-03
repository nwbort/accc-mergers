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
import { formatDate, getDaysRemaining } from '../utils/dates';

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
  const [stats, setStats] = useState(null);
  const [upcomingEvents, setUpcomingEvents] = useState(null);
  const [loading, setLoading] = useState(true);
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
      setUpcomingEvents(data.events);
    } catch (err) {
      // Don't block the page if upcoming events fail
      setUpcomingEvents([]);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600">Error: {error}</div>;
  if (!stats) return null;

  // Calculate Phase 1 duration stats using business days
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

  const statusData = {
    labels: Object.keys(stats.by_status),
    datasets: [
      {
        data: Object.values(stats.by_status),
        backgroundColor: ['#335145', '#e07a5f', '#6b8f7f', '#8cafa0'],
        borderWidth: 2,
        borderColor: '#fff',
      },
    ],
  };

  const determinationData = {
    labels: Object.keys(stats.by_determination),
    datasets: [
      {
        data: Object.values(stats.by_determination),
        backgroundColor: ['#335145', '#e07a5f', '#6b8f7f', '#8cafa0'],
        borderWidth: 2,
        borderColor: '#fff',
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: {
        position: 'bottom',
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
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 mb-8">
        <StatCard
          title="Mergers"
          value={`${stats.by_status['Under assessment'] || 0} under assessment`}
          subtitle={`${stats.total_mergers} notified${stats.total_waivers ? `, ${stats.total_waivers} waiver${stats.total_waivers !== 1 ? 's' : ''}` : ''}`}
          icon="🔍"
        />
        <StatCard
          title="Average duration"
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
          title="Median duration"
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
      <div className="bg-white shadow rounded-lg mb-8">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            Recently notified mergers
          </h2>
        </div>
        <ul className="divide-y divide-gray-200">
          {stats.recent_mergers.map((merger) => (
            <li key={merger.merger_id}>
              <Link
                to={`/mergers/${merger.merger_id}`}
                className="block hover:bg-gray-50 transition-colors duration-150"
                aria-label={`View merger details for ${merger.merger_name}`}
              >
                <div className="px-6 py-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-start gap-2 min-w-0 flex-1">
                      <p className="text-sm font-medium text-primary break-words">
                        {merger.merger_name}
                      </p>
                      {merger.is_waiver && (
                        <span
                          className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800"
                          role="status"
                          aria-label="Merger type: waiver application"
                        >
                          Waiver
                        </span>
                      )}
                    </div>
                    <div className="ml-2 flex-shrink-0 flex">
                      <StatusBadge
                        status={merger.status}
                        determination={merger.accc_determination}
                      />
                    </div>
                  </div>
                  <div className="mt-2 flex items-center text-sm text-gray-500">
                    <span className="truncate">
                      {merger.is_waiver ? 'Applied:' : 'Notified:'}{' '}
                      {formatDate(merger.effective_notification_datetime)}
                    </span>
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
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Phase 1 Duration Table */}
        {(() => {
          const durationStats = calculateDurationStats();
          return durationStats && (
            <div className="bg-white p-6 rounded-lg shadow">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Phase 1 duration
              </h2>
              <div className="space-y-3">
                <div className="flex justify-between items-center py-2 border-b border-gray-200">
                  <span className="text-sm font-medium text-gray-700">Determined by day 15</span>
                  <span className="text-sm font-semibold text-gray-900">
                    {durationStats.day15.percentage}% ({durationStats.day15.count})
                  </span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-gray-200">
                  <span className="text-sm font-medium text-gray-700">Determined by day 20</span>
                  <span className="text-sm font-semibold text-gray-900">
                    {durationStats.day20.percentage}% ({durationStats.day20.count})
                  </span>
                </div>
                <div className="flex justify-between items-center py-2">
                  <span className="text-sm font-medium text-gray-700">Determined by day 30</span>
                  <span className="text-sm font-semibold text-gray-900">
                    {durationStats.day30.percentage}% ({durationStats.day30.count})
                  </span>
                </div>
              </div>
            </div>
          );
        })()}

        {/* Status Distribution */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Mergers by status
          </h2>
          <div className="h-64" role="img" aria-label={`Doughnut chart showing distribution of mergers by status: ${Object.entries(stats.by_status).map(([status, count]) => `${count} ${status}`).join(', ')}`}>
            <Doughnut data={statusData} options={chartOptions} />
          </div>
        </div>

        {/* Determination Distribution */}
        {Object.keys(stats.by_determination).length > 0 && (
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Phase 1 determinations
            </h2>
            <div className="h-64" role="img" aria-label={`Doughnut chart showing distribution of Phase 1 determinations: ${Object.entries(stats.by_determination).map(([det, count]) => `${count} ${det}`).join(', ')}`}>
              <Doughnut data={determinationData} options={chartOptions} />
            </div>
          </div>
        )}
      </div>
    </div>
    </>
  );
}

export default Dashboard;
