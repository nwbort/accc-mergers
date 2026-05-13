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
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';

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

const COLORS = {
  primary: '#335145',
  primaryLight: 'rgba(51, 81, 69, 0.15)',
  accent: '#e07a5f',
  accentLight: 'rgba(224, 122, 95, 0.15)',
  teal: '#6b8f7f',
  tealLight: 'rgba(107, 143, 127, 0.15)',
  sage: '#8cafa0',
};

function formatMonthLabel(yyyymm) {
  const [year, month] = yyyymm.split('-');
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${months[parseInt(month, 10) - 1]} ${year}`;
}

function Analysis() {
  const { data, loading, error } = useFetchData(API_ENDPOINTS.analysis, {
    cacheKey: 'analysis-data',
  });
  const navigate = useNavigate();
  const [calendarDays, setCalendarDays] = useState(false);

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;
  if (!data) return null;

  const { phase1_duration, waiver_duration, monthly_volume } = data;
  const phase1Stats = calendarDays ? phase1_duration.calendar_stats : phase1_duration.stats;
  const waiverStats = calendarDays ? waiver_duration.calendar_stats : waiver_duration.stats;

  // --- Phase 1 Scatter Chart ---
  const phase1ScatterData = {
    datasets: [
      {
        label: 'Approved',
        data: phase1_duration.scatter_data
          .filter(d => d.determination === 'Approved')
          .map(d => ({
            x: new Date(d.notification_date).getTime(),
            y: d.business_days,
            label: d.merger_name,
            id: d.merger_id,
          })),
        backgroundColor: COLORS.primary,
        pointRadius: 6,
        pointHoverRadius: 9,
      },
      {
        label: 'Referred to phase 2',
        data: phase1_duration.scatter_data
          .filter(d => d.determination === 'Referred to phase 2')
          .map(d => ({
            x: new Date(d.notification_date).getTime(),
            y: d.business_days,
            label: d.merger_name,
            id: d.merger_id,
          })),
        backgroundColor: COLORS.accent,
        pointRadius: 8,
        pointHoverRadius: 10,
        pointStyle: 'triangle',
      },
    ],
  };

  const handleChartClick = (event, elements, chart) => {
    if (elements.length > 0) {
      const { datasetIndex, index } = elements[0];
      const point = chart.data.datasets[datasetIndex].data[index];
      if (point?.id) {
        navigate(`/mergers/${point.id}`);
      }
    }
  };

  const phase1ScatterOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    onClick: handleChartClick,
    onHover: (event, elements) => {
      event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
    },
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
          title: (items) => {
            if (!items.length) return '';
            const raw = items[0].raw;
            return raw.label;
          },
          label: (item) => {
            const date = new Date(item.raw.x);
            return [
              `Duration: ${item.raw.y} business days`,
              `Notified: ${date.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}`,
            ];
          },
        },
      },
    },
    scales: {
      x: {
        type: 'linear',
        ticks: {
          callback: function (value) {
            const date = new Date(value);
            const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            return `${months[date.getMonth()]} ${date.getFullYear()}`;
          },
          maxTicksLimit: 8,
          font: { size: 11 },
        },
        title: {
          display: true,
          text: 'Notification date',
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
        grid: { color: 'rgba(0,0,0,0.04)' },
      },
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Business days',
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
        grid: { color: 'rgba(0,0,0,0.04)' },
        ticks: { font: { size: 11 } },
      },
    },
  };

  // --- Waiver Scatter Chart ---
  const waiverScatterData = {
    datasets: [
      {
        label: 'Approved',
        data: waiver_duration.scatter_data
          .filter(d => d.determination === 'Approved')
          .map(d => ({
            x: new Date(d.application_date).getTime(),
            y: d.business_days,
            label: d.merger_name,
            id: d.merger_id,
          })),
        backgroundColor: COLORS.primary,
        pointRadius: 5,
        pointHoverRadius: 8,
      },
      {
        label: 'Not approved',
        data: waiver_duration.scatter_data
          .filter(d => d.determination === 'Not approved')
          .map(d => ({
            x: new Date(d.application_date).getTime(),
            y: d.business_days,
            label: d.merger_name,
            id: d.merger_id,
          })),
        backgroundColor: COLORS.accent,
        pointRadius: 8,
        pointHoverRadius: 10,
        pointStyle: 'triangle',
      },
    ],
  };

  const waiverScatterOptions = {
    ...phase1ScatterOptions,
    onClick: handleChartClick,
    onHover: (event, elements) => {
      event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
    },
    scales: {
      ...phase1ScatterOptions.scales,
      x: {
        ...phase1ScatterOptions.scales.x,
        title: {
          display: true,
          text: 'Application date',
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
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
            <div className="bg-white rounded-2xl border border-gray-100 shadow-card overflow-hidden">
              <div className="px-5 py-3 bg-primary">
                <p className="text-sm font-semibold text-white">Notifications phase 1</p>
              </div>
              <div className="grid grid-cols-2 divide-x divide-gray-100">
                <div className="p-5">
                  <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Avg duration</p>
                  <p className="text-2xl font-bold text-gray-900 mt-1.5 tracking-tight">
                    {phase1Stats.average ? `${phase1Stats.average} days` : 'N/A'}
                  </p>
                  {phase1Stats.count && (
                    <p className="text-sm text-gray-400 mt-0.5">{phase1Stats.count} completed</p>
                  )}
                </div>
                <div className="p-5">
                  <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Median duration</p>
                  <p className="text-2xl font-bold text-gray-900 mt-1.5 tracking-tight">
                    {phase1Stats.median ? `${phase1Stats.median} days` : 'N/A'}
                  </p>
                  {phase1Stats.min && phase1Stats.max && (
                    <p className="text-sm text-gray-400 mt-0.5">Range {phase1Stats.min}–{phase1Stats.max} days</p>
                  )}
                </div>
              </div>
            </div>

            {/* Waivers */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-card overflow-hidden">
              <div className="px-5 py-3 bg-primary">
                <p className="text-sm font-semibold text-white">Waivers</p>
              </div>
              <div className="grid grid-cols-2 divide-x divide-gray-100">
                <div className="p-5">
                  <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Avg duration</p>
                  <p className="text-2xl font-bold text-gray-900 mt-1.5 tracking-tight">
                    {waiverStats.average ? `${waiverStats.average} days` : 'N/A'}
                  </p>
                  {waiverStats.count && (
                    <p className="text-sm text-gray-400 mt-0.5">{waiverStats.count} completed</p>
                  )}
                </div>
                <div className="p-5">
                  <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Median duration</p>
                  <p className="text-2xl font-bold text-gray-900 mt-1.5 tracking-tight">
                    {waiverStats.median ? `${waiverStats.median} days` : 'N/A'}
                  </p>
                  {waiverStats.min && waiverStats.max && (
                    <p className="text-sm text-gray-400 mt-0.5">Range {waiverStats.min}–{waiverStats.max} days</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Monthly Volume */}
        <div className="grid grid-cols-1 gap-6 mb-8">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-card overflow-hidden">
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
              <p className="text-xs text-gray-400 mt-3">
                Waivers are recorded on the ACCC's register when they are decided. This means the number of waiver applications in a month can rise for up to 25 business days after the month ends.
              </p>
            </div>
          </div>
        </div>

        {/* Phase 1 Duration Analysis */}
        <section className="mb-8">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-card overflow-hidden">
            <div className="px-6 py-5 border-b border-gray-100">
              <h2 className="text-lg font-semibold text-gray-900">Phase 1 duration over time</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Each point represents a completed phase 1 assessment. Hover for details.
              </p>
            </div>
            <div className="p-6">
              <div className="h-80">
                <Scatter data={phase1ScatterData} options={phase1ScatterOptions} />
              </div>
            </div>
          </div>
        </section>

        {/* Waiver Duration Analysis */}
        <section className="mb-8">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-card overflow-hidden">
            <div className="px-6 py-5 border-b border-gray-100">
              <h2 className="text-lg font-semibold text-gray-900">Waiver duration over time</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Each point represents a completed waiver application. Hover for details.
              </p>
            </div>
            <div className="p-6">
              <div className="h-80">
                <Scatter data={waiverScatterData} options={waiverScatterOptions} />
              </div>
            </div>
          </div>
        </section>


      </div>
    </>
  );
}

export default Analysis;
