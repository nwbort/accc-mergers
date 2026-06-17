import { Link } from 'react-router-dom';
import { Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  Tooltip,
  Legend,
  ArcElement,
} from 'chart.js';
import {
  FaBolt,
  FaGaugeHigh,
  FaLayerGroup,
  FaArrowRightLong,
  FaClock,
} from 'react-icons/fa6';
import { mergerPath } from '../../utils/slug';
import { formatDateMedium, getDaysRemaining, isDatePast } from '../../utils/dates';
import { useFetchData } from '../../hooks/useFetchData';
import { API_ENDPOINTS } from '../../config';
import LoadingSpinner from '../../components/LoadingSpinner';
import SEO from '../../components/SEO';
import ConceptSwitcher from './ConceptSwitcher';
import { clearanceRate } from './conceptHelpers';

ChartJS.register(Tooltip, Legend, ArcElement);

// ── Concept 2 · "Command Deck" ───────────────────────────────────────────────
// A dark, data-terminal dashboard for the deal-maker and competition analyst.
// The questions it answers: how fast does the ACCC clear deals, how likely is a
// clearance, and where does the pipeline sit right now? Big numerals, a
// clearance-velocity gauge, a phase pipeline funnel, and a determinations split.

function KpiTile({ icon: Icon, value, label, sub, accent = 'text-accent-light' }) {
  return (
    <div className="relative rounded-2xl bg-white/[0.04] border border-white/10 p-5 overflow-hidden">
      <div className="absolute -right-4 -top-4 text-white/[0.04] text-7xl">
        <Icon />
      </div>
      <div className="relative">
        <div className={`text-4xl font-bold tracking-tight tabular-nums ${accent}`}>{value}</div>
        <div className="mt-1 text-sm font-medium text-white">{label}</div>
        {sub && <div className="text-xs text-white/50 mt-0.5">{sub}</div>}
      </div>
    </div>
  );
}

