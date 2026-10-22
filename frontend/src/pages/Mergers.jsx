import { useState, useEffect, useLayoutEffect, useMemo, useRef, useCallback } from 'react';
import { FaSearch, FaTimes, FaSlidersH, FaArrowDown, FaList, FaTable } from 'react-icons/fa';
import { useSearchParams, useNavigate, useLocation, useNavigationType } from 'react-router';
import { mergerPath } from '../utils/slug';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import MergerListCard from '../components/MergerListCard';
import MergerListTable from '../components/MergerListTable';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { useTracking } from '../context/TrackingContext';
import { useDebounce } from '../hooks/useDebounce';
import { buildSearchIndex } from '../utils/searchIndex';
import { MERGERS_LIST_KEY } from '../utils/mergerList';
import { FILTER_PARAMS, activeFilterTests, applyFilters, filterOptions } from '../utils/mergerFilters';
import { loadListPosition, saveListPosition } from '../utils/mergerListPosition';
import { CARD, SECTION_HEADING } from '../utils/classNames';
import { STATIC_PAGE_META } from '../utils/pageMeta';
import { DEFAULT_SORT, SORT_FIELDS, SORT_FIELDS_BY_VALUE, normaliseSort, splitSort, sortMergers } from '../utils/mergerSort';

// Title and description live in the shared table so this page and the
// build-time prerenderer emit the same <head>.
const PAGE_META = STATIC_PAGE_META['/mergers'];

const SEARCH_DEBOUNCE_MS = 300;
const PAGE_SIZE = 50;
// Stable empty list while loading, so memos keyed on it don't churn.
const NO_MERGERS = [];

// Whether this document has shown the list before — see restoredPosition.
let listShownThisDocument = false;

const SELECT_CLASSES = 'w-full px-3 py-2.5 bg-gray-50 border rounded-xl text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary focus:bg-white transition-all appearance-none';

const withCount = (label, count) => `${label} (${count})`;

