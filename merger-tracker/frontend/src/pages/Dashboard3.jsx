import { Link } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { formatDate, getDaysRemaining } from '../utils/dates';
import { useFetchData } from '../hooks/useFetchData';
import ConceptSwitcher from '../components/ConceptSwitcher';

// ────────────────────────────────────────────────────────────────────────────
// Concept 3 — "Bento"
// Modern minimal SaaS. Soft gradients, big rounded cards in a varied bento
// grid, oversized typography, playful but restrained. Inspired by Linear /
// Vercel / Apple landing pages.
// ────────────────────────────────────────────────────────────────────────────

function Bento3() {
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
  const day20 = stats.phase_duration.percentiles.day20.percentage;
  const topIndustries = stats.top_industries || [];
  const maxIndustry = topIndustries[0]?.count || 1;

  // Ring chart for "% cleared by day 20"
  const ringRadius = 64;
  const ringCircumference = 2 * Math.PI * ringRadius;
  const ringOffset = ringCircumference * (1 - day20 / 100);

  return (
    <>
      <SEO title="Bento — Concept 3" url="/dashboard-3" />
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-emerald-50/40">
        <ConceptSwitcher current={3} />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          {/* Hero strap */}
          <div className="mb-10 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
            <div>
              <p className="inline-flex items-center gap-2 text-xs font-medium text-emerald-700 bg-emerald-100/70 px-3 py-1 rounded-full mb-4">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Live · Updated hourly
              </p>
              <h1 className="text-5xl sm:text-6xl font-bold tracking-tight text-slate-900">
                Australian mergers,
                <br />
                <span className="bg-gradient-to-r from-emerald-600 via-primary to-emerald-700 bg-clip-text text-transparent">
                  at a glance.
                </span>
              </h1>
            </div>
            <p className="text-slate-500 max-w-sm text-sm leading-relaxed">
              Tracking every ACCC merger review since the new regime began.
              Pick a card to dive deeper.
            </p>
          </div>

          {/* Bento grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 auto-rows-[180px]">
            {/* Big — Under assessment */}
            <Link
              to="/mergers?status=Under assessment"
              className="sm:col-span-2 sm:row-span-2 group relative overflow-hidden rounded-3xl bg-gradient-to-br from-primary to-primary-dark text-white p-8 shadow-xl hover:shadow-2xl transition-all duration-300 hover:-translate-y-1"
            >
              <div className="absolute -top-20 -right-20 w-72 h-72 bg-emerald-400/20 rounded-full blur-3xl" />
              <div className="absolute -bottom-20 -left-20 w-72 h-72 bg-white/5 rounded-full blur-3xl" />
              <div className="relative h-full flex flex-col justify-between">
                <div>
                  <p className="text-xs uppercase tracking-widest text-emerald-200/80 mb-2">
                    Open matters
                  </p>
                  <p className="text-sm text-emerald-100/90 max-w-xs">
                    Currently under assessment at the Commission
                  </p>
                </div>
                <div>
                  <div className="flex items-baseline gap-3">
                    <span className="text-8xl font-bold tracking-tighter">
                      {underAssessment}
                    </span>
                    <span className="text-emerald-200/80 text-lg">active</span>
                  </div>
                  <p className="text-sm text-emerald-100/80 mt-3 flex items-center gap-1 group-hover:gap-2 transition-all">
                    See the list →
                  </p>
                </div>
              </div>
            </Link>

            {/* Ring — Day 20 */}
            <div className="sm:col-span-2 sm:row-span-2 group relative overflow-hidden rounded-3xl bg-white border border-slate-100 p-8 shadow-sm hover:shadow-md transition-all">
              <div className="flex items-start justify-between gap-6 h-full">
                <div className="flex flex-col justify-between h-full">
                  <div>
                    <p className="text-xs uppercase tracking-widest text-slate-500 mb-2">
                      Phase 1 speed
                    </p>
                    <h3 className="text-lg font-semibold text-slate-900">
                      Decisions within 20 business days
                    </h3>
                  </div>
                  <div>
                    <p className="text-sm text-slate-500 mb-1">Median</p>
                    <p className="text-2xl font-bold text-slate-900">
                      {stats.phase_duration.median_business_days} <span className="text-base font-normal text-slate-500">business days</span>
                    </p>
                    <Link to="/analysis" className="inline-flex items-center gap-1 text-sm text-primary font-medium mt-3 group-hover:gap-2 transition-all">
                      View analysis →
                    </Link>
                  </div>
                </div>
                <div className="relative w-44 h-44 shrink-0">
                  <svg viewBox="0 0 160 160" className="w-full h-full -rotate-90">
                    <circle cx="80" cy="80" r={ringRadius} fill="none" stroke="#e2e8f0" strokeWidth="12" />
                    <circle
                      cx="80"
                      cy="80"
                      r={ringRadius}
                      fill="none"
                      stroke="url(#bentoRing)"
                      strokeWidth="12"
                      strokeLinecap="round"
                      strokeDasharray={ringCircumference}
                      strokeDashoffset={ringOffset}
                      className="transition-all duration-700"
                    />
                    <defs>
                      <linearGradient id="bentoRing" x1="0" y1="0" x2="1" y2="1">
                        <stop offset="0%" stopColor="#10b981" />
                        <stop offset="100%" stopColor="#335145" />
                      </linearGradient>
                    </defs>
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-4xl font-bold text-slate-900 tabular-nums">{day20}%</span>
                    <span className="text-xs text-slate-500 mt-0.5">by day 20</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Cleared */}
            <Link
              to="/mergers"
              className="group relative overflow-hidden rounded-3xl bg-white border border-slate-100 p-6 shadow-sm hover:shadow-md transition-all hover:-translate-y-0.5"
            >
              <div className="flex flex-col h-full justify-between">
                <p className="text-xs uppercase tracking-widest text-slate-500">Cleared</p>
                <div>
                  <p className="text-5xl font-bold text-emerald-600 tabular-nums">{approved}</p>
                  <p className="text-xs text-slate-500 mt-1">Approved notifications</p>
                </div>
              </div>
            </Link>

            {/* Phase 2 */}
            <Link
              to="/mergers"
              className="group relative overflow-hidden rounded-3xl bg-gradient-to-br from-amber-50 to-amber-100/40 border border-amber-100 p-6 shadow-sm hover:shadow-md transition-all hover:-translate-y-0.5"
            >
              <div className="flex flex-col h-full justify-between">
                <p className="text-xs uppercase tracking-widest text-amber-700">Phase 2</p>
                <div>
                  <p className="text-5xl font-bold text-amber-700 tabular-nums">{phase2}</p>
                  <p className="text-xs text-amber-700/70 mt-1">Referred</p>
                </div>
              </div>
            </Link>

            {/* Lead determination */}
            {stats.recent_determinations?.[0] && (
              <Link
                to={`/mergers/${stats.recent_determinations[0].merger_id}`}
                className="sm:col-span-2 group relative overflow-hidden rounded-3xl bg-slate-900 text-white p-6 shadow-sm hover:shadow-xl transition-all"
              >
                <div className="absolute top-0 right-0 w-40 h-40 bg-emerald-500/20 rounded-full blur-2xl -translate-y-10 translate-x-10" />
                <div className="relative h-full flex flex-col justify-between">
                  <p className="text-xs uppercase tracking-widest text-emerald-300">
                    Latest determination
                  </p>
                  <div>
                    <h3 className="text-xl font-semibold leading-snug line-clamp-2 group-hover:text-emerald-300 transition-colors">
                      {stats.recent_determinations[0].merger_name}
                    </h3>
                    <div className="flex items-center gap-3 mt-3 text-xs text-slate-400">
                      <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-medium">
                        {stats.recent_determinations[0].determination}
                      </span>
                      <span>{formatDate(stats.recent_determinations[0].determination_date)}</span>
                    </div>
                  </div>
                </div>
              </Link>
            )}

            {/* Total notifications */}
            <div className="sm:col-span-2 group relative overflow-hidden rounded-3xl bg-white border border-slate-100 p-6 shadow-sm">
              <div className="flex items-center justify-between gap-6 h-full">
                <div>
                  <p className="text-xs uppercase tracking-widest text-slate-500 mb-2">
                    On the register
                  </p>
                  <div className="flex items-baseline gap-2">
                    <span className="text-5xl font-bold text-slate-900 tabular-nums">{stats.total_mergers}</span>
                    <span className="text-sm text-slate-500">notifications</span>
                  </div>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-2xl font-semibold text-slate-700 tabular-nums">{stats.total_waivers}</span>
                    <span className="text-sm text-slate-500">waivers</span>
                  </div>
                </div>
                {/* Mini bars */}
                <div className="flex items-end gap-1 h-20">
                  {[4, 6, 3, 8, 5, 9, 7, 11, 8, 12, 10, 14].map((v, i) => (
                    <div
                      key={i}
                      className="w-2 rounded-t bg-gradient-to-t from-emerald-200 to-primary"
                      style={{ height: `${(v / 14) * 100}%` }}
                    />
                  ))}
                </div>
              </div>
            </div>

            {/* Top industries — wide */}
            <Link
              to="/industries"
              className="sm:col-span-2 lg:col-span-2 sm:row-span-2 group relative overflow-hidden rounded-3xl bg-white border border-slate-100 p-6 shadow-sm hover:shadow-md transition-all"
            >
              <div className="h-full flex flex-col">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <p className="text-xs uppercase tracking-widest text-slate-500 mb-1">
                      By industry
                    </p>
                    <h3 className="text-lg font-semibold text-slate-900">Where the activity is</h3>
                  </div>
                  <span className="text-primary text-sm font-medium group-hover:translate-x-1 transition-transform">→</span>
                </div>
                <ul className="space-y-2 flex-1">
                  {topIndustries.slice(0, 6).map((ind) => (
                    <li key={ind.name}>
                      <div className="flex items-center gap-3">
                        <span className="text-sm text-slate-700 flex-1 truncate">{ind.name}</span>
                        <span className="text-sm font-semibold text-slate-900 tabular-nums">{ind.count}</span>
                      </div>
                      <div className="h-1 mt-1 rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-emerald-400 to-primary rounded-full"
                          style={{ width: `${(ind.count / maxIndustry) * 100}%` }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </Link>

            {/* Upcoming */}
            <Link
              to="/timeline"
              className="sm:col-span-2 sm:row-span-2 group relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 to-primary-dark text-white p-6 shadow-sm hover:shadow-xl transition-all"
            >
              <div className="absolute bottom-0 right-0 w-40 h-40 bg-emerald-400/20 rounded-full blur-2xl translate-y-10 translate-x-10" />
              <div className="relative h-full flex flex-col">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <p className="text-xs uppercase tracking-widest text-emerald-300 mb-1">
                      Coming up
                    </p>
                    <h3 className="text-lg font-semibold">Next 7 days</h3>
                  </div>
                </div>
                <ul className="space-y-3 flex-1">
                  {upcomingEvents.slice(0, 4).map((e, i) => {
                    const days = getDaysRemaining(e.date);
                    return (
                      <li key={i} className="flex items-start gap-3">
                        <div className="shrink-0 w-12 text-center bg-white/10 rounded-lg py-1.5">
                          <div className="text-xs text-emerald-300 leading-none">in</div>
                          <div className="text-lg font-bold leading-tight">{days}d</div>
                        </div>
                        <div className="text-sm leading-snug line-clamp-2 mt-1 text-slate-100">
                          {e.merger_name || e.title || e.label}
                        </div>
                      </li>
                    );
                  })}
                  {upcomingEvents.length === 0 && (
                    <li className="text-slate-300 text-sm italic">Nothing scheduled.</li>
                  )}
                </ul>
              </div>
            </Link>
          </div>

          {/* Recent matters strip */}
          <div className="mt-6 rounded-3xl bg-white border border-slate-100 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-5">
              <div>
                <p className="text-xs uppercase tracking-widest text-slate-500 mb-1">
                  Recently notified
                </p>
                <h3 className="text-lg font-semibold text-slate-900">Fresh on the register</h3>
              </div>
              <Link to="/mergers" className="text-sm text-primary font-medium hover:underline">
                See all →
              </Link>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {stats.recent_mergers.slice(0, 6).map((m) => (
                <Link
                  key={m.merger_id}
                  to={`/mergers/${m.merger_id}`}
                  className="group p-4 rounded-2xl bg-slate-50/70 hover:bg-emerald-50/60 border border-transparent hover:border-emerald-100 transition-all"
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <span className="text-xs font-medium text-slate-500">
                      {m.is_waiver ? 'Waiver' : 'Notification'}
                    </span>
                    <span className="text-[10px] text-slate-400 tabular-nums">
                      {formatDate(m.effective_notification_datetime)}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-slate-900 group-hover:text-primary line-clamp-2 leading-snug">
                    {m.merger_name}
                  </p>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

export default Bento3;
