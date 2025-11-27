import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Bar, Doughnut } from 'react-chartjs-2';
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
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { formatDate } from '../utils/dates';

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
      console.error('Error fetching upcoming events:', err);
      // Don't block the page if upcoming events fail
      setUpcomingEvents([]);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600">Error: {error}</div>;
  if (!stats) return null;

  const durationData = {
    labels: stats.phase_duration.all_durations.map((_, i) => `Merger ${i + 1}`),
    datasets: [
      {
        label: 'Phase Duration (days)',
        data: stats.phase_duration.all_durations,
        backgroundColor: '#335145',
        borderColor: '#335145',
        borderWidth: 1,
      },
    ],
  };

  const statusData = {
    labels: Object.keys(stats.by_status),
    datasets: [
      {
        data: Object.values(stats.by_status),
        backgroundColor: ['#335145', '#4a6d5e', '#6b8f7f', '#8cafa0'],
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
        backgroundColor: ['#10b981', '#ef4444', '#6b7280'],
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
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Australian Merger Tracker</h1>
          <p className="mt-2 text-lg text-gray-600">Overview of ACCC merger reviews and key statistics</p>
        </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <StatCard
          title="Total mergers"
          value={stats.total_mergers}
          icon="📊"
        />
        <StatCard
          title="Average duration"
          value={
            stats.phase_duration.average_days
              ? `${Math.round(stats.phase_duration.average_days)} calendar days`
              : 'N/A'
          }
          subtitle={
            stats.phase_duration.average_business_days
              ? `${Math.round(stats.phase_duration.average_business_days)} business days`
              : null
          }
          icon="⏱️"
        />
        <StatCard
          title="Median duration"
          value={
            stats.phase_duration.median_days
              ? `${stats.phase_duration.median_days} calendar days`
              : 'N/A'
          }
          subtitle={
            stats.phase_duration.median_business_days
              ? `${stats.phase_duration.median_business_days} business days`
              : null
          }
          icon="📈"
        />
        <StatCard
          title="Under assessment"
          value={stats.by_status['Under assessment'] || 0}
          icon="🔍"
        />
      </div>

      {/* Upcoming Events */}
      {upcomingEvents && (
        <div className="mb-8">
          <UpcomingEventsTable events={upcomingEvents} />
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
        {/* Duration Chart */}
        {stats.phase_duration.all_durations.length > 0 && (
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Phase duration distribution
            </h2>
            <div className="h-64" role="img" aria-label={`Bar chart showing phase duration distribution across ${stats.phase_duration.all_durations.length} mergers. Average duration is ${Math.round(stats.phase_duration.average_days)} days.`}>
              <Bar data={durationData} options={chartOptions} />
            </div>
          </div>
        )}

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
              Determinations
            </h2>
            <div className="h-64" role="img" aria-label={`Doughnut chart showing distribution of determinations: ${Object.entries(stats.by_determination).map(([det, count]) => `${count} ${det}`).join(', ')}`}>
              <Doughnut data={determinationData} options={chartOptions} />
            </div>
          </div>
        )}

        {/* Top Industries */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Top industries
          </h2>
          <div className="space-y-3">
            {stats.top_industries.slice(0, 5).map((industry, index) => (
              <div key={index} className="flex items-center justify-between">
                <span className="text-sm text-gray-700 truncate flex-1">
                  {industry.name}
                </span>
                <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary text-white">
                  {industry.count}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Mergers */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            Recent mergers
          </h2>
        </div>
        <ul className="divide-y divide-gray-200">
          {stats.recent_mergers.map((merger) => (
            <li key={merger.merger_id}>
              <Link
                to={`/mergers/${merger.merger_id}`}
                className="block hover:bg-gray-50 transition-colors duration-150"
              >
                <div className="px-6 py-4">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-primary truncate">
                      {merger.merger_name}
                    </p>
                    <div className="ml-2 flex-shrink-0 flex">
                      <StatusBadge
                        status={merger.status}
                        determination={merger.accc_determination}
                      />
                    </div>
                  </div>
                  <div className="mt-2 flex items-center text-sm text-gray-500">
                    <span className="truncate">
                      Notified:{' '}
                      {formatDate(merger.effective_notification_datetime)}
                    </span>
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
    </>
  );
}

export default Dashboard;
