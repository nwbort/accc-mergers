import { Link } from 'react-router-dom';
import { FaArrowRightLong } from 'react-icons/fa6';
import { mergerPath } from '../../utils/slug';
import { formatDateMedium, getDaysRemaining, isDatePast } from '../../utils/dates';
import { useFetchData } from '../../hooks/useFetchData';
import { API_ENDPOINTS } from '../../config';
import LoadingSpinner from '../../components/LoadingSpinner';
import SEO from '../../components/SEO';
import ConceptSwitcher from './ConceptSwitcher';
import { relativeTime, clearanceRate } from './conceptHelpers';

// ── Concept 3 · "Clarity" ────────────────────────────────────────────────────
// A calm, typographic brief for the first-time visitor and the public reader.
// One narrow column, generous air, hairline rules. The data is the same, but it
// reads like the opening page of a report rather than a control panel: a single
// big sentence, a handful of large figures, then quiet lists.

function BigStat({ value, label, href }) {
  const inner = (
    <div className="py-6">
      <div className="text-4xl sm:text-5xl font-bold tracking-tight text-gray-900 tabular-nums">{value}</div>
      <div className="mt-1 text-sm text-gray-500">{label}</div>
    </div>
  );
  return href ? (
    <Link to={href} className="block group hover:bg-gray-50/60 rounded-xl transition-colors -mx-3 px-3">
      {inner}
    </Link>
  ) : inner;
}

function DashboardClarity() {
  const { data: stats, loading, error } = useFetchData(API_ENDPOINTS.stats, { cacheKey: 'dashboard-stats' });
  const { data: upcomingData } = useFetchData(API_ENDPOINTS.upcomingEvents, { cacheKey: 'dashboard-events' });

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;
  if (!stats) return null;

  const underAssessment = stats.by_status?.['Under assessment'] ?? 0;
  const rate = clearanceRate(stats);
  const medianBd = stats.phase_duration?.median_business_days;
  const recentDeterminations = (stats.recent_determinations ?? []).slice(0, 5);
  const topIndustries = (stats.top_industries ?? []).slice(0, 5);
  const maxIndustry = Math.max(...topIndustries.map((i) => i.count), 1);

  const events = (upcomingData?.events ?? [])
    .filter((e) => !isDatePast(e.date))
    .sort((a, b) => new Date(a.date) - new Date(b.date))
    .slice(0, 4);

  return (
    <>
      <SEO title="Dashboard concept · Clarity" description="Minimal editorial ACCC merger dashboard concept." url="/concepts/clarity" />
      <div className="max-w-3xl mx-auto px-5 sm:px-6 py-10 animate-fade-in">
        <ConceptSwitcher current="clarity" />

        {/* Hero sentence */}
        <header className="mt-8 mb-14">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-gray-400 mb-5">
            Australian merger review · {formatDateMedium(new Date().toISOString())}
          </p>
          <h1 className="text-3xl sm:text-[2.6rem] font-semibold leading-[1.15] tracking-tight text-gray-900">
            The ACCC is reviewing{' '}
            <span className="text-primary">{underAssessment} {underAssessment === 1 ? 'merger' : 'mergers'}</span>{' '}
            right now.
          </h1>
          <p className="mt-5 text-lg text-gray-500 leading-relaxed">
            Across {stats.total_mergers} notifications since the mandatory regime began,
            {rate != null ? ` ${rate}% have cleared at Phase 1` : ' most have cleared at Phase 1'}
            {medianBd ? `, with a median review of ${medianBd} business days.` : '.'}
          </p>
        </header>

        {/* Big stats row, hairline separated */}
        <section className="grid grid-cols-2 sm:grid-cols-3 divide-x divide-gray-100 border-y border-gray-100">
          <div className="px-3 first:pl-0"><BigStat value={underAssessment} label="Under assessment" href="/mergers?status=Under assessment" /></div>
          <div className="px-3"><BigStat value={rate != null ? `${rate}%` : '—'} label="Cleared at Phase 1" href="/analysis" /></div>
          <div className="px-3"><BigStat value={medianBd ?? '—'} label="Median Phase 1 (business days)" href="/analysis" /></div>
        </section>

        {/* Recent determinations */}
        <section className="mt-14">
          <div className="flex items-baseline justify-between mb-1">
            <h2 className="text-lg font-semibold text-gray-900">Latest determinations</h2>
            <Link to="/timeline" className="text-sm text-primary hover:text-primary-dark">View all</Link>
          </div>
          <ul className="mt-3">
            {recentDeterminations.map((d) => {
              const cleared = d.determination === 'Approved' || d.determination === 'Not opposed';
              return (
                <li key={`${d.merger_id}-${d.determination_date}`} className="border-b border-gray-100 last:border-0">
                  <Link to={mergerPath(d.merger_id, d.merger_name)} className="group flex items-center gap-4 py-4">
                    <span className={`h-2 w-2 shrink-0 rounded-full ${cleared ? 'bg-emerald-500' : d.determination === 'Referred to phase 2' ? 'bg-amber-500' : 'bg-purple-500'}`} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-[15px] text-gray-900 group-hover:text-primary transition-colors truncate">{d.merger_name}</span>
                      <span className="block text-xs text-gray-400">{d.determination} · {relativeTime(d.determination_date)}</span>
                    </span>
                    <FaArrowRightLong className="h-3.5 w-3.5 text-gray-300 group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>

        {/* Upcoming */}
        {events.length > 0 && (
          <section className="mt-14">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">Coming up</h2>
            <ul className="space-y-px">
              {events.map((e) => {
                const days = getDaysRemaining(e.date);
                return (
                  <li key={`${e.merger_id}-${e.date}`}>
                    <Link to={mergerPath(e.merger_id, e.merger_name)} className="group flex items-baseline gap-4 py-3 border-b border-gray-100 last:border-0">
                      <span className="w-20 shrink-0 text-sm font-medium text-gray-900 tabular-nums">
                        {days === 0 ? 'Today' : `${days} ${days === 1 ? 'day' : 'days'}`}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[15px] text-gray-700 group-hover:text-primary transition-colors truncate">{e.merger_name}</span>
                        <span className="block text-xs text-gray-400">{e.event_type_display}</span>
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        {/* Where the deals are */}
        {topIndustries.length > 0 && (
          <section className="mt-14">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Where the deals are</h2>
            <div className="space-y-3">
              {topIndustries.map((ind) => (
                <div key={ind.name} className="flex items-center gap-4">
                  <span className="w-44 shrink-0 text-sm text-gray-600 truncate">{ind.name}</span>
                  <span className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
                    <span className="block h-2 rounded-full bg-primary/70" style={{ width: `${(ind.count / maxIndustry) * 100}%` }} />
                  </span>
                  <span className="w-8 text-right text-sm font-semibold text-gray-900 tabular-nums">{ind.count}</span>
                </div>
              ))}
            </div>
            <Link to="/industries" className="mt-5 inline-flex items-center gap-1.5 text-sm text-primary hover:text-primary-dark">
              All industries <FaArrowRightLong className="h-3 w-3" />
            </Link>
          </section>
        )}
      </div>
    </>
  );
}

export default DashboardClarity;
