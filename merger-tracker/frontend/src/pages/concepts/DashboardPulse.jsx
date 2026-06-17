import { Link } from 'react-router-dom';
import {
  FaArrowTrendUp,
  FaCircleCheck,
  FaFileCirclePlus,
  FaTriangleExclamation,
  FaScaleBalanced,
  FaArrowRightLong,
} from 'react-icons/fa6';
import { mergerPath } from '../../utils/slug';
import { formatDateMedium, getDaysRemaining, isDatePast } from '../../utils/dates';
import { useFetchData } from '../../hooks/useFetchData';
import { API_ENDPOINTS } from '../../config';
import LoadingSpinner from '../../components/LoadingSpinner';
import SEO from '../../components/SEO';
import ConceptSwitcher from './ConceptSwitcher';
import {
  buildActivityFeed,
  relativeTime,
  recentActivitySummary,
  clearanceRate,
} from './conceptHelpers';

// ── Concept 1 · "Pulse" ──────────────────────────────────────────────────────
// A newsroom-style dashboard. Built for the engaged follower — the competition
// journalist, the associate doing a morning sweep, the policy watcher. The page
// answers one question first: "what just happened, and what's about to?"
//
//   • a live numbers ticker pinned to the top
//   • an editorial lede that summarises the week in one sentence
//   • a single merged activity stream (notifications + determinations)
//   • a focused "on the radar" rail of imminent deadlines

const FEED_STYLES = {
  notified:     { icon: FaFileCirclePlus,     rail: 'bg-blue-400',    chip: 'bg-blue-50 text-blue-700',       verb: 'Notified' },
  waiver_filed: { icon: FaScaleBalanced,      rail: 'bg-slate-400',   chip: 'bg-slate-100 text-slate-700',    verb: 'Waiver filed' },
  cleared:      { icon: FaCircleCheck,        rail: 'bg-emerald-400', chip: 'bg-emerald-50 text-emerald-700', verb: 'Cleared' },
  phase2:       { icon: FaTriangleExclamation,rail: 'bg-amber-400',   chip: 'bg-amber-50 text-amber-700',     verb: 'Referred to Phase 2' },
  decided:      { icon: FaScaleBalanced,      rail: 'bg-purple-400',  chip: 'bg-purple-50 text-purple-700',   verb: 'Decided' },
};

function TickerItem({ value, label }) {
  return (
    <span className="inline-flex items-baseline gap-2 whitespace-nowrap">
      <span className="text-base font-bold text-white tabular-nums">{value}</span>
      <span className="text-xs uppercase tracking-wider text-white/60">{label}</span>
    </span>
  );
}

