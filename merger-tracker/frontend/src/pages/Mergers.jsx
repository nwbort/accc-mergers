import { useState, useEffect, useMemo, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import StatusBadge from '../components/StatusBadge';
import BellIcon from '../components/BellIcon';
import WaiverBadge from '../components/WaiverBadge';
import SEO from '../components/SEO';
import { formatDate } from '../utils/dates';
import { API_ENDPOINTS } from '../config';
import { dataCache } from '../utils/dataCache';
import { useTracking } from '../context/TrackingContext';
import { useDebounce } from '../hooks/useDebounce';
import { buildSearchIndex, searchMergers, clearSearchIndex } from '../utils/searchIndex';

const SORT_FIELDS = [
  { value: 'notification', label: 'Notification date' },
  { value: 'determination', label: 'Determination date' },
];

const SEARCH_DEBOUNCE_MS = 300;
const PAGE_SIZE = 50;
// Max concurrent page fetches to avoid saturating the connection pool
const FETCH_BATCH_SIZE = 4;

const sortMergers = (list, sortBy = 'notification-desc') => {
  return [...list].sort((a, b) => {
    switch (sortBy) {
      case 'notification-asc': {
        const dateA = a.effective_notification_datetime || '';
        const dateB = b.effective_notification_datetime || '';
        return dateA.localeCompare(dateB);
      }
      case 'determination-desc': {
        const dateA = a.determination_publication_date;
        const dateB = b.determination_publication_date;
        if (!dateA && !dateB) return 0;
        if (!dateA) return 1;
        if (!dateB) return -1;
        return dateB.localeCompare(dateA);
      }
      case 'determination-asc': {
        const dateA = a.determination_publication_date;
        const dateB = b.determination_publication_date;
        if (!dateA && !dateB) return 0;
        if (!dateA) return 1;
        if (!dateB) return -1;
        return dateA.localeCompare(dateB);
      }
      case 'notification-desc':
      default: {
        const dateA = a.effective_notification_datetime || '';
        const dateB = b.effective_notification_datetime || '';
        return dateB.localeCompare(dateA);
      }
    }
  });
};

function Mergers() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [mergers, setMergers] = useState(() => dataCache.get('mergers-list') || []);
  const [loading, setLoading] = useState(() => !dataCache.has('mergers-list'));
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);

  // searchTerm is kept as local state so the input is responsive and debouncing works.
  // All other filter values are derived directly from the URL (source of truth).
  const [searchTerm, setSearchTerm] = useState(() => searchParams.get('q') || '');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const { isTracked, toggleTracking } = useTracking();

  // Derive filter state from URL params — no local state duplication needed
  const statusFilter = searchParams.get('status') || 'all';
  const phaseFilter = searchParams.get('phase') || 'all';
  const sortBy = searchParams.get('sort') || 'notification-desc';
  const trackedOnly = searchParams.get('tracked') === 'true';

  // Initialize search index from session cache if merger data is already cached
  const [searchIndex, setSearchIndex] = useState(() => {
    const cachedMergers = dataCache.get('mergers-list') || [];
    return cachedMergers.length ? buildSearchIndex(cachedMergers) : null;
  });

  const debouncedSearchTerm = useDebounce(searchTerm, SEARCH_DEBOUNCE_MS);

  // Sync searchTerm from URL on back/forward navigation; also persist filter state.
  // For regular typing, searchTerm is set directly on the input (see onChange below)
  // so React skips the extra render when this effect fires with the same value.
  useEffect(() => {
    setSearchTerm(searchParams.get('q') || '');
    sessionStorage.setItem('mergers_filter_params', searchParams.toString());
  }, [searchParams]);

  // Auto-open the filter panel on desktop when the page is loaded with active filters
  // (e.g. arriving from a shared link). Run once on mount only.
  useEffect(() => {
    const hasActiveFilters =
      searchParams.get('phase') ||
      searchParams.get('status') ||
      searchParams.get('tracked') === 'true';
    if (hasActiveFilters && window.matchMedia('(min-width: 768px)').matches) {
      setFiltersOpen(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchMergers();
  }, []);

  const fetchMergers = async () => {
    try {
      // First, fetch metadata to know how many pages there are
      const metaResponse = await fetch(API_ENDPOINTS.mergersListMeta);

      if (!metaResponse.ok) throw new Error('Failed to fetch merger list metadata');

      const meta = await metaResponse.json();
      const totalPages = meta.total_pages;

      // Fetch pages in batches to avoid saturating the browser's connection pool.
      // Promise.all within each batch still parallelises those requests.
      const allResponses = [];
      for (let i = 1; i <= totalPages; i += FETCH_BATCH_SIZE) {
        const batch = [];
        for (let j = i; j < i + FETCH_BATCH_SIZE && j <= totalPages; j++) {
          batch.push(fetch(API_ENDPOINTS.mergersListPage(j)));
        }
        const batchResponses = await Promise.all(batch);
        allResponses.push(...batchResponses);
      }

      const pagesData = await Promise.all(
        allResponses.map((r) => {
          if (!r.ok) throw new Error('Failed to fetch merger page');
          return r.json();
        })
      );

      const allMergers = pagesData.flatMap((p) => p.mergers);

      dataCache.set('mergers-list', allMergers);
      setMergers(allMergers);

      // Clear the session-cached index so it is rebuilt from the freshly fetched
      // data rather than returning the stale index from the previous navigation.
      clearSearchIndex();
      setSearchIndex(buildSearchIndex(allMergers));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const updateParam = (key, value, defaultValue) => {
    const params = new URLSearchParams(searchParams);
    if (value && value !== defaultValue) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    setSearchParams(params);
  };

  const activeFilterCount = [
    phaseFilter !== 'all',
    statusFilter !== 'all',
    trackedOnly,
  ].filter(Boolean).length;

  // Filtered mergers (unsorted). Recomputes only when data or filter values change.
  // Starting from the raw `mergers` array avoids an up-front spread on every run —
  // each .filter() call already produces a new array.
  const filteredMergers = useMemo(() => {
    if (!mergers.length || !searchIndex) return [];

    let filtered = mergers;

    if (trackedOnly) {
      filtered = filtered.filter((m) => isTracked(m.merger_id));
    }

    if (phaseFilter === 'phase1') {
      filtered = filtered.filter((m) => m.stage && m.stage.includes('Phase 1'));
    } else if (phaseFilter === 'phase2') {
      filtered = filtered.filter((m) => m.stage && m.stage.includes('Phase 2'));
    } else if (phaseFilter === 'waivers') {
      filtered = filtered.filter((m) => m.is_waiver);
    }

    if (statusFilter !== 'all') {
      filtered = filtered.filter((m) => {
        const displayedOutcome = m.accc_determination || m.status;
        return displayedOutcome === statusFilter;
      });
    }

    if (debouncedSearchTerm) {
      filtered = searchMergers(filtered, debouncedSearchTerm, searchIndex);
    }

    return filtered;
  }, [mergers, searchIndex, debouncedSearchTerm, statusFilter, phaseFilter, trackedOnly, isTracked]);

  // Sorted mergers — separate memo so changing sort order only re-sorts,
  // not re-filters. sortMergers spreads its input so the original is not mutated.
  const sortedMergers = useMemo(
    () => sortMergers(filteredMergers, sortBy),
    [filteredMergers, sortBy]
  );

  // Status options for the dropdown — only recomputes when the data changes
  const outcomes = useMemo(
    () => ['all', ...new Set(mergers.map((m) => m.accc_determination || m.status))],
    [mergers]
  );

  // Paginated slice of sorted results
  const visibleMergers = sortedMergers.slice(0, page * PAGE_SIZE);
  const hasMore = visibleMergers.length < sortedMergers.length;

  // Reset to page 1 whenever filters or sort order change
  useEffect(() => {
    setPage(1);
  }, [filteredMergers, sortBy]);

  // Sentinel element watched by IntersectionObserver to trigger the next page
  const sentinelRef = useRef(null);

  useEffect(() => {
    if (!hasMore) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setPage((p) => p + 1);
        }
      },
      { rootMargin: '200px' }
    );
    const el = sentinelRef.current;
    if (el) observer.observe(el);
    return () => observer.disconnect();
  }, [hasMore]);

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;

  return (
    <>
      <SEO
        title="All Mergers"
        description="Browse all Australian mergers and acquisitions being reviewed by the ACCC. Search, filter, and track merger statuses and determinations."
        url="/mergers"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        {/* Search & Filters */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-5 mb-6">
          {/* Search row with filter toggle */}
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              <input
                type="text"
                id="search"
                className={`w-full pl-10 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary focus:bg-white transition-all ${
                  searchTerm ? 'pr-10' : 'pr-3'
                }`}
                placeholder="Search mergers, companies, or industries..."
                aria-label="Search mergers, companies, or industries"
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  updateParam('q', e.target.value, '');
                }}
              />
              {searchTerm && (
                <button
                  onClick={() => {
                    setSearchTerm('');
                    updateParam('q', '', '');
                  }}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                  aria-label="Clear search"
                  type="button"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
            <button
              onClick={() => setFiltersOpen(!filtersOpen)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium border transition-all ${
                filtersOpen || activeFilterCount > 0
                  ? 'bg-primary text-white border-primary shadow-sm'
                  : 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100'
              }`}
              aria-label="Toggle filters"
              aria-expanded={filtersOpen}
            >
              <span className="relative">
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" />
                </svg>
                {activeFilterCount > 0 && (
                  <span className="absolute -top-1.5 -right-1.5 text-[10px] font-bold text-white leading-none">
                    {activeFilterCount}
                  </span>
                )}
              </span>
              <span className="hidden sm:inline">Filters</span>
            </button>
          </div>

          {/* Collapsible filter panel */}
          {filtersOpen && (
            <div className="mt-4 pt-4 border-t border-gray-100 animate-fade-in">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div>
                  <label
                    htmlFor="phase"
                    className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-2"
                  >
                    Phase
                  </label>
                  <select
                    id="phase"
                    className="w-full px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary focus:bg-white transition-all appearance-none"
                    value={phaseFilter}
                    onChange={(e) => updateParam('phase', e.target.value, 'all')}
                    aria-label="Filter by merger phase"
                  >
                    <option value="all">All phases</option>
                    <option value="phase1">Phase 1</option>
                    <option value="phase2">Phase 2</option>
                    <option value="waivers">Waiver</option>
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="status"
                    className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-2"
                  >
                    Status
                  </label>
                  <select
                    id="status"
                    className="w-full px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary focus:bg-white transition-all appearance-none"
                    value={statusFilter}
                    onChange={(e) => updateParam('status', e.target.value, 'all')}
                    aria-label="Filter by merger status"
                  >
                    {outcomes.map((outcome) => (
                      <option key={outcome} value={outcome}>
                      {outcome === 'all'
                        ? 'All statuses'
                        : outcome}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label
                    className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-2"
                  >
                    Tracked
                  </label>
                  <button
                    role="switch"
                    aria-checked={trackedOnly}
                    onClick={() => updateParam('tracked', !trackedOnly ? 'true' : '', '')}
                    className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm border transition-all ${
                      trackedOnly
                        ? 'bg-primary/5 border-primary/30 text-primary'
                        : 'bg-gray-50 border-gray-200 text-gray-500 hover:bg-gray-100'
                    }`}
                  >
                    <span
                      className={`relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition-colors ${
                        trackedOnly ? 'bg-primary' : 'bg-gray-300'
                      }`}
                    >
                      <span
                        className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transform transition-transform ${
                          trackedOnly ? 'translate-x-4' : 'translate-x-0.5'
                        }`}
                      />
                    </span>
                    <span className="font-medium">Tracked mergers only</span>
                  </button>
                </div>
              </div>
              {activeFilterCount > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-100 flex justify-end">
                  <button
                    onClick={() => {
                      const params = new URLSearchParams(searchParams);
                      params.delete('phase');
                      params.delete('status');
                      params.delete('tracked');
                      setSearchParams(params);
                    }}
                    className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
                  >
                    Clear all filters
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Results count & Sort */}
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm text-gray-400">
            Showing {visibleMergers.length} of {sortedMergers.length} mergers
          </p>
          <div className="flex items-center gap-2">
            <label htmlFor="sort" className="text-sm text-gray-400 hidden sm:inline">Sort by</label>
            <select
              id="sort"
              className="px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-600 focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all appearance-none cursor-pointer"
              value={sortBy.replace(/-(?:asc|desc)$/, '')}
              onChange={(e) => {
                const dir = sortBy.endsWith('-asc') ? 'asc' : 'desc';
                updateParam('sort', `${e.target.value}-${dir}`, 'notification-desc');
              }}
              aria-label="Sort field"
            >
              {SORT_FIELDS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <button
              onClick={() => {
                const field = sortBy.replace(/-(?:asc|desc)$/, '');
                const newDir = sortBy.endsWith('-asc') ? 'desc' : 'asc';
                updateParam('sort', `${field}-${newDir}`, 'notification-desc');
              }}
              className="p-1 text-gray-400 hover:text-gray-600 transition-all"
              aria-label={sortBy.endsWith('-asc') ? 'Sort descending' : 'Sort ascending'}
              title={sortBy.endsWith('-asc') ? 'Ascending (click for descending)' : 'Descending (click for ascending)'}
            >
              <svg className={`h-4 w-4 transition-transform ${sortBy.endsWith('-asc') ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 13.5L12 21m0 0l-7.5-7.5M12 21V3" />
              </svg>
            </button>
          </div>
        </div>

        {/* Mergers List */}
        <div className="space-y-3">
          {visibleMergers.map((merger) => {
            // Compute once per item rather than calling isTracked 4 times in the JSX
            const tracked = isTracked(merger.merger_id);
            return (
              <div
                key={merger.merger_id}
                className="bg-white rounded-2xl border border-gray-100 shadow-card hover:shadow-card-hover hover:border-gray-200 transition-all duration-200"
              >
                <div className="p-5">
                  <div className="flex items-start justify-between gap-3">
                    <Link
                      to={`/mergers/${merger.merger_id}`}
                      className="flex-1 min-w-0"
                      aria-label={`View merger details for ${merger.merger_name}`}
                    >
                      <div className="flex items-center gap-2">
                        {tracked && (
                          <svg className="h-4 w-4 flex-shrink-0 text-primary" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
                          </svg>
                        )}
                        <h3 className="text-base font-semibold text-gray-900 truncate hover:text-primary transition-colors">
                          {merger.merger_name}
                        </h3>
                        {merger.is_waiver && <WaiverBadge className="flex-shrink-0" />}
                      </div>
                      <p className="text-xs text-gray-400 mt-1">
                        {merger.merger_id} · {merger.stage || 'N/A'}
                      </p>
                    </Link>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <StatusBadge
                        status={merger.status}
                        determination={merger.accc_determination}
                      />
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          toggleTracking(merger.merger_id);
                        }}
                        className={`hidden md:inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 ${
                          tracked
                            ? 'bg-primary text-white hover:bg-primary-dark shadow-sm'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                        }`}
                        aria-pressed={tracked}
                        aria-label={tracked ? 'Stop tracking this merger' : 'Track this merger for updates'}
                      >
                        <BellIcon filled={tracked} className="w-3.5 h-3.5" />
                        {tracked ? 'Tracking' : 'Track'}
                      </button>
                    </div>
                  </div>

                  <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-gray-400 mb-0.5">
                        {merger.is_waiver ? 'Application date' : 'Notification date'}
                      </p>
                      <p className="text-sm font-medium text-gray-700">
                        {!merger.effective_notification_datetime && merger.status?.toLowerCase().includes('suspended')
                          ? 'None - assessment suspended'
                          : formatDate(merger.effective_notification_datetime)}
                      </p>
                    </div>
                    {(merger.determination_publication_date || (merger.end_of_determination_period && !merger.status?.toLowerCase().includes('suspended'))) && (
                      <div>
                        <p className="text-xs text-gray-400 mb-0.5">
                          {merger.determination_publication_date ? 'Determination date' : 'End of determination period'}
                        </p>
                        <p className="text-sm font-medium text-gray-700">
                          {merger.determination_publication_date
                            ? formatDate(merger.determination_publication_date)
                            : formatDate(merger.end_of_determination_period)}
                        </p>
                      </div>
                    )}
                  </div>

                  {merger.anzsic_codes && merger.anzsic_codes.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {merger.anzsic_codes.map((code) => (
                        <span
                          key={`${merger.merger_id}-anzsic-${code.code || code.name}`}
                          className="inline-flex items-center px-2 py-0.5 rounded-md text-xs bg-gray-50 text-gray-500 border border-gray-100"
                        >
                          {code.name}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {hasMore && <div ref={sentinelRef} className="h-12" />}

        {sortedMergers.length === 0 && (
          <div className="text-center py-16">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gray-100 flex items-center justify-center">
              <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
            </div>
            <p className="text-gray-500 font-medium">
              {trackedOnly ? 'No tracked mergers yet' : 'No mergers found'}
            </p>
            <p className="text-gray-400 text-sm mt-1">Try adjusting your search or filters</p>
          </div>
        )}
      </div>
    </>
  );
}

export default Mergers;