// Horizontal "% cleared by day N" velocity bars.
function VelocityBar({ label, pct, count }) {
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1.5">
        <span className="text-white/70">{label}</span>
        <span className="font-bold text-white tabular-nums">
          {pct}% <span className="text-white/40 font-normal">({count})</span>
        </span>
      </div>
      <div className="h-2 rounded-full bg-white/10 overflow-hidden">
        <div
          className="h-2 rounded-full bg-gradient-to-r from-accent-dark to-accent-light transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function DashboardCommand() {
  const { data: stats, loading, error } = useFetchData(API_ENDPOINTS.stats, { cacheKey: 'dashboard-stats' });
  const { data: upcomingData } = useFetchData(API_ENDPOINTS.upcomingEvents, { cacheKey: 'dashboard-events' });

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;
  if (!stats) return null;

  const rate = clearanceRate(stats);
  const underAssessment = stats.by_status?.['Under assessment'] ?? 0;
  const completed = stats.by_status?.['Assessment completed'] ?? 0;
  const phase2 = stats.by_determination?.['Referred to phase 2'] ?? 0;
  const pct = stats.phase_duration?.percentiles ?? {};

  // Pipeline funnel stages from real status/determination counts.
  const maxStage = Math.max(stats.total_mergers, 1);
  const pipeline = [
    { label: 'Notified', value: stats.total_mergers, tone: 'from-sky-500 to-sky-400' },
    { label: 'Under assessment', value: underAssessment, tone: 'from-indigo-500 to-indigo-400' },
    { label: 'Completed', value: completed, tone: 'from-emerald-600 to-emerald-400' },
    { label: 'Referred to Phase 2', value: phase2, tone: 'from-amber-500 to-amber-400' },
  ];

  const events = (upcomingData?.events ?? [])
    .filter((e) => !isDatePast(e.date))
    .sort((a, b) => new Date(a.date) - new Date(b.date))
    .slice(0, 5);

  const detLabels = Object.keys(stats.by_determination ?? {});
  const doughnut = {
    labels: detLabels,
    datasets: [{
      data: detLabels.map((l) => stats.by_determination[l]),
      backgroundColor: ['#34d399', '#fbbf24', '#60a5fa', '#f472b6'],
      borderWidth: 0,
    }],
  };
  const doughnutOpts = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '70%',
    plugins: {
      legend: {
        position: 'bottom',
        labels: { color: '#cbd5e1', padding: 14, usePointStyle: true, pointStyle: 'circle', font: { size: 12, family: 'Inter, sans-serif' } },
      },
      tooltip: {
        callbacks: {
          label: (item) => {
            const total = item.dataset.data.reduce((s, v) => s + v, 0);
            const p = total ? Math.round((item.parsed / total) * 100) : 0;
            return ` ${item.parsed} (${p}%)`;
          },
        },
      },
    },
  };

  return (
    <>
      <SEO title="Dashboard concept · Command Deck" description="Analyst command-deck ACCC merger dashboard concept." url="/concepts/command" />
      <div className="bg-primary-dark min-h-screen -mt-16 pt-16">
        <div className="gradient-hero">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 pb-10">
            <ConceptSwitcher current="command" dark />
            <div className="mt-6 flex items-center gap-2">
              <FaBolt className="text-accent-light h-4 w-4" />
              <span className="text-xs font-bold uppercase tracking-widest text-accent-light">Command deck</span>
            </div>
            <h1 className="mt-2 text-3xl sm:text-4xl font-bold tracking-tight text-white">
              The state of merger review, at a glance
            </h1>
            <p className="mt-2 text-white/60 max-w-2xl">
              Live clearance velocity, pipeline and outcomes under Australia's mandatory merger regime.
            </p>

            {/* KPI band */}
            <div className="mt-8 grid grid-cols-2 lg:grid-cols-4 gap-4">
              <KpiTile icon={FaLayerGroup} value={underAssessment} label="Under assessment" sub={`${stats.total_mergers} notified all-time`} />
              <KpiTile icon={FaGaugeHigh} value={rate != null ? `${rate}%` : '—'} label="Cleared at Phase 1" sub={`${phase2} referred to Phase 2`} />
              <KpiTile icon={FaClock} value={stats.phase_duration?.median_business_days ?? '—'} label="Median Phase 1 days" sub={`${Math.round(stats.phase_duration?.average_business_days ?? 0)} avg · business days`} accent="text-white" />
              <KpiTile icon={FaBolt} value={stats.total_waivers} label="Waiver applications" sub={`${stats.by_waiver_determination?.['Approved'] ?? 0} approved`} accent="text-white" />
            </div>
          </div>
        </div>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Clearance velocity */}
          <div className="rounded-2xl bg-white/[0.04] border border-white/10 p-6">
            <h2 className="text-sm font-bold uppercase tracking-wider text-white/70 mb-1">Clearance velocity</h2>
            <p className="text-xs text-white/40 mb-5">Share of Phase 1 reviews completed by day…</p>
            <div className="space-y-5">
              {pct.day15 && <VelocityBar label="By day 15" pct={pct.day15.percentage} count={pct.day15.count} />}
              {pct.day20 && <VelocityBar label="By day 20" pct={pct.day20.percentage} count={pct.day20.count} />}
              {pct.day30 && <VelocityBar label="By day 30" pct={pct.day30.percentage} count={pct.day30.count} />}
            </div>
          </div>

          {/* Pipeline funnel */}
          <div className="rounded-2xl bg-white/[0.04] border border-white/10 p-6">
            <h2 className="text-sm font-bold uppercase tracking-wider text-white/70 mb-5">Pipeline</h2>
            <div className="space-y-4">
              {pipeline.map((stage) => (
                <div key={stage.label}>
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span className="text-white/70">{stage.label}</span>
                    <span className="font-bold text-white tabular-nums">{stage.value}</span>
                  </div>
                  <div className="h-6 rounded-lg bg-white/[0.06] overflow-hidden">
                    <div
                      className={`h-6 rounded-lg bg-gradient-to-r ${stage.tone} transition-all duration-700`}
                      style={{ width: `${Math.max((stage.value / maxStage) * 100, 3)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Determination split */}
          <div className="rounded-2xl bg-white/[0.04] border border-white/10 p-6">
            <h2 className="text-sm font-bold uppercase tracking-wider text-white/70 mb-5">Phase 1 outcomes</h2>
            <div className="h-56">
              <Doughnut data={doughnut} options={doughnutOpts} />
            </div>
          </div>

          {/* Upcoming deadlines — full width */}
          <div className="lg:col-span-3 rounded-2xl bg-white/[0.04] border border-white/10 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
              <h2 className="text-sm font-bold uppercase tracking-wider text-white/70">Imminent deadlines</h2>
              <Link to="/timeline" className="text-sm font-medium text-accent-light hover:text-accent inline-flex items-center gap-1.5">
                Timeline <FaArrowRightLong className="h-3 w-3" />
              </Link>
            </div>
            <ul className="divide-y divide-white/5">
              {events.length === 0 && <li className="px-6 py-6 text-sm text-white/40">Nothing scheduled.</li>}
              {events.map((e) => {
                const days = getDaysRemaining(e.date);
                const urgent = days != null && days <= 3;
                return (
                  <li key={`${e.merger_id}-${e.date}`}>
                    <Link to={mergerPath(e.merger_id, e.merger_name)} className="flex items-center gap-4 px-6 py-4 hover:bg-white/[0.03] transition-colors">
                      <div className={`flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-xl ${urgent ? 'bg-red-500/20 text-red-300' : 'bg-white/[0.06] text-accent-light'}`}>
                        <span className="text-base font-bold leading-none tabular-nums">{days}</span>
                        <span className="text-[9px] uppercase tracking-wide">days</span>
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-white truncate">{e.merger_name}</p>
                        <p className="text-xs text-white/50">{e.event_type_display} · {formatDateMedium(e.date)}</p>
                      </div>
                      <span className="hidden sm:block text-xs text-white/40">{e.merger_id}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      </div>
    </>
  );
}

export default DashboardCommand;
