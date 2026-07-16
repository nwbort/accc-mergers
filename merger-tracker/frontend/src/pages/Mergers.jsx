import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { FaSearch, FaTimes, FaSlidersH, FaArrowDown, FaStar } from 'react-icons/fa';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { mergerPath } from '../utils/slug';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import StatusBadge from '../components/StatusBadge';
import BellIcon from '../components/BellIcon';
import WaiverBadge from '../components/WaiverBadge';
import AppealBadge from '../components/AppealBadge';
import SEO from '../components/SEO';
import { formatDate } from '../utils/dates';
import { getBusinessDayProgress } from '../utils/businessDayProgress';
import { API_ENDPOINTS } from '../config';
import { dataCache } from '../utils/dataCache';
import { useTracking } from '../context/TrackingContext';
import { useDebounce } from '../hooks/useDebounce';
import { buildSearchIndex, searchMergers, clearSearchIndex } from '../utils/searchIndex';
import { PHASES } from '../constants/mergerStatus';
import { CARD, SECTION_HEADING } from '../utils/classNames';

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
  const navigate = useNavigate();
  const [mergers, setMergers] = useState(() => dataCache.get('mergers-list') || []);
  const [loading, setLoading] = useState(() => !dataCache.has('mergers-list'));
  const [error, setError] = useState(null);
  // Total merger count from list-meta.json — known from the very first request,
  // well before every page has loaded, so the unfiltered "of N" count doesn't
  // have to creep up page by page while the rest load in the background.
  const [totalMergerCount, setTotalMergerCount] = useState(() => dataCache.get('mergers-list')?.length ?? null);
  const [page, setPage] = useState(1);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const listRef = useRef(null);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchMergers = async () => {
    // Only render progressively on a cold visit — if a full list is already
    // cached (and showing), replacing it with a partial page-1-only list
    // while the rest re-fetches in the background would be a visible regression.
    const isColdVisit = mergers.length === 0;

    try {
      // First, fetch metadata to know how many pages there are
      const metaResponse = await fetch(API_ENDPOINTS.mergersListMeta);

      if (!metaResponse.ok) throw new Error('Failed to fetch merger list metadata');

      const meta = await metaResponse.json();
      const totalPages = meta.total_pages;
      setTotalMergerCount(meta.total);

      // list-page-N.json files are sorted ascending by notification date
      // (oldest first — new mergers only ever append to the last page, so
      // regenerating the pipeline only touches that one file). The default
      // frontend sort is notification-desc (newest first), so fetch the
      // *last* page first in that case — otherwise the first screen would
      // flash the oldest mergers before the background fetch replaces them
      // with the newest ones. For notification-asc, page 1 is already the
      // right first screen; the determination sorts have no page/sort
      // correlation, so page 1 is just a reasonable default there too.
      const initialPage = sortBy === 'notification-desc' ? totalPages : 1;

      const initialResponse = await fetch(API_ENDPOINTS.mergersListPage(initialPage));
      if (!initialResponse.ok) throw new Error('Failed to fetch merger page');
      const initialPageData = await initialResponse.json();
      let allMergers = initialPageData.mergers;

      if (isColdVisit) {
        // Render immediately with just this one page so users aren't stuck
        // looking at a spinner while the remaining ~8 pages load in the
        // background. The rest fill in silently (no progress UI) since a
        // banner that appears then disappears just shifts the list under it.
        // The search index is built without touching the shared dataCache
        // entry — that entry is reserved for the complete, final index so a
        // stale partial index is never mistaken for a complete one.
        setMergers(allMergers);
        setSearchIndex(buildSearchIndex(allMergers, { cache: false }));
        setLoading(false);
      }

      // Fetch remaining pages in batches to avoid saturating the browser's
      // connection pool. Promise.all within each batch still parallelises
      // those requests. Order doesn't matter — the default sort is always
      // re-applied to the combined list on render.
      const remainingPages = [];
      for (let p = 1; p <= totalPages; p++) {
        if (p !== initialPage) remainingPages.push(p);
      }

      for (let i = 0; i < remainingPages.length; i += FETCH_BATCH_SIZE) {
        const batchPages = remainingPages.slice(i, i + FETCH_BATCH_SIZE);
        const batchResponses = await Promise.all(
          batchPages.map((p) => fetch(API_ENDPOINTS.mergersListPage(p)))
        );
        const batchResults = await Promise.allSettled(
          batchResponses.map((r) => {
            if (!r.ok) throw new Error('Failed to fetch merger page');
            return r.json();
          })
        );
        const batchMergers = batchResults
          .filter((r) => r.status === 'fulfilled')
          .flatMap((r) => r.value.mergers);
        allMergers = allMergers.concat(batchMergers);

        if (isColdVisit) {
          setMergers(allMergers);
          setSearchIndex(buildSearchIndex(allMergers, { cache: false }));
        }
      }

      // Only now — once every page has arrived — write the shared caches, so
      // a partial list/index is never persisted as if it were complete.
      dataCache.set('mergers-list', allMergers);
      clearSearchIndex();
      setMergers(allMergers);
      setSearchIndex(buildSearchIndex(allMergers));
    } catch (err) {
      console.error('Failed to load mergers list:', err);
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
    // replace: true avoids pushing a history entry per keystroke/toggle, so
    // Back doesn't have to walk through every intermediate filter state.
    setSearchParams(params, { replace: true });
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
      filtered = filtered.filter((m) => m.stage && m.stage.includes(PHASES.PHASE_1));
    } else if (phaseFilter === 'phase2') {
      filtered = filtered.filter((m) => m.stage && m.stage.includes(PHASES.PHASE_2));
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

  // With no search/filter active, sortedMergers *is* every merger, so its count
  // otherwise creeps up page by page while background pages are still loading.
  // The real total is already known from list-meta.json, so use that instead.
  const hasActiveSearchOrFilter = activeFilterCount > 0 || Boolean(debouncedSearchTerm);
  const displayedTotal = !hasActiveSearchOrFilter && totalMergerCount !== null
    ? totalMergerCount
    : sortedMergers.length;

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

  // Reset keyboard selection when the visible list changes
  useEffect(() => {
    setSelectedIndex(-1);
  }, [sortedMergers]);

  // j/k/Enter keyboard navigation for the merger list
  const handleListKeyDown = useCallback((e) => {
    const tag = e.target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target.isContentEditable) return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    if (e.key === 'j') {
      e.preventDefault();
      setSelectedIndex((prev) => {
        const next = Math.min(prev + 1, visibleMergers.length - 1);
        const el = listRef.current?.querySelector(`[data-merger-index="${next}"]`);
        el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        return next;
      });
    } else if (e.key === 'k') {
      e.preventDefault();
      setSelectedIndex((prev) => {
        const next = Math.max(prev - 1, 0);
        const el = listRef.current?.querySelector(`[data-merger-index="${next}"]`);
        el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        return next;
      });
    } else if (e.key === 'Enter' && selectedIndex >= 0 && selectedIndex < visibleMergers.length) {
      e.preventDefault();
      navigate(mergerPath(visibleMergers[selectedIndex].merger_id, visibleMergers[selectedIndex].merger_name));
    }
  }, [visibleMergers, selectedIndex, navigate]);

  useEffect(() => {
    window.addEventListener('keydown', handleListKeyDown);
    return () => window.removeEventListener('keydown', handleListKeyDown);
  }, [handleListKeyDown]);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;

  return (
    <>
      <SEO
        title="All Mergers"
        description="Search every Australian merger notified to the ACCC. Filter by status, industry, acquirer, or outcome — cleared, declined, Phase 2, or under review."
        url="/mergers"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        {/* Search & Filters */}
        <div className={`${CARD} p-5 mb-6`}>
          {/* Search row with filter toggle */}
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <FaSearch className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" aria-hidden="true" />
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
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 transition-colors"
                  aria-label="Clear search"
                  type="button"
                >
                  <FaTimes className="h-4 w-4" aria-hidden="true" />
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
                <FaSlidersH className="h-4 w-4" aria-hidden="true" />
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
                    className={`block ${SECTION_HEADING} mb-2`}
                  >
                    Phase
                  </label>
                  <select
                    id="phase"
                    className={`w-full px-3 py-2.5 bg-gray-50 border rounded-xl text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary focus:bg-white transition-all appearance-none ${
                      phaseFilter !== 'all' ? 'border-primary border-2' : 'border-gray-200'
                    }`}
                    value={phaseFilter}
                    onChange={(e) => updateParam('phase', e.target.value, 'all')}
                    aria-label="Filter by merger phase"
                  >
                    <option value="all">All phases</option>
                    <option value="phase1">{PHASES.PHASE_1}</option>
                    <option value="phase2">{PHASES.PHASE_2}</option>
                    <option value="waivers">{PHASES.WAIVER}</option>
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="status"
                    className={`block ${SECTION_HEADING} mb-2`}
                  >
                    Status
                  </label>
                  <select
                    id="status"
                    className={`w-full px-3 py-2.5 bg-gray-50 border rounded-xl text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary focus:bg-white transition-all appearance-none ${
                      statusFilter !== 'all' ? 'border-primary border-2' : 'border-gray-200'
                    }`}
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
                    className={`block ${SECTION_HEADING} mb-2`}
                  >
                    Tracked
                  </label>
                  <button
                    role="switch"
                    aria-checked={trackedOnly}
                    onClick={() => updateParam('tracked', !trackedOnly ? 'true' : '', '')}
                    className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm transition-all ${
                      trackedOnly
                        ? 'bg-primary/5 border-2 border-primary text-primary'
                        : 'bg-gray-50 border border-gray-200 text-gray-500 hover:bg-gray-100'
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
                      setSearchParams(params, { replace: true });
                    }}
                    className="text-xs text-gray-500 hover:text-gray-700 transition-colors"
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
          <p className="text-sm text-gray-500">
            Showing {visibleMergers.length} of {displayedTotal} mergers
          </p>
          <div className="flex items-center gap-2">
            <label htmlFor="sort" className="text-sm text-gray-500 hidden sm:inline">Sort by</label>
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
              className="p-1 text-gray-500 hover:text-gray-700 transition-all"
              aria-label={sortBy.endsWith('-asc') ? 'Sort descending' : 'Sort ascending'}
              title={sortBy.endsWith('-asc') ? 'Ascending (click for descending)' : 'Descending (click for ascending)'}
            >
              <FaArrowDown className={`h-4 w-4 transition-transform ${sortBy.endsWith('-asc') ? 'rotate-180' : ''}`} aria-hidden="true" />
            </button>
          </div>
        </div>

        {/* Mergers List */}
        <div ref={listRef} className="space-y-3">
          {visibleMergers.map((merger, idx) => {
            // Compute once per item rather than calling isTracked 4 times in the JSX
            const tracked = isTracked(merger.merger_id);
            const isSelected = idx === selectedIndex;
            const businessDayProgress = getBusinessDayProgress(merger);
            return (
              <div
                key={merger.merger_id}
                data-merger-index={idx}
                role="link"
                tabIndex={0}
                aria-label={`View merger details for ${merger.merger_name}`}
                onClick={() => navigate(mergerPath(merger.merger_id, merger.merger_name))}
                onMouseDown={(e) => { if (e.button === 1) e.preventDefault(); }}
                onAuxClick={(e) => {
                  if (e.button === 1) window.open(mergerPath(merger.merger_id, merger.merger_name), '_blank');
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    navigate(mergerPath(merger.merger_id, merger.merger_name));
                  }
                }}
                className={`bg-white rounded-2xl border shadow-card hover:shadow-card-hover hover:border-gray-200 transition-all duration-200 cursor-pointer ${
                  isSelected ? 'border-primary/40 ring-2 ring-primary/20' : 'border-gray-100'
                }`}
              >
                <div className="p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        {tracked && (
                          <FaStar className="h-4 w-4 flex-shrink-0 text-primary" aria-hidden="true" />
                        )}
                        <h3 className="text-base font-semibold text-gray-900 truncate hover:text-primary transition-colors">
                          {merger.merger_name}
                        </h3>
                        {merger.is_waiver && <WaiverBadge className="flex-shrink-0" />}
                      </div>
                      <p className="text-xs text-gray-500 mt-1">
                        {merger.merger_id} · {merger.stage || 'N/A'}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {merger.under_appeal && <AppealBadge />}
                      <StatusBadge
                        status={merger.status}
                        determination={merger.accc_determination}
                        hasConditions={merger.has_conditions}
                        appeal={merger.appeal}
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

                  <div className={`mt-4 grid gap-4 ${
                    businessDayProgress ? 'grid-cols-2 md:grid-cols-3' : 'grid-cols-1 md:grid-cols-2'
                  }`}>
                    <div className={businessDayProgress ? 'order-1' : ''}>
                      <p className="text-xs text-gray-500 mb-0.5">
                        {merger.is_waiver ? 'Application date' : 'Notification date'}
                      </p>
                      <p className="text-sm font-medium text-gray-700">
                        {!merger.effective_notification_datetime && merger.status?.toLowerCase().includes('suspended')
                          ? 'None - assessment suspended'
                          : formatDate(merger.effective_notification_datetime)}
                      </p>
                    </div>
                    {(merger.determination_publication_date || (merger.end_of_determination_period && !merger.status?.toLowerCase().includes('suspended'))) && (
                      <div className={businessDayProgress ? 'order-3 md:order-2 col-span-2 md:col-span-1' : ''}>
                        <p className="text-xs text-gray-500 mb-0.5">
                          {merger.determination_publication_date ? 'Determination date' : 'End of determination period'}
                        </p>
                        <p className="text-sm font-medium text-gray-700">
                          {merger.determination_publication_date
                            ? formatDate(merger.determination_publication_date)
                            : formatDate(merger.end_of_determination_period)}
                        </p>
                      </div>
                    )}
                    {businessDayProgress && (
                      <div className="order-2 md:order-3">
                        <p className="text-xs text-gray-500 mb-0.5">Business days</p>
                        <p className={`text-sm font-medium ${
                          businessDayProgress.overdue ? 'text-amber-600' : 'text-gray-700'
                        }`}>
                          {businessDayProgress.overdue
                            ? 'Overdue'
                            : `${businessDayProgress.elapsed}/${businessDayProgress.total}`}
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
              <FaSearch className="w-8 h-8 text-gray-500" aria-hidden="true" />
            </div>
            <p className="text-gray-500 font-medium">
              {trackedOnly ? 'No tracked mergers yet' : 'No mergers found'}
            </p>
            <p className="text-gray-500 text-sm mt-1">Try adjusting your search or filters</p>
          </div>
        )}
      </div>
    </>
  );
}

export default Mergers;
