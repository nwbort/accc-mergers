import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
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
import { dataCache } from '../utils/dataCache';

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
  const [data, setData] = useState(() => dataCache.get('analysis-data') || null);
  const [loading, setLoading] = useState(() => !dataCache.has('analysis-data'));
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.analysis);
      if (!response.ok) throw new Error('Failed to fetch analysis data');
      const result = await response.json();
      dataCache.set('analysis-data', result);
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;
  if (!data) return null;

  const { phase1_duration, waiver_duration, determination_period_usage, monthly_volume, consultation_gap } = data;

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

  const phase1ScatterOptions = {
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
        pointRadius: 6,
        pointHoverRadius: 9,
        pointStyle: 'crossRot',
      },
    ],
  };

  const waiverScatterOptions = {
    ...phase1ScatterOptions,
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

  // --- Phase 1 Duration Distribution ---
  const distributionLabels = Object.keys(phase1_duration.distribution);
  const distributionData = {
    labels: distributionLabels,
    datasets: [
      {
        label: 'Number of mergers',
        data: Object.values(phase1_duration.distribution),
        backgroundColor: COLORS.primary,
        borderRadius: 6,
        maxBarThickness: 60,
      },
    ],
  };

  const distributionOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title: (items) => `${items[0].label} business days`,
          label: (item) => `${item.raw} merger${item.raw !== 1 ? 's' : ''}`,
        },
      },
    },
    scales: {
      x: {
        title: {
          display: true,
          text: 'Business days',
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
        grid: { display: false },
        ticks: { font: { size: 11 } },
      },
      y: {
        beginAtZero: true,
        ticks: { stepSize: 1, font: { size: 11 } },
        grid: { color: 'rgba(0,0,0,0.04)' },
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

  // --- Determination Period Usage (horizontal bar) ---
  const sortedUsage = [...determination_period_usage.data].sort((a, b) => a.percentage_used - b.percentage_used);
  const usageLabels = sortedUsage.map(d => {
    const name = d.merger_name;
    return name.length > 35 ? name.slice(0, 32) + '...' : name;
  });

  const usageData = {
    labels: usageLabels,
    datasets: [
      {
        label: 'Period used',
        data: sortedUsage.map(d => d.days_used),
        backgroundColor: sortedUsage.map(d =>
          d.percentage_used >= 90 ? COLORS.accent : COLORS.primary
        ),
        borderRadius: 4,
      },
      {
        label: 'Days remaining',
        data: sortedUsage.map(d => d.days_before_deadline),
        backgroundColor: 'rgba(0,0,0,0.05)',
        borderRadius: 4,
      },
    ],
  };

  const usageOptions = {
    indexAxis: 'y',
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
          title: (items) => sortedUsage[items[0].dataIndex].merger_name,
          afterTitle: (items) => sortedUsage[items[0].dataIndex].merger_id,
          label: (item) => {
            const d = sortedUsage[item.dataIndex];
            if (item.datasetIndex === 0) {
              return `Used: ${d.days_used} of ${d.total_period_days} business days (${d.percentage_used}%)`;
            }
            return `Remaining: ${d.days_before_deadline} business days`;
          },
        },
      },
    },
    scales: {
      x: {
        stacked: true,
        title: {
          display: true,
          text: 'Business days',
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
        grid: { color: 'rgba(0,0,0,0.04)' },
        ticks: { font: { size: 11 } },
      },
      y: {
        stacked: true,
        grid: { display: false },
        ticks: { font: { size: 11 } },
      },
    },
  };

  return (
    <>
      <SEO
        title="Analysis"
        description="Statistical analysis of Australian merger reviews including phase 1 durations, waiver processing times, and ACCC determination trends."
        url="/analysis"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Analysis</h1>
          <p className="text-sm text-gray-500 mt-1">
            Statistical analysis of ACCC merger review durations and trends. All durations are in business days (excluding weekends, ACT public holidays, and the 23 Dec &ndash; 10 Jan period).
          </p>
        </div>

        {/* Summary Stat Cards */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
          {[
            {
              label: 'Avg phase 1 duration',
              value: phase1_duration.stats.average ? `${phase1_duration.stats.average} days` : 'N/A',
              detail: phase1_duration.stats.count ? `${phase1_duration.stats.count} completed` : null,
            },
            {
              label: 'Median phase 1 duration',
              value: phase1_duration.stats.median ? `${phase1_duration.stats.median} days` : 'N/A',
              detail: phase1_duration.stats.min && phase1_duration.stats.max
                ? `Range: ${phase1_duration.stats.min}–${phase1_duration.stats.max}`
                : null,
            },
            {
              label: 'Avg waiver duration',
              value: waiver_duration.stats.average ? `${waiver_duration.stats.average} days` : 'N/A',
              detail: waiver_duration.stats.count ? `${waiver_duration.stats.count} completed` : null,
            },
            {
              label: 'Avg determination period used',
              value: determination_period_usage.stats.average_percentage_used
                ? `${determination_period_usage.stats.average_percentage_used}%`
                : 'N/A',
              detail: determination_period_usage.stats.average_days_early
                ? `~${determination_period_usage.stats.average_days_early} days early`
                : null,
            },
          ].map(({ label, value, detail }) => (
            <div key={label} className="bg-white p-5 rounded-2xl border border-gray-100 shadow-card">
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">{label}</p>
              <p className="text-2xl font-bold text-gray-900 mt-1.5 tracking-tight">{value}</p>
              {detail && <p className="text-sm text-gray-400 mt-0.5">{detail}</p>}
            </div>
          ))}
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

        {/* Phase 1 Distribution + Consultation Gap side by side */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-card overflow-hidden">
            <div className="px-6 py-5 border-b border-gray-100">
              <h2 className="text-base font-semibold text-gray-900">Phase 1 duration distribution</h2>
            </div>
            <div className="p-6">
              <div className="h-64">
                <Bar data={distributionData} options={distributionOptions} />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-gray-100 shadow-card overflow-hidden">
            <div className="px-6 py-5 border-b border-gray-100">
              <h2 className="text-base font-semibold text-gray-900">Consultation close to determination</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Business days from consultation response due date to determination
              </p>
            </div>
            <div className="p-6">
              <div className="space-y-3">
                {consultation_gap.data
                  .sort((a, b) => a.business_days - b.business_days)
                  .map((d) => (
                    <div key={d.merger_id} className="flex items-center gap-3">
                      <Link
                        to={`/mergers/${d.merger_id}`}
                        className="text-xs text-gray-600 hover:text-primary transition-colors w-40 truncate flex-shrink-0"
                        title={d.merger_name}
                      >
                        {d.merger_name}
                      </Link>
                      <div className="flex-1 bg-gray-100 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="h-1.5 rounded-full transition-all duration-300"
                          style={{
                            width: `${Math.min((d.business_days / (consultation_gap.stats.average * 2)) * 100, 100)}%`,
                            backgroundColor: d.business_days > consultation_gap.stats.average * 1.5
                              ? COLORS.accent
                              : COLORS.primary,
                          }}
                        />
                      </div>
                      <span className="text-xs font-semibold text-gray-700 tabular-nums w-12 text-right">
                        {d.business_days}d
                      </span>
                    </div>
                  ))}
              </div>
              <div className="mt-4 pt-3 border-t border-gray-100 flex gap-6 text-xs text-gray-500">
                <span>Average: <strong className="text-gray-700">{consultation_gap.stats.average} days</strong></span>
                <span>Median: <strong className="text-gray-700">{consultation_gap.stats.median} days</strong></span>
              </div>
            </div>
          </div>
        </div>

        {/* Waiver Duration Analysis */}
        <section className="mb-8">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-card overflow-hidden">
            <div className="px-6 py-5 border-b border-gray-100">
              <h2 className="text-lg font-semibold text-gray-900">Waiver duration over time</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Each point represents a completed waiver application. Average: {waiver_duration.stats.average} business days, median: {waiver_duration.stats.median} business days.
              </p>
            </div>
            <div className="p-6">
              <div className="h-80">
                <Scatter data={waiverScatterData} options={waiverScatterOptions} />
              </div>
            </div>
          </div>
        </section>

        {/* Monthly Volume + Determination Period Usage */}
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
            </div>
          </div>
        </div>

        {/* Determination Period Usage */}
        <section className="mb-8">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-card overflow-hidden">
            <div className="px-6 py-5 border-b border-gray-100">
              <h2 className="text-lg font-semibold text-gray-900">Determination period usage</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                How much of the statutory determination period (30 business days) each merger used before a decision was made. Mergers highlighted in red used over 90% of the period.
              </p>
            </div>
            <div className="p-6">
              <div style={{ height: `${Math.max(sortedUsage.length * 36, 200)}px` }}>
                <Bar data={usageData} options={usageOptions} />
              </div>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}

export default Analysis;
