import { useState, useEffect } from 'react';
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

const approvalDateLinesPlugin = {
  id: 'approvalDateLines',
  beforeDatasetsDraw(chart) {
    const { ctx, scales: { x: xScale, y: yScale } } = chart;
    const yZero = yScale.getPixelForValue(0);
    const yMax = yScale.max;

    ctx.save();
    chart.data.datasets.forEach((dataset) => {
      dataset.data.forEach((point) => {
        if (!point.calendarDays) return;
        const msPerDay = 86400000;
        const approvalDateMs = point.x + point.calendarDays * msPerDay;

        const px = xScale.getPixelForValue(point.x);
        const py = yScale.getPixelForValue(point.y);
        const approvalPx = xScale.getPixelForValue(approvalDateMs);

        // Extend line upward: from point to top of chart at same slope
        const slope = (yZero - py) / (approvalPx - px); // pixels per pixel
        const topY = yScale.getPixelForValue(yMax);
        const topX = px - (py - topY) / slope;

        ctx.beginPath();
        ctx.moveTo(topX, topY);
        ctx.lineTo(approvalPx, yZero);
        ctx.strokeStyle = 'rgba(0, 0, 0, 0.06)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
      });
    });
    ctx.restore();
  },
};

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
  const navigate = useNavigate();

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

  const { phase1_duration, waiver_duration, monthly_volume } = data;

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
            calendarDays: d.calendar_days,
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
            calendarDays: d.calendar_days,
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
            calendarDays: d.calendar_days,
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
            calendarDays: d.calendar_days,
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
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 mb-8">
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
                <Scatter data={phase1ScatterData} options={phase1ScatterOptions} plugins={[approvalDateLinesPlugin]} />
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
                <Scatter data={waiverScatterData} options={waiverScatterOptions} plugins={[approvalDateLinesPlugin]} />
              </div>
            </div>
          </div>
        </section>

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
            </div>
          </div>
        </div>

      </div>
    </>
  );
}

export default Analysis;
