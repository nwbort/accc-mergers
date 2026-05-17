import { Link } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { formatDate, getDaysRemaining } from '../utils/dates';
import { useFetchData } from '../hooks/useFetchData';
import ConceptSwitcher from '../components/ConceptSwitcher';

// ────────────────────────────────────────────────────────────────────────────
// Concept 2 — "Terminal"
// Data-desk / Bloomberg inspired. Dark, dense, monospace-leaning. Designed
// for analysts who want to scan numbers without scrolling. Live ticker top,
// multi-column dense layout, mini ASCII-style bars, tabular numerics.
// ────────────────────────────────────────────────────────────────────────────

function Bar({ value, max, color = 'bg-emerald-400' }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="flex-1 bg-zinc-800 h-1.5 overflow-hidden rounded-sm">
      <div className={`${color} h-full`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function Sparkline({ values, color = '#34d399' }) {
  if (!values || values.length === 0) return null;
  const max = Math.max(...values, 1);
  const w = 80;
  const h = 24;
  const step = w / (values.length - 1 || 1);
  const points = values
    .map((v, i) => `${i * step},${h - (v / max) * h}`)
    .join(' ');
  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

function Dashboard2() {
  const { data: stats, loading, error } = useFetchData(API_ENDPOINTS.stats, {
    cacheKey: 'dashboard-stats',
  });
  const { data: upcomingEventsData } = useFetchData(API_ENDPOINTS.upcomingEvents, {
    cacheKey: 'dashboard-events',
  });
  const upcomingEvents = upcomingEventsData?.events ?? [];

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;
  if (!stats) return null;

  const underAssessment = stats.by_status['Under assessment'] || 0;
  const approved = stats.by_determination['Approved'] || 0;
  const phase2 = stats.by_determination['Referred to phase 2'] || 0;
  const waiverApproved = stats.by_waiver_determination?.Approved || 0;
  const waiverDenied = stats.by_waiver_determination?.['Not approved'] || 0;

  const tickerItems = [
    ...(stats.recent_determinations || []).slice(0, 6).map((d) => ({
      tag: d.determination === 'Approved' ? 'CLR' : 'PH2',
      name: d.merger_name,
      delta: d.determination === 'Approved' ? '+APPROVED' : '+PHASE 2',
      up: d.determination === 'Approved',
      id: d.merger_id,
    })),
  ];

  const topIndustries = stats.top_industries || [];
  const maxIndustry = topIndustries[0]?.count || 1;

  // Fake sparkline data — for visual only; would be replaced with real trend
  const fakeSpark = [3, 5, 4, 7, 6, 9, 8, 11, 9, 12];

  const now = new Date();
  const timestamp = now.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';

  return (
    <>
      <SEO title="ACCC Terminal — Concept 2" url="/dashboard-2" />
      <div className="bg-zinc-950 min-h-screen text-zinc-200 font-mono">
        <ConceptSwitcher current={2} dark />

        {/* Top status bar */}
        <div className="border-b border-zinc-800 bg-zinc-900/60">
          <div className="max-w-[1400px] mx-auto px-4 py-2 flex items-center justify-between text-[11px] uppercase tracking-wider">
            <div className="flex items-center gap-6">
              <span className="text-emerald-400 font-bold">● LIVE</span>
              <span className="text-zinc-400">ACCC MERGER TERMINAL <span className="text-zinc-600">v1.0</span></span>
              <span className="text-zinc-500">{timestamp}</span>
            </div>
            <div className="hidden md:flex items-center gap-6 text-zinc-500">
              <span>SRC: accc.gov.au</span>
              <span>POLL: 60m</span>
              <span className="text-emerald-400">CONN OK</span>
            </div>
          </div>
        </div>

        {/* Ticker */}
        <div className="border-b border-zinc-800 bg-black overflow-hidden">
          <div className="flex gap-8 animate-marquee whitespace-nowrap py-2 text-xs">
            {[...tickerItems, ...tickerItems].map((t, i) => (
              <Link
                key={i}
                to={`/mergers/${t.id}`}
                className="flex items-center gap-2 hover:bg-zinc-900 px-2"
              >
                <span className={`px-1.5 py-0.5 text-[10px] font-bold rounded-sm ${t.up ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}`}>
                  {t.tag}
                </span>
                <span className="text-zinc-300">{t.name}</span>
                <span className={t.up ? 'text-emerald-400' : 'text-amber-400'}>
                  {t.up ? '▲' : '▼'} {t.delta}
                </span>
              </Link>
            ))}
          </div>
        </div>

        <div className="max-w-[1400px] mx-auto px-4 py-6">
          {/* KPI strip */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-px bg-zinc-800 mb-6 border border-zinc-800">
            {[
              { label: 'NOTIFIED', value: stats.total_mergers, delta: '+2', up: true, spark: fakeSpark },
              { label: 'WAIVERS', value: stats.total_waivers, delta: '+5', up: true, spark: fakeSpark },
              { label: 'ACTIVE', value: underAssessment, delta: '-1', up: false, spark: fakeSpark },
              { label: 'CLEARED', value: approved, delta: '+1', up: true, spark: fakeSpark },
              { label: 'PHASE 2', value: phase2, delta: '0', up: true, spark: fakeSpark },
              { label: 'MED P1 BD', value: stats.phase_duration.median_business_days, delta: '-0.5', up: true, spark: fakeSpark },
            ].map((k) => (
              <div key={k.label} className="bg-zinc-950 px-4 py-3">
                <div className="text-[10px] text-zinc-500 tracking-widest mb-1">{k.label}</div>
                <div className="flex items-end justify-between gap-2">
                  <div className="text-3xl font-bold text-zinc-100 tabular-nums leading-none">
                    {k.value}
                  </div>
                  <Sparkline values={k.spark} color={k.up ? '#34d399' : '#fbbf24'} />
                </div>
                <div className={`text-[10px] mt-1 ${k.up ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {k.up ? '▲' : '▼'} {k.delta}
                </div>
              </div>
            ))}
          </div>

          {/* Main grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* Recent determinations */}
            <section className="lg:col-span-7 border border-zinc-800 bg-zinc-900/40">
              <header className="px-4 py-2 border-b border-zinc-800 flex items-center justify-between">
                <h2 className="text-xs uppercase tracking-widest text-zinc-400">
                  &gt; recent_determinations
                </h2>
                <Link to="/mergers" className="text-[10px] uppercase tracking-widest text-emerald-400 hover:text-emerald-300">
                  view all →
                </Link>
              </header>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-[10px] uppercase tracking-widest text-zinc-500 border-b border-zinc-800">
                    <th className="text-left px-4 py-2">ID</th>
                    <th className="text-left px-4 py-2">MATTER</th>
                    <th className="text-left px-4 py-2">TYPE</th>
                    <th className="text-right px-4 py-2">DATE</th>
                    <th className="text-right px-4 py-2">RESULT</th>
                  </tr>
                </thead>
                <tbody>
                  {(stats.recent_determinations || []).slice(0, 10).map((d) => {
                    const up = d.determination === 'Approved';
                    return (
                      <tr key={d.merger_id} className="border-b border-zinc-900 hover:bg-zinc-900 group">
                        <td className="px-4 py-2 text-zinc-500 tabular-nums">{d.merger_id}</td>
                        <td className="px-4 py-2">
                          <Link to={`/mergers/${d.merger_id}`} className="text-zinc-200 group-hover:text-emerald-400 truncate block max-w-[300px]">
                            {d.merger_name}
                          </Link>
                        </td>
                        <td className="px-4 py-2 text-zinc-500">{d.is_waiver ? 'WVR' : 'NTF'}</td>
                        <td className="px-4 py-2 text-right text-zinc-500 tabular-nums">
                          {formatDate(d.determination_date)}
                        </td>
                        <td className={`px-4 py-2 text-right font-bold ${up ? 'text-emerald-400' : 'text-amber-400'}`}>
                          {up ? '▲' : '▼'} {d.determination?.toUpperCase()}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </section>

            {/* Right column */}
            <div className="lg:col-span-5 space-y-4">
              {/* Determination breakdown */}
              <section className="border border-zinc-800 bg-zinc-900/40 p-4">
                <h2 className="text-xs uppercase tracking-widest text-zinc-400 mb-3">
                  &gt; outcome_distribution
                </h2>
                <div className="space-y-2 text-xs">
                  {[
                    { label: 'Notification approved', value: approved, color: 'bg-emerald-400' },
                    { label: 'Phase 2 referral', value: phase2, color: 'bg-amber-400' },
                    { label: 'Waiver approved', value: waiverApproved, color: 'bg-emerald-500' },
                    { label: 'Waiver denied', value: waiverDenied, color: 'bg-rose-400' },
                  ].map((row) => (
                    <div key={row.label} className="flex items-center gap-3">
                      <span className="w-40 text-zinc-400 truncate">{row.label}</span>
                      <Bar value={row.value} max={Math.max(approved, waiverApproved)} color={row.color} />
                      <span className="w-10 text-right text-zinc-200 tabular-nums">{row.value}</span>
                    </div>
                  ))}
                </div>
              </section>

              {/* Phase 1 percentiles */}
              <section className="border border-zinc-800 bg-zinc-900/40 p-4">
                <h2 className="text-xs uppercase tracking-widest text-zinc-400 mb-3">
                  &gt; phase1_duration_pct
                </h2>
                <div className="space-y-2 text-xs">
                  {[
                    { label: 'By day 15', pct: stats.phase_duration.percentiles.day15.percentage, n: stats.phase_duration.percentiles.day15.count },
                    { label: 'By day 20', pct: stats.phase_duration.percentiles.day20.percentage, n: stats.phase_duration.percentiles.day20.count },
                    { label: 'By day 30', pct: stats.phase_duration.percentiles.day30.percentage, n: stats.phase_duration.percentiles.day30.count },
                  ].map((p) => (
                    <div key={p.label} className="flex items-center gap-3">
                      <span className="w-20 text-zinc-400">{p.label}</span>
                      <Bar value={p.pct} max={100} color="bg-emerald-400" />
                      <span className="w-16 text-right text-zinc-200 tabular-nums">
                        {p.pct}% <span className="text-zinc-500">({p.n})</span>
                      </span>
                    </div>
                  ))}
                </div>
                <div className="mt-3 pt-3 border-t border-zinc-800 grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <div className="text-[10px] text-zinc-500 tracking-widest">MEAN BD</div>
                    <div className="text-zinc-200 tabular-nums">{Math.round(stats.phase_duration.average_business_days)}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-zinc-500 tracking-widest">MEDIAN BD</div>
                    <div className="text-zinc-200 tabular-nums">{stats.phase_duration.median_business_days}</div>
                  </div>
                </div>
              </section>

              {/* Upcoming */}
              <section className="border border-zinc-800 bg-zinc-900/40 p-4">
                <h2 className="text-xs uppercase tracking-widest text-zinc-400 mb-3">
                  &gt; upcoming_events
                </h2>
                <ul className="space-y-1.5 text-xs">
                  {upcomingEvents.slice(0, 5).map((e, i) => {
                    const days = getDaysRemaining(e.date);
                    const urgent = days !== null && days <= 7;
                    return (
                      <li key={i} className="flex items-center gap-3">
                        <span className={`w-10 text-right tabular-nums ${urgent ? 'text-amber-400' : 'text-zinc-500'}`}>
                          T-{days}d
                        </span>
                        <span className="text-zinc-500">|</span>
                        <span className="text-zinc-300 truncate flex-1">
                          {e.merger_name || e.title || e.label}
                        </span>
                      </li>
                    );
                  })}
                  {upcomingEvents.length === 0 && (
                    <li className="text-zinc-600">// no upcoming events</li>
                  )}
                </ul>
              </section>
            </div>
          </div>

          {/* Industries heatmap-ish bar */}
          <section className="mt-4 border border-zinc-800 bg-zinc-900/40 p-4">
            <h2 className="text-xs uppercase tracking-widest text-zinc-400 mb-3">
              &gt; top_industries_by_volume
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-xs">
              {topIndustries.slice(0, 10).map((ind, i) => (
                <div key={ind.name} className="flex items-center gap-3 py-1">
                  <span className="w-6 text-right text-zinc-600 tabular-nums">{String(i + 1).padStart(2, '0')}</span>
                  <span className="text-zinc-300 truncate flex-1">{ind.name}</span>
                  <Bar value={ind.count} max={maxIndustry} color="bg-emerald-400" />
                  <span className="w-8 text-right text-zinc-200 tabular-nums">{ind.count}</span>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </>
  );
}

export default Dashboard2;
