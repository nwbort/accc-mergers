import { Link } from 'react-router-dom';
import { FaArrowRightLong, FaCircleCheck, FaScaleBalanced, FaClock, FaFileCirclePlus, FaTriangleExclamation } from 'react-icons/fa6';
import { mergerPath } from '../../utils/slug';
import { getDaysRemaining, isDatePast } from '../../utils/dates';
import { useFetchData } from '../../hooks/useFetchData';
import { API_ENDPOINTS } from '../../config';
import LoadingSpinner from '../../components/LoadingSpinner';
import SEO from '../../components/SEO';
import ConceptSwitcher from './ConceptSwitcher';
import { clearanceRate, relativeTime } from './conceptHelpers';

// ── Concept 4 · "Bento" ──────────────────────────────────────────────────────
// A modern asymmetric bento-box grid. Each metric gets its own colour-blocked
// tile sized to its importance — playful, glanceable, and lifting the palette
// already defined in tailwind.config.js (cleared / phase-1 / phase-2 / etc.).
// For the casual visitor who wants the whole picture in one colourful screen.

function Tile({ className = '', children }) {
  return (
    <div className={`relative rounded-3xl p-5 sm:p-6 overflow-hidden flex flex-col ${className}`}>
      {children}
    </div>
  );
}

function DashboardBento() {
  const { data: stats, loading, error } = useFetchData(API_ENDPOINTS.stats, { cacheKey: 'dashboard-stats' });
  const { data: upcomingData } = useFetchData(API_ENDPOINTS.upcomingEvents, { cacheKey: 'dashboard-events' });

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;
  if (!stats) return null;

  const underAssessment = stats.by_status?.['Under assessment'] ?? 0;
  const rate = clearanceRate(stats);
  const medianBd = stats.phase_duration?.median_business_days;
  const avgBd = Math.round(stats.phase_duration?.average_business_days ?? 0);
  const phase2 = stats.by_determination?.['Referred to phase 2'] ?? 0;
  const pct = stats.phase_duration?.percentiles ?? {};
  const recent = (stats.recent_mergers ?? []).slice(0, 3);
  const latestDet = (stats.recent_determinations ?? [])[0];
  const topIndustry = (stats.top_industries ?? [])[0];
  const nextEvent = (upcomingData?.events ?? [])
    .filter((e) => !isDatePast(e.date))
    .sort((a, b) => new Date(a.date) - new Date(b.date))[0];

  return (
    <>
      <SEO title="Dashboard concept · Bento" description="Bento-grid ACCC merger dashboard concept." url="/concepts/bento" />
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <ConceptSwitcher current="bento" />

        <header className="mt-8 mb-6">
          <p className="text-xs font-semibold uppercase tracking-widest text-accent-dark mb-1">At a glance</p>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">Merger review, boxed up</h1>
        </header>

        <div className="grid grid-cols-2 lg:grid-cols-4 auto-rows-[10.5rem] gap-3 sm:gap-4">
          {/* Hero: under assessment + recent list */}
          <Tile className="col-span-2 row-span-2 bg-gradient-to-br from-primary-dark via-primary to-primary-light text-white">
            <div className="text-6xl sm:text-7xl font-bold tracking-tight tabular-nums leading-none">{underAssessment}</div>
            <div className="mt-1 text-white/80 font-medium">mergers under assessment</div>
            <div className="mt-auto pt-4 space-y-2 border-t border-white/15">
              {recent.map((m) => (
                <Link key={m.merger_id} to={mergerPath(m.merger_id, m.merger_name)} className="flex items-center gap-2 text-sm text-white/85 hover:text-white group">
                  <FaFileCirclePlus className="h-3 w-3 shrink-0 text-accent-light" />
                  <span className="truncate flex-1">{m.merger_name}</span>
                  <FaArrowRightLong className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                </Link>
              ))}
            </div>
          </Tile>

          {/* Clearance rate */}
          <Tile className="col-span-2 bg-cleared-pale border border-cleared-light/40">
            <div className="flex items-center gap-2 text-cleared-dark text-sm font-semibold"><FaCircleCheck /> Cleared at Phase 1</div>
            <div className="mt-auto flex items-end gap-2">
              <span className="text-5xl font-bold tracking-tight tabular-nums text-cleared-dark">{rate != null ? `${rate}%` : '—'}</span>
              <span className="text-sm text-cleared-dark/70 mb-1.5">{stats.by_determination?.['Approved'] ?? 0} of {Object.values(stats.by_determination ?? {}).reduce((a, b) => a + b, 0)}</span>
            </div>
          </Tile>

          {/* Median days */}
          <Tile className="bg-phase-1-pale border border-phase-1-light/40">
            <div className="flex items-center gap-1.5 text-phase-1-dark text-xs font-semibold"><FaClock className="h-3 w-3" /> Median</div>
            <div className="mt-auto">
              <span className="text-4xl font-bold tabular-nums text-phase-1-dark">{medianBd ?? '—'}</span>
              <span className="block text-xs text-phase-1-dark/70">business days · Phase 1</span>
            </div>
          </Tile>

          {/* Avg days */}
          <Tile className="bg-white border border-gray-100 shadow-card">
            <div className="text-xs font-semibold text-gray-400">Average</div>
            <div className="mt-auto">
              <span className="text-4xl font-bold tabular-nums text-gray-900">{avgBd || '—'}</span>
              <span className="block text-xs text-gray-400">business days</span>
            </div>
          </Tile>

          {/* Velocity bars */}
          <Tile className="col-span-2 bg-white border border-gray-100 shadow-card">
            <div className="text-sm font-semibold text-gray-700 mb-3">Cleared by day…</div>
            <div className="mt-auto space-y-2.5">
              {[['15', pct.day15], ['20', pct.day20], ['30', pct.day30]].filter(([, d]) => d).map(([label, d]) => (
                <div key={label} className="flex items-center gap-3">
                  <span className="w-6 text-xs text-gray-400 tabular-nums">d{label}</span>
                  <span className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
                    <span className="block h-2 rounded-full bg-primary" style={{ width: `${d.percentage}%` }} />
                  </span>
                  <span className="w-9 text-right text-xs font-semibold text-gray-700 tabular-nums">{d.percentage}%</span>
                </div>
              ))}
            </div>
          </Tile>

          {/* Waivers */}
          <Tile className="bg-new-merger-pale border border-new-merger-light/40">
            <div className="flex items-center gap-1.5 text-new-merger-dark text-xs font-semibold"><FaScaleBalanced className="h-3 w-3" /> Waivers</div>
            <div className="mt-auto">
              <span className="text-4xl font-bold tabular-nums text-new-merger-dark">{stats.total_waivers}</span>
              <span className="block text-xs text-new-merger-dark/70">{stats.by_waiver_determination?.['Approved'] ?? 0} approved</span>
            </div>
          </Tile>

          {/* Phase 2 */}
          <Tile className="bg-phase-2-pale border border-phase-2-light/40">
            <div className="flex items-center gap-1.5 text-phase-2-dark text-xs font-semibold"><FaTriangleExclamation className="h-3 w-3" /> Phase 2</div>
            <div className="mt-auto">
              <span className="text-4xl font-bold tabular-nums text-phase-2-dark">{phase2}</span>
              <span className="block text-xs text-phase-2-dark/70">referred for deeper review</span>
            </div>
          </Tile>

          {/* Latest determination spotlight */}
          {latestDet && (
            <Tile className="col-span-2 bg-gray-900 text-white">
              <div className="text-xs font-semibold uppercase tracking-wider text-accent-light">Latest determination</div>
              <Link to={mergerPath(latestDet.merger_id, latestDet.merger_name)} className="mt-2 block group">
                <p className="text-lg font-semibold leading-snug group-hover:text-accent-light transition-colors line-clamp-2">{latestDet.merger_name}</p>
              </Link>
              <div className="mt-auto flex items-center gap-2 text-sm text-white/70">
                <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-white/10 text-white text-xs font-semibold">{latestDet.determination}</span>
                <span>{relativeTime(latestDet.determination_date)}</span>
              </div>
            </Tile>
          )}

          {/* Top industry */}
          {topIndustry && (
            <Tile className="bg-white border border-gray-100 shadow-card">
              <div className="text-xs font-semibold text-gray-400">Busiest sector</div>
              <Link to="/industries" className="mt-2 text-sm font-semibold text-gray-900 hover:text-primary leading-snug line-clamp-3">{topIndustry.name}</Link>
              <div className="mt-auto text-2xl font-bold tabular-nums text-primary">{topIndustry.count}<span className="text-xs font-normal text-gray-400 ml-1">deals</span></div>
            </Tile>
          )}

          {/* Next deadline */}
          {nextEvent && (
            <Tile className="bg-accent text-white">
              <div className="text-xs font-semibold uppercase tracking-wider text-white/80">Next deadline</div>
              <div className="mt-1 text-3xl font-bold tabular-nums">
                {(() => { const d = getDaysRemaining(nextEvent.date); return d === 0 ? 'Today' : `${d}d`; })()}
              </div>
              <Link to={mergerPath(nextEvent.merger_id, nextEvent.merger_name)} className="mt-auto text-xs text-white/90 hover:text-white leading-snug line-clamp-2">
                {nextEvent.event_type_display} · {nextEvent.merger_name}
              </Link>
            </Tile>
          )}
        </div>
      </div>
    </>
  );
}

export default DashboardBento;
