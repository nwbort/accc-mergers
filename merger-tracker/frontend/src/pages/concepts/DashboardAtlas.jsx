import { Link } from 'react-router-dom';
import { FaArrowRightLong, FaLayerGroup } from 'react-icons/fa6';
import { mergerPath } from '../../utils/slug';
import { relativeTime } from './conceptHelpers';
import { useFetchData } from '../../hooks/useFetchData';
import { API_ENDPOINTS } from '../../config';
import LoadingSpinner from '../../components/LoadingSpinner';
import SEO from '../../components/SEO';
import ConceptSwitcher from './ConceptSwitcher';

// ── Concept 5 · "Atlas" ──────────────────────────────────────────────────────
// A sector-first dashboard. Most views lead with time; this one leads with
// *where* — a treemap-style heatmap of industries packed by deal volume and
// shaded by intensity. For the economist / policy watcher asking which corners
// of the economy competition review is concentrating on.

// Map a 0..1 intensity to one of the primary-tinted steps. Full class strings
// so Tailwind's scanner keeps them.
function cellTone(intensity) {
  if (intensity > 0.66) return 'bg-primary text-white hover:bg-primary-dark';
  if (intensity > 0.33) return 'bg-primary/60 text-white hover:bg-primary/70';
  if (intensity > 0.15) return 'bg-primary/25 text-primary-dark hover:bg-primary/35';
  return 'bg-primary/10 text-primary-dark hover:bg-primary/20';
}

function DashboardAtlas() {
  const { data: stats, loading, error } = useFetchData(API_ENDPOINTS.stats, { cacheKey: 'dashboard-stats' });
  const { data: industriesData } = useFetchData(API_ENDPOINTS.industries, { cacheKey: 'dashboard-industries' });

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;
  if (!stats) return null;

  const industries = (industriesData?.industries ?? []).slice(0, 28);
  const maxCount = Math.max(...industries.map((i) => i.merger_count), 1);
  const totalIndustries = industriesData?.total_industries ?? industries.length;
  const recentDet = (stats.recent_determinations ?? []).slice(0, 4);

  return (
    <>
      <SEO title="Dashboard concept · Atlas" description="Industry heatmap ACCC merger dashboard concept." url="/concepts/atlas" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <ConceptSwitcher current="atlas" />

        <header className="mt-8 mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-accent-dark mb-1 flex items-center gap-2">
              <FaLayerGroup className="h-3.5 w-3.5" /> The map of merger activity
            </p>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">Where Australia's deals are happening</h1>
          </div>
          <div className="flex gap-6">
            <div>
              <div className="text-3xl font-bold tabular-nums text-gray-900">{totalIndustries}</div>
              <div className="text-xs text-gray-400">sectors active</div>
            </div>
            <div>
              <div className="text-3xl font-bold tabular-nums text-gray-900">{stats.total_mergers}</div>
              <div className="text-xs text-gray-400">notifications</div>
            </div>
          </div>
        </header>

        {/* Treemap-style packed heatmap. flex-grow proportional to count gives a
            justified, treemap-like layout without a charting dependency. */}
        <div className="flex flex-wrap gap-2">
          {industries.map((ind) => {
            const intensity = ind.merger_count / maxCount;
            return (
              <Link
                key={ind.code}
                to={`/industries/${ind.code}`}
                className={`group relative rounded-xl px-4 py-3 flex flex-col justify-between transition-colors ${cellTone(intensity)}`}
                style={{ flexGrow: ind.merger_count, flexBasis: `${120 + ind.merger_count * 4}px`, minHeight: '4.5rem' }}
              >
                <span className="text-[13px] font-semibold leading-tight line-clamp-2 pr-4">{ind.name}</span>
                <span className="mt-1 text-2xl font-bold tabular-nums leading-none">{ind.merger_count}</span>
                <FaArrowRightLong className="absolute top-3 right-3 h-3 w-3 opacity-0 group-hover:opacity-70 transition-opacity" />
              </Link>
            );
          })}
        </div>

        {/* Legend */}
        <div className="mt-4 flex items-center gap-3 text-xs text-gray-400">
          <span>Fewer deals</span>
          <span className="flex gap-1">
            <span className="h-3 w-6 rounded bg-primary/10" />
            <span className="h-3 w-6 rounded bg-primary/25" />
            <span className="h-3 w-6 rounded bg-primary/60" />
            <span className="h-3 w-6 rounded bg-primary" />
          </span>
          <span>More deals</span>
          <Link to="/industries" className="ml-auto inline-flex items-center gap-1.5 font-medium text-primary hover:text-primary-dark">
            All {totalIndustries} sectors <FaArrowRightLong className="h-3 w-3" />
          </Link>
        </div>

        {/* Recent activity across sectors */}
        <div className="mt-10">
          <h2 className="text-sm font-bold uppercase tracking-wider text-gray-500 mb-3">Latest determinations across sectors</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {recentDet.map((d) => {
              const cleared = d.determination === 'Approved' || d.determination === 'Not opposed';
              return (
                <Link key={`${d.merger_id}-${d.determination_date}`} to={mergerPath(d.merger_id, d.merger_name)} className="flex items-center gap-3 rounded-xl border border-gray-100 bg-white shadow-card hover:shadow-card-hover transition-all px-4 py-3 group">
                  <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${cleared ? 'bg-emerald-500' : d.determination === 'Referred to phase 2' ? 'bg-amber-500' : 'bg-purple-500'}`} />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900 truncate group-hover:text-primary transition-colors">{d.merger_name}</p>
                    <p className="text-xs text-gray-400">{d.determination} · {relativeTime(d.determination_date)}</p>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}

export default DashboardAtlas;