function DashboardPulse() {
  const { data: stats, loading, error } = useFetchData(API_ENDPOINTS.stats, { cacheKey: 'dashboard-stats' });
  const { data: upcomingData } = useFetchData(API_ENDPOINTS.upcomingEvents, { cacheKey: 'dashboard-events' });

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;
  if (!stats) return null;

  const feed = buildActivityFeed(stats);
  const week = recentActivitySummary(stats, 7);
  const rate = clearanceRate(stats);
  const underAssessment = stats.by_status?.['Under assessment'] ?? 0;
  const medianBd = stats.phase_duration?.median_business_days;

  const events = (upcomingData?.events ?? [])
    .filter((e) => !isDatePast(e.date))
    .sort((a, b) => new Date(a.date) - new Date(b.date))
    .slice(0, 6);

  // One-sentence editorial lede assembled from the week's real activity.
  const ledeParts = [];
  if (week.notified) ledeParts.push(`${week.notified} new ${week.notified === 1 ? 'matter' : 'matters'} landed on the register`);
  if (week.cleared) ledeParts.push(`${week.cleared} cleared`);
  if (week.phase2) ledeParts.push(`${week.phase2} pushed to Phase 2`);
  const lede = ledeParts.length
    ? `${ledeParts.join(', ').replace(/, ([^,]*)$/, ' and $1')} this week.`
    : 'A quiet week on the register — no new determinations in the last seven days.';

  return (
    <>
      <SEO title="Dashboard concept · Pulse" description="Newsroom-style ACCC merger dashboard concept." url="/concepts/pulse" />

      {/* Numbers ticker */}
      <div className="gradient-hero">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-6 overflow-x-auto py-3 no-scrollbar">
            <span className="inline-flex items-center gap-2 shrink-0">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent-light opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-accent-light" />
              </span>
              <span className="text-xs font-bold uppercase tracking-widest text-white">Live</span>
            </span>
            <div className="h-4 w-px bg-white/20 shrink-0" />
            <TickerItem value={underAssessment} label="under assessment" />
            <TickerItem value={stats.total_mergers} label="notified" />
            <TickerItem value={stats.total_waivers} label="waivers" />
            {rate != null && <TickerItem value={`${rate}%`} label="cleared phase 1" />}
            {medianBd && <TickerItem value={`${medianBd}d`} label="median phase 1" />}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <ConceptSwitcher current="pulse" />

        {/* Editorial lede */}
        <header className="mb-8 max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-widest text-accent-dark mb-2">
            The week in mergers
          </p>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-gray-900 leading-tight">
            {lede}
          </h1>
          <p className="mt-3 text-gray-500">
            A running account of every matter the ACCC has touched, newest first.
          </p>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Activity stream */}
          <section className="lg:col-span-2">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold uppercase tracking-wider text-gray-500">Activity stream</h2>
              <Link to="/timeline" className="text-sm font-medium text-primary hover:text-primary-dark inline-flex items-center gap-1.5">
                Full timeline <FaArrowRightLong className="h-3 w-3" />
              </Link>
            </div>

            <ol className="relative">
              {feed.map((item, i) => {
                const s = FEED_STYLES[item.kind] ?? FEED_STYLES.decided;
                const Icon = s.icon;
                return (
                  <li key={`${item.id}-${item.date}-${i}`} className="relative pl-12 pb-5 group">
                    {/* connector line */}
                    {i < feed.length - 1 && (
                      <span className="absolute left-[18px] top-9 bottom-0 w-px bg-gray-200" aria-hidden="true" />
                    )}
                    <span className={`absolute left-0 top-1 flex h-9 w-9 items-center justify-center rounded-full text-white ${s.rail}`}>
                      <Icon className="h-4 w-4" />
                    </span>
                    <Link
                      to={mergerPath(item.id, item.name)}
                      className="block rounded-xl border border-gray-100 bg-white shadow-card hover:shadow-card-hover hover:border-gray-200 transition-all duration-200 px-4 py-3"
                    >
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-bold uppercase tracking-wide ${s.chip}`}>
                          {s.verb}
                        </span>
                        <span className="text-xs text-gray-400 tabular-nums">{relativeTime(item.date)}</span>
                        <span className="text-xs text-gray-300">·</span>
                        <span className="text-xs text-gray-400">{formatDateMedium(item.date)}</span>
                      </div>
                      <p className="mt-1.5 text-[15px] font-semibold text-gray-900 group-hover:text-primary transition-colors leading-snug">
                        {item.name}
                      </p>
                      <p className="text-xs text-gray-400 mt-0.5">{item.id}</p>
                    </Link>
                  </li>
                );
              })}
            </ol>
          </section>

          {/* On the radar rail */}
          <aside className="lg:col-span-1 space-y-6">
            <div className="rounded-2xl border border-gray-100 bg-white shadow-card overflow-hidden">
              <div className="px-5 py-4 bg-gradient-to-r from-primary to-primary-light">
                <h2 className="text-sm font-bold uppercase tracking-wider text-white flex items-center gap-2">
                  <FaArrowTrendUp className="h-3.5 w-3.5" /> On the radar
                </h2>
                <p className="text-xs text-white/70 mt-0.5">Next deadlines on the register</p>
              </div>
              <ul className="divide-y divide-gray-50">
                {events.length === 0 && (
                  <li className="px-5 py-6 text-sm text-gray-400">Nothing scheduled.</li>
                )}
                {events.map((e) => {
                  const days = getDaysRemaining(e.date);
                  const urgent = days != null && days <= 3;
                  return (
                    <li key={`${e.merger_id}-${e.date}`}>
                      <Link to={mergerPath(e.merger_id, e.merger_name)} className="block px-5 py-3.5 hover:bg-gray-50 transition-colors">
                        <div className="flex items-center gap-2">
                          <span className={`text-sm font-bold tabular-nums ${urgent ? 'text-red-600' : 'text-primary'}`}>
                            {days === 0 ? 'Today' : days === 1 ? '1 day' : `${days} days`}
                          </span>
                          <span className="text-[11px] text-gray-400">· {e.event_type_display}</span>
                        </div>
                        <p className="text-sm font-medium text-gray-900 mt-0.5 leading-snug">{e.merger_name}</p>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>

            {/* Scoreboard */}
            <div className="rounded-2xl border border-gray-100 bg-white shadow-card p-5">
              <h2 className="text-sm font-bold uppercase tracking-wider text-gray-500 mb-4">Clearance scoreboard</h2>
              <div className="space-y-4">
                <ScoreRow label="Cleared at Phase 1" value={stats.by_determination?.['Approved'] ?? 0} tone="emerald" />
                <ScoreRow label="Referred to Phase 2" value={stats.by_determination?.['Referred to phase 2'] ?? 0} tone="amber" />
                <ScoreRow label="Waivers approved" value={stats.by_waiver_determination?.['Approved'] ?? 0} tone="slate" />
              </div>
              <Link to="/analysis" className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:text-primary-dark">
                See the analysis <FaArrowRightLong className="h-3 w-3" />
              </Link>
            </div>
          </aside>
        </div>
      </div>
    </>
  );
}

function ScoreRow({ label, value, tone }) {
  const dot = { emerald: 'bg-emerald-500', amber: 'bg-amber-500', slate: 'bg-slate-400' }[tone];
  return (
    <div className="flex items-center justify-between">
      <span className="flex items-center gap-2 text-sm text-gray-600">
        <span className={`h-2 w-2 rounded-full ${dot}`} /> {label}
      </span>
      <span className="text-lg font-bold text-gray-900 tabular-nums">{value}</span>
    </div>
  );
}

export default DashboardPulse;
