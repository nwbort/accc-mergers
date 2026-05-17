import { Link } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { formatDate } from '../utils/dates';
import { useFetchData } from '../hooks/useFetchData';
import ConceptSwitcher from '../components/ConceptSwitcher';

// ────────────────────────────────────────────────────────────────────────────
// Concept 1 — "The Merger Desk"
// Editorial / newsroom inspired. Big serif headline, lead story, sidebar of
// indicators, and a wire-service feed of recent activity. Designed to feel
// like opening a morning briefing rather than a dashboard.
// ────────────────────────────────────────────────────────────────────────────

function Dashboard1() {
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

  const today = new Date().toLocaleDateString('en-AU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  const lead = stats.recent_determinations?.[0];
  const secondary = (stats.recent_determinations || []).slice(1, 4);
  const underAssessment = stats.by_status['Under assessment'] || 0;
  const approved = stats.by_determination['Approved'] || 0;
  const phase2 = stats.by_determination['Referred to phase 2'] || 0;

  return (
    <>
      <SEO title="The Merger Desk — Concept 1" url="/dashboard-1" />
      <div className="bg-[#faf7f2] min-h-screen">
        <ConceptSwitcher current={1} />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          {/* Masthead */}
          <header className="border-b-4 border-double border-gray-900 pb-6 mb-10">
            <div className="flex items-baseline justify-between flex-wrap gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-gray-500 mb-2">
                  Vol. 1 · The Merger Desk · Australia
                </p>
                <h1 className="font-serif text-5xl sm:text-6xl font-bold text-gray-900 tracking-tight leading-none">
                  Today's Briefing
                </h1>
              </div>
              <div className="text-right">
                <p className="font-serif italic text-gray-600">{today}</p>
                <p className="text-xs uppercase tracking-widest text-gray-500 mt-1">
                  {stats.total_mergers + stats.total_waivers} matters on file
                </p>
              </div>
            </div>
          </header>

          {/* Lead story + sidebar */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 mb-12">
            {/* Lead */}
            <article className="lg:col-span-8 lg:border-r lg:border-gray-300 lg:pr-10">
              <p className="text-xs uppercase tracking-[0.25em] text-amber-700 font-semibold mb-3">
                Lead determination
              </p>
              {lead && (
                <Link to={`/mergers/${lead.merger_id}`} className="group block">
                  <h2 className="font-serif text-4xl sm:text-5xl font-bold text-gray-900 leading-tight mb-4 group-hover:text-primary transition-colors">
                    {lead.merger_name}
                  </h2>
                  <p className="font-serif text-lg text-gray-700 leading-relaxed mb-6 first-letter:font-bold first-letter:text-5xl first-letter:float-left first-letter:mr-2 first-letter:mt-1 first-letter:font-serif first-letter:leading-none">
                    The ACCC issued its {lead.determination_type || 'final'} determination on{' '}
                    {formatDate(lead.determination_date)}, marking the matter as{' '}
                    <em className="font-semibold not-italic text-primary">
                      {lead.determination?.toLowerCase()}
                    </em>
                    {lead.is_waiver ? ' under the merger waiver pathway' : ' under formal notification'}.
                    The matter sits within the broader cohort of {underAssessment} active
                    reviews currently before the Commission.
                  </p>
                  <p className="text-sm uppercase tracking-widest text-gray-500 group-hover:text-primary">
                    Continue reading →
                  </p>
                </Link>
              )}

              {/* Secondary stories */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-10 pt-8 border-t border-gray-300">
                {secondary.map((d) => (
                  <Link
                    key={d.merger_id}
                    to={`/mergers/${d.merger_id}`}
                    className="group"
                  >
                    <p className="text-[10px] uppercase tracking-[0.2em] text-amber-700 font-semibold mb-2">
                      {d.is_waiver ? 'Waiver' : 'Notification'} · {d.determination}
                    </p>
                    <h3 className="font-serif text-lg font-bold text-gray-900 leading-snug group-hover:text-primary transition-colors mb-2">
                      {d.merger_name}
                    </h3>
                    <p className="text-xs text-gray-500 font-serif italic">
                      {formatDate(d.determination_date)}
                    </p>
                  </Link>
                ))}
              </div>
            </article>

            {/* Sidebar */}
            <aside className="lg:col-span-4 space-y-8">
              <div>
                <h3 className="font-serif text-2xl font-bold text-gray-900 border-b-2 border-gray-900 pb-2 mb-4">
                  By the numbers
                </h3>
                <dl className="space-y-4">
                  <div className="flex items-baseline justify-between border-b border-gray-200 pb-3">
                    <dt className="font-serif text-gray-700">Under assessment</dt>
                    <dd className="font-serif text-3xl font-bold text-primary">{underAssessment}</dd>
                  </div>
                  <div className="flex items-baseline justify-between border-b border-gray-200 pb-3">
                    <dt className="font-serif text-gray-700">Cleared</dt>
                    <dd className="font-serif text-3xl font-bold text-gray-900">{approved}</dd>
                  </div>
                  <div className="flex items-baseline justify-between border-b border-gray-200 pb-3">
                    <dt className="font-serif text-gray-700">Phase 2 referrals</dt>
                    <dd className="font-serif text-3xl font-bold text-amber-700">{phase2}</dd>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <dt className="font-serif text-gray-700">Median phase 1</dt>
                    <dd className="font-serif text-3xl font-bold text-gray-900">
                      {stats.phase_duration.median_business_days}
                      <span className="text-sm font-normal text-gray-500 ml-1">days</span>
                    </dd>
                  </div>
                </dl>
              </div>

              {/* Pull quote */}
              <blockquote className="border-l-4 border-amber-700 pl-5 py-2">
                <p className="font-serif italic text-xl text-gray-800 leading-snug">
                  "{Math.round(stats.phase_duration.percentiles.day20.percentage)}% of phase 1
                  reviews conclude within 20 business days."
                </p>
                <footer className="mt-2 text-xs uppercase tracking-widest text-gray-500">
                  — From the analysis desk
                </footer>
              </blockquote>

              {/* Upcoming */}
              {upcomingEvents.length > 0 && (
                <div>
                  <h3 className="font-serif text-2xl font-bold text-gray-900 border-b-2 border-gray-900 pb-2 mb-4">
                    Diary
                  </h3>
                  <ul className="space-y-3">
                    {upcomingEvents.slice(0, 4).map((e, i) => (
                      <li key={i} className="flex gap-4 font-serif">
                        <time className="text-xs uppercase tracking-wider text-amber-700 font-semibold w-16 shrink-0 pt-1">
                          {formatDate(e.date)}
                        </time>
                        <div className="text-sm text-gray-700 leading-snug">
                          {e.merger_name || e.title || e.label}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </aside>
          </div>

          {/* Wire feed */}
          <section className="border-t-4 border-double border-gray-900 pt-8">
            <div className="flex items-baseline justify-between mb-6">
              <h2 className="font-serif text-3xl font-bold text-gray-900">From the wire</h2>
              <Link to="/mergers" className="text-sm uppercase tracking-widest text-amber-700 hover:text-amber-900 font-semibold">
                Full register →
              </Link>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-10">
              {stats.recent_mergers.slice(0, 10).map((m, i) => (
                <Link
                  key={m.merger_id}
                  to={`/mergers/${m.merger_id}`}
                  className={`group block py-4 ${i < 8 ? 'border-b border-gray-200' : ''}`}
                >
                  <div className="flex items-start gap-4">
                    <span className="font-serif italic text-amber-700 text-sm shrink-0 w-20 pt-0.5">
                      {formatDate(m.effective_notification_datetime)}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="font-serif text-base text-gray-900 group-hover:text-primary transition-colors leading-snug">
                        {m.merger_name}
                      </p>
                      <p className="text-[10px] uppercase tracking-widest text-gray-500 mt-1">
                        {m.is_waiver ? 'Waiver' : 'Notification'} · {m.status}
                      </p>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </section>

          <footer className="mt-16 pt-6 border-t border-gray-300 text-center">
            <p className="font-serif italic text-sm text-gray-500">
              Compiled from the ACCC public register. The Merger Desk is published continuously.
            </p>
          </footer>
        </div>
      </div>
    </>
  );
}

export default Dashboard1;