// A filter select: highlighted while set, each option carrying its count.
function FilterSelect({ id, label, value, allLabel, options, onChange }) {
  return (
    <div>
      <label htmlFor={id} className={`block ${SECTION_HEADING} mb-2`}>
        {label}
      </label>
      <select
        id={id}
        className={`${SELECT_CLASSES} ${value ? 'border-primary border-2' : 'border-gray-200'}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{allLabel}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.count === undefined ? o.label : withCount(o.label, o.count)}
          </option>
        ))}
        {/* A shared link can name a value the data no longer has (a year
            with nothing left in it, say). Keep it selectable so the select
            still says what is being applied. */}
        {value && !options.some((o) => o.value === value) && (
          <option value={value}>{value}</option>
        )}
      </select>
    </div>
  );
}

// An on/off filter, styled as a switch.
function FilterSwitch({ heading, label, checked, onToggle }) {
  return (
    <div>
      <p className={`${SECTION_HEADING} mb-2`} aria-hidden="true">{heading}</p>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={onToggle}
        className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm transition-all ${
          checked
            ? 'bg-primary/5 border-2 border-primary text-primary'
            : 'bg-gray-50 border border-gray-200 text-gray-500 hover:bg-gray-100'
        }`}
      >
        <span
          className={`relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition-colors ${
            checked ? 'bg-primary' : 'bg-gray-300'
          }`}
        >
          <span
            className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transform transition-transform ${
              checked ? 'translate-x-4' : 'translate-x-0.5'
            }`}
          />
        </span>
        <span className="font-medium">{label}</span>
      </button>
    </div>
  );
}

function Mergers() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const navigationType = useNavigationType();
  const listRef = useRef(null);

  // The whole list is one file (~110 KB gzipped). useFetchData shares it with
  // the command palette through dataCache and keeps it fresh in the
  // background.
  const { data, loading, error } = useFetchData(API_ENDPOINTS.mergersList, { cacheKey: MERGERS_LIST_KEY });
  const mergers = data?.mergers ?? NO_MERGERS;
  const searchIndex = useMemo(() => buildSearchIndex(mergers), [mergers]);

  // searchTerm is kept as local state so the input is responsive and debouncing works.
  // All other filter values are derived directly from the URL (source of truth).
  const [searchTerm, setSearchTerm] = useState(() => searchParams.get('q') || '');
  const debouncedSearchTerm = useDebounce(searchTerm, SEARCH_DEBOUNCE_MS);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const { isTracked, toggleTracking } = useTracking();

  const paramString = searchParams.toString();
  // 'all' was the phase and status selects' old "no filter" value; old links
  // still carry it.
  const unlessAll = (value) => (value && value !== 'all' ? value : '');
  const phaseFilter = unlessAll(searchParams.get('phase'));
  const statusFilter = unlessAll(searchParams.get('status'));
  const notifiedFilter = searchParams.get('notified') || '';
  const industryFilter = searchParams.get('industry') || '';
  const conditionsOnly = searchParams.get('conditions') === 'true';
  const trackedOnly = searchParams.get('tracked') === 'true';
  // An unrecognised ?sort= folds back to the default, so the select and the
  // direction labels always describe the order actually applied.
  const sortBy = normaliseSort(searchParams.get('sort') || DEFAULT_SORT);
  const { field: sortField, dir: sortDir } = splitSort(sortBy);
  const directionLabels = SORT_FIELDS_BY_VALUE[sortField];
  const tableView = searchParams.get('view') === 'table';

  // Coming back to the list — Back, or the detail page's "Back to all
  // mergers" — puts the reader where they were: as many pages showing, at
  // the same scroll offset. Read once, on mount. Loading the page also counts
  // as a POP, but that is an arrival rather than a return, so a POP only
  // restores once the list has already been shown in this document.
  const [restoredPosition] = useState(() => (
    (navigationType === 'POP' && listShownThisDocument) || location.state?.restoreListPosition
      ? loadListPosition(paramString)
      : null
  ));
  useEffect(() => {
    listShownThisDocument = true;
  }, []);
  const [page, setPage] = useState(() => restoredPosition?.page ?? 1);
  const [selectedIndex, setSelectedIndex] = useState(-1);

  // Back to the first page, and no keyboard selection, whenever what the list
  // holds or its order changes. Keyed on the inputs rather than on the
  // filtered array, so tracking a merger or a background data refresh leaves
  // the reader where they are.
  const listKey = [debouncedSearchTerm, ...FILTER_PARAMS.map((k) => searchParams.get(k)), sortBy].join('\u0000');
  const [pagedListKey, setPagedListKey] = useState(listKey);
  if (pagedListKey !== listKey) {
    setPagedListKey(listKey);
    setPage(1);
    setSelectedIndex(-1);
  }

  // Sync searchTerm from URL on back/forward navigation; also persist filter state.
  // For regular typing, searchTerm is set directly on the input (see onChange below)
  // so React skips the extra render when this effect fires with the same value.
  useEffect(() => {
    setSearchTerm(searchParams.get('q') || '');
    sessionStorage.setItem('mergers_filter_params', paramString);
  }, [searchParams, paramString]);

  // Auto-open the filter panel on desktop when the page is loaded with active filters
  // (e.g. arriving from a shared link). Run once on mount only.
  useEffect(() => {
    const hasActiveFilters = FILTER_PARAMS.some((k) => searchParams.get(k) && searchParams.get(k) !== 'all');
    if (hasActiveFilters && window.matchMedia('(min-width: 768px)').matches) {
      setFiltersOpen(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Remember the position as the reader scrolls and pages. A layout effect so
  // the last save on leaving runs before the list's DOM is removed — once it
  // is, the browser clamps scrollY to the next page's (shorter) height.
  const positionRef = useRef({ params: paramString, page });
  useLayoutEffect(() => {
    positionRef.current = { params: paramString, page };
  }, [paramString, page]);
  useLayoutEffect(() => {
    let frame = 0;
    const save = () => {
      const { params, page: p } = positionRef.current;
      saveListPosition(params, p, window.scrollY);
    };
    const onScroll = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        save();
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(frame);
      save();
    };
  }, []);

  // Scroll back to the saved offset once the list it was measured on is
  // rendered. In a frame, so it lands after ScrollToTop's reset to the top.
  const restoredRef = useRef(false);
  const listReady = mergers.length > 0;
  useEffect(() => {
    if (!restoredPosition || restoredRef.current || !listReady) return undefined;
    const frame = requestAnimationFrame(() => {
      restoredRef.current = true;
      window.scrollTo(0, restoredPosition.y);
    });
    return () => cancelAnimationFrame(frame);
  }, [restoredPosition, listReady]);

  const updateParam = (key, value, defaultValue = '') => {
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

  const setSort = (field, dir) => updateParam('sort', `${field}-${dir}`, DEFAULT_SORT);

  // Picking a field keeps the direction when it is already the sort, and
  // otherwise starts from that field's natural direction; the table headers
  // flip the direction when clicked again, as sortable headers do.
  const sortByColumn = (field) => {
    if (field === sortField) setSort(field, sortDir === 'asc' ? 'desc' : 'asc');
    else setSort(field, SORT_FIELDS_BY_VALUE[field].defaultDir);
  };

  const activeFilterCount = [
    phaseFilter, statusFilter, notifiedFilter, industryFilter, conditionsOnly, trackedOnly,
  ].filter(Boolean).length;

  const filterTests = useMemo(
    () => activeFilterTests(
      {
        q: debouncedSearchTerm,
        phase: phaseFilter,
        status: statusFilter,
        notified: notifiedFilter,
        industry: industryFilter,
        conditions: conditionsOnly ? 'true' : '',
        tracked: trackedOnly ? 'true' : '',
      },
      { isTracked, searchIndex },
    ),
    [debouncedSearchTerm, phaseFilter, statusFilter, notifiedFilter, industryFilter, conditionsOnly, trackedOnly, isTracked, searchIndex]
  );

  const filteredMergers = useMemo(() => applyFilters(mergers, filterTests), [mergers, filterTests]);

  // Sorted mergers — separate memo so changing sort order only re-sorts,
  // not re-filters. sortMergers spreads its input so the original is not mutated.
  const sortedMergers = useMemo(
    () => sortMergers(filteredMergers, sortBy),
    [filteredMergers, sortBy]
  );

  // Each select's options and counts. Only worked out while the panel is open.
  const options = useMemo(
    () => (filtersOpen ? filterOptions(mergers, filterTests) : null),
    [filtersOpen, mergers, filterTests]
  );

  // Paginated slice of sorted results
  const visibleMergers = sortedMergers.slice(0, page * PAGE_SIZE);
  const hasMore = visibleMergers.length < sortedMergers.length;

  // Sentinel element watched by IntersectionObserver to trigger the next page
  const sentinelRef = useRef(null);

  useEffect(() => {
    if (!hasMore) return undefined;
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
        title={PAGE_META.title}
        description={PAGE_META.description}
        url="/mergers"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        {/* The page leads straight into content, so the document's h1 is
            visually hidden rather than dropped: it names the page for screen
            readers and keeps the heading outline starting at level 1. */}
        <h1 className="sr-only">Mergers</h1>

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
                  updateParam('q', e.target.value);
                }}
              />
              {searchTerm && (
                <button
                  onClick={() => {
                    setSearchTerm('');
                    updateParam('q', '');
                  }}
                  // right-2 + p-1 pads the 16px glyph out to a 24px hit area
                  // (WCAG 2.5.8) while leaving it where it was.
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded text-gray-500 hover:text-gray-700 transition-colors"
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

          {/* Collapsible filter panel. Each count is what picking that option
              would leave, given the search and the other filters. */}
          {filtersOpen && options && (
            <div className="mt-4 pt-4 border-t border-gray-100 animate-fade-in">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <FilterSelect
                  id="phase"
                  label="Phase"
                  value={phaseFilter}
                  allLabel="All phases"
                  options={options.phase}
                  onChange={(v) => updateParam('phase', v)}
                />
                <FilterSelect
                  id="status"
                  label="Status"
                  value={statusFilter}
                  allLabel="All statuses"
                  options={options.status}
                  onChange={(v) => updateParam('status', v)}
                />
                <FilterSelect
                  id="notified"
                  label="Notified"
                  value={notifiedFilter}
                  allLabel="Any time"
                  options={options.notified}
                  onChange={(v) => updateParam('notified', v)}
                />
                <FilterSelect
                  id="industry"
                  label="Industry"
                  value={industryFilter}
                  allLabel="All industries"
                  options={options.industry}
                  onChange={(v) => updateParam('industry', v)}
                />
                <FilterSwitch
                  heading="Conditions"
                  label={withCount('Approved with conditions', options.conditions)}
                  checked={conditionsOnly}
                  onToggle={() => updateParam('conditions', conditionsOnly ? '' : 'true')}
                />
                <FilterSwitch
                  heading="Tracked"
                  label="Tracked mergers only"
                  checked={trackedOnly}
                  onToggle={() => updateParam('tracked', trackedOnly ? '' : 'true')}
                />
              </div>
              {activeFilterCount > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-100 flex justify-end">
                  <button
                    onClick={() => {
                      const params = new URLSearchParams(searchParams);
                      FILTER_PARAMS.forEach((k) => params.delete(k));
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

        {/* Results count, view & sort */}
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 mb-4">
          <p className="text-sm text-gray-500">
            Showing {visibleMergers.length} of {sortedMergers.length} mergers
          </p>
          <div className="flex items-center gap-3">
            <div role="group" aria-label="View" className="flex rounded-lg border border-gray-200 bg-white p-0.5">
              {[
                { value: '', label: 'Cards', Icon: FaList },
                { value: 'table', label: 'Table', Icon: FaTable },
              ].map(({ value, label, Icon }) => {
                const active = (value === 'table') === tableView;
                return (
                  <button
                    key={label}
                    type="button"
                    aria-pressed={active}
                    aria-label={`${label} view`}
                    title={`${label} view`}
                    onClick={() => updateParam('view', value)}
                    className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-sm transition-colors ${
                      active ? 'bg-primary text-white' : 'text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                    <span className="hidden sm:inline">{label}</span>
                  </button>
                );
              })}
            </div>
            <div className="flex items-center gap-2">
              <label htmlFor="sort" className="text-sm text-gray-500 hidden sm:inline">Sort by</label>
              <select
                id="sort"
                className="px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-600 focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all appearance-none cursor-pointer"
                value={sortField}
                onChange={(e) => {
                  const field = e.target.value;
                  // Keep the direction when only re-sorting the same field;
                  // switching fields starts from that field's natural direction.
                  setSort(field, field === sortField ? sortDir : SORT_FIELDS_BY_VALUE[field].defaultDir);
                }}
                aria-label="Sort field"
              >
                {SORT_FIELDS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <button
                onClick={() => setSort(sortField, sortDir === 'asc' ? 'desc' : 'asc')}
                className="p-1 text-gray-500 hover:text-gray-700 transition-all"
                aria-label={`Change sort order to ${sortDir === 'asc' ? directionLabels.desc : directionLabels.asc}`}
                title={`${sortDir === 'asc' ? directionLabels.asc : directionLabels.desc} — click for ${sortDir === 'asc' ? directionLabels.desc : directionLabels.asc}`}
              >
                <FaArrowDown className={`h-4 w-4 transition-transform ${sortDir === 'asc' ? 'rotate-180' : ''}`} aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>

        {/* Mergers List */}
        <div ref={listRef}>
          {tableView ? (
            visibleMergers.length > 0 && (
              <MergerListTable
                mergers={visibleMergers}
                selectedIndex={selectedIndex}
                isTracked={isTracked}
                sortField={sortField}
                sortDir={sortDir}
                onSort={sortByColumn}
              />
            )
          ) : (
            <div className="space-y-3">
              {visibleMergers.map((merger, idx) => (
                <MergerListCard
                  key={merger.merger_id}
                  merger={merger}
                  index={idx}
                  selected={idx === selectedIndex}
                  tracked={isTracked(merger.merger_id)}
                  onToggleTracking={toggleTracking}
                />
              ))}
            </div>
          )}
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
