import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import SEO from '../components/SEO';
import ExternalLinkIcon from '../components/ExternalLinkIcon';
import { formatDate } from '../utils/dates';
import { API_ENDPOINTS } from '../config';
import { dataCache } from '../utils/dataCache';
import { useFetchData } from '../hooks/useFetchData';

const ITEMS_PER_PAGE = 15;
const LOAD_MORE_COUNT = 10;
const SCROLL_THRESHOLD_PX = 300;
// If fewer than this many events are displayed after the initial load, keep
// loading more pages automatically so the user has enough content to scroll
// and trigger the infinite-scroll handler. Required because the last (newest)
// page can have very few events — e.g. 503 total / 100 per page → 3 events.
const MIN_DISPLAYED_TO_ENABLE_SCROLL = 8;

const EVENT_TYPE_OPTIONS = [
  { value: 'notification', label: 'Application/Notification' },
  { value: 'questionnaire', label: 'Questionnaire' },
  { value: 'determination', label: 'Determination' },
  { value: 'nocc', label: 'NOCC' },
  { value: 'other', label: 'Other' },
];

const isPhase2ReferralTitle = (text) => {
  const lower = text.toLowerCase();
  return (
    lower.includes('subject to phase 2 review') ||
    lower.includes('proceed to a phase 2') ||
    lower.includes('proceed to phase 2')
  );
};

// Maps an event to one of the high-level categories used by the type filter.
// Order matters: notification > NOCC > questionnaire > determination > other.
const getEventCategory = (event) => {
  const title = (event.title || '').toLowerCase();
  const display = (event.display_title || '').toLowerCase();
  const combined = `${title} ${display}`;

  if (title.includes('notified')) return 'notification';
  if (combined.includes('notice of competition concerns')) return 'nocc';
  if (combined.includes('questionnaire')) return 'questionnaire';
  if (
    combined.includes('determination') ||
    isPhase2ReferralTitle(combined)
  ) {
    return 'determination';
  }
  return 'other';
};

function Timeline() {
  const [searchParams, setSearchParams] = useSearchParams();
  const typesParam = searchParams.get('types') || '';
  const selectedTypes = useMemo(
    () => (typesParam ? typesParam.split(',').filter(Boolean) : []),
    [typesParam]
  );

  const toggleType = (value) => {
    const next = selectedTypes.includes(value)
      ? selectedTypes.filter((t) => t !== value)
      : [...selectedTypes, value];
    const params = new URLSearchParams(searchParams);
    if (next.length === 0) params.delete('types');
    else params.set('types', next.join(','));
    setSearchParams(params);
  };

  const clearFilters = () => {
    const params = new URLSearchParams(searchParams);
    params.delete('types');
    setSearchParams(params);
  };

  const { data: meta, error: metaError } = useFetchData(
    API_ENDPOINTS.timelineMeta,
    { cacheKey: 'timeline-meta' }
  );
  const totalPages = meta?.total_pages ?? null;
  const lastPage = totalPages;

  // Events are stored date-ascending (oldest first). We fetch the last page
  // first — the hook handles caching the raw response — then reverse below.
  const { data: lastPageData, error: pageError } = useFetchData(
    lastPage ? API_ENDPOINTS.timelinePage(lastPage) : null,
    { cacheKey: lastPage ? `timeline-page-${lastPage}-raw` : undefined }
  );

  const [allEvents, setAllEvents] = useState([]);
  const [displayedEvents, setDisplayedEvents] = useState([]);
  const [hasMore, setHasMore] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [loadingMore, setLoadingMore] = useState(false);
  const [initialLoaded, setInitialLoaded] = useState(false);
  const loadingMoreRef = useRef(false);

  // Initialize display state once the last page's events arrive.
  useEffect(() => {
    if (!lastPageData || !lastPage) return;
    const events = [...lastPageData.events].reverse();
    setAllEvents(events);
    setDisplayedEvents(events.slice(0, ITEMS_PER_PAGE));
    setHasMore(events.length > ITEMS_PER_PAGE || lastPage > 1);
    setCurrentPage(lastPage);
    setInitialLoaded(true);
  }, [lastPageData, lastPage]);

  const error = metaError || pageError;
  // Show the spinner until the initial events are processed (or an error occurs).
  const loading = !error && !initialLoaded;

  const matchesFilters = (event) => {
    if (selectedTypes.length === 0) return true;
    return selectedTypes.includes(getEventCategory(event));
  };

  const filteredDisplayedEvents = useMemo(
    () => displayedEvents.filter(matchesFilters),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [displayedEvents, typesParam]
  );

  const filteredAllEvents = useMemo(
    () => allEvents.filter(matchesFilters),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [allEvents, typesParam]
  );

  const filtersActive = selectedTypes.length > 0;

  // Auto-load more pages while:
  //   - the initial page has too few events to scroll, OR
  //   - active filters have thinned the displayed list below the threshold
  //     while more pages remain to fetch.
  // Depends on displayedEvents.length (not just filtered length) so it
  // re-fires after each load even when none of the new events matched the
  // filter — otherwise a sparse filter would stall after one fetch.
  useEffect(() => {
    if (!initialLoaded || loadingMore || !hasMore) return;
    if (filteredDisplayedEvents.length < MIN_DISPLAYED_TO_ENABLE_SCROLL) {
      loadMoreEvents();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialLoaded, filteredDisplayedEvents.length, displayedEvents.length, hasMore, loadingMore]);

  useEffect(() => {
    const handleScroll = () => {
      const scrollPosition = window.innerHeight + window.scrollY;
      const threshold = document.documentElement.scrollHeight - SCROLL_THRESHOLD_PX;

      if (scrollPosition >= threshold && hasMore && !loadingMore) {
        loadMoreEvents();
      }
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasMore, loadingMore, displayedEvents.length, allEvents.length, currentPage, totalPages]);

  const loadMoreEvents = async () => {
    if (loadingMoreRef.current || !hasMore) return;

    loadingMoreRef.current = true;
    setLoadingMore(true);

    try {
      const currentLength = displayedEvents.length;

      // Check if we have more events in the current loaded data
      if (currentLength < allEvents.length) {
        const nextBatch = allEvents.slice(currentLength, currentLength + LOAD_MORE_COUNT);
        setDisplayedEvents(prev => [...prev, ...nextBatch]);
        setHasMore(currentLength + nextBatch.length < allEvents.length || (totalPages && currentPage > 1));
      } else if (totalPages && currentPage > 1) {
        // Events stored ascending: page before current has older events
        const prevPage = currentPage - 1;
        const cachedPage = dataCache.get(`timeline-page-${prevPage}`);

        let pageEvents;
        if (cachedPage) {
          pageEvents = cachedPage;
        } else {
          const response = await fetch(API_ENDPOINTS.timelinePage(prevPage));
          if (!response.ok) {
            setHasMore(false);
            setLoadingMore(false);
            return;
          }
          const data = await response.json();
          // Reverse each page so events append oldest-to-newest as user scrolls down
          pageEvents = [...data.events].reverse();
          dataCache.set(`timeline-page-${prevPage}`, pageEvents);
        }

        setAllEvents(prev => [...prev, ...pageEvents]);
        const nextBatch = pageEvents.slice(0, LOAD_MORE_COUNT);
        setDisplayedEvents(prev => [...prev, ...nextBatch]);
        setCurrentPage(prevPage);
        setHasMore(nextBatch.length < pageEvents.length || prevPage > 1);
      } else {
        setHasMore(false);
      }
    } catch (err) {
      console.error('Failed to load more events:', err);
      setHasMore(false);
    } finally {
      loadingMoreRef.current = false;
      setLoadingMore(false);
    }
  };

  const getEventType = (title, displayTitle) => {
    if (title.includes('notified')) return 'notification';
    if (displayTitle.includes('determination:') || isPhase2ReferralTitle(displayTitle)) {
      const fullText = (displayTitle || title).toLowerCase();
      if (fullText.includes('not approved') || fullText.includes('declined') || fullText.includes('not opposed')) {
        return 'determination-not-approved';
      }
      if (isPhase2ReferralTitle(fullText)) {
        return 'determination-referred';
      }
      return 'determination-approved';
    }
    return 'event';
  };

  const getEventColor = (eventType) => {
    switch (eventType) {
      case 'notification': return 'bg-blue-500';
      case 'determination-approved': return 'bg-emerald-500';
      case 'determination-not-approved': return 'bg-red-500';
      case 'determination-referred': return 'bg-amber-500';
      default: return 'bg-primary';
    }
  };

  const getEventIcon = (eventType) => {
    switch (eventType) {
      case 'notification':
        return <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v2H7a1 1 0 100 2h2v2a1 1 0 102 0v-2h2a1 1 0 100-2h-2V7z" clipRule="evenodd" />;
      case 'determination-approved':
        return <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />;
      case 'determination-not-approved':
        return <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />;
      case 'determination-referred':
        return <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />;
      default:
        return <path fillRule="evenodd" d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z" clipRule="evenodd" />;
    }
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;

  return (
    <>
      <SEO
        title="Timeline"
        description="Chronological feed of every ACCC merger event — notifications, Phase 2 launches, public consultation windows, and final determinations in date order."
        url="/timeline"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <div className="mb-6 pl-14 flex flex-wrap items-center gap-2" role="group" aria-label="Filter by event type">
          {EVENT_TYPE_OPTIONS.map((opt) => {
            const active = selectedTypes.includes(opt.value);
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => toggleType(opt.value)}
                aria-pressed={active}
                className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                  active
                    ? 'bg-primary text-white border-primary'
                    : 'bg-transparent text-gray-500 border-gray-200 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {opt.label}
              </button>
            );
          })}
          {filtersActive && (
            <button
              onClick={clearFilters}
              className="text-xs text-gray-400 hover:text-gray-600 transition-colors ml-1"
            >
              Clear
            </button>
          )}
        </div>

        <div className="flow-root">
          <ul className="-mb-8">
            {filteredDisplayedEvents.map((event, idx) => {
              const eventType = getEventType(event.title || '', event.display_title || '');

              return (
                <li key={`${event.merger_id}-${event.date}-${idx}`}>
                  <div className="relative pb-8">
                    {idx !== filteredDisplayedEvents.length - 1 && (
                      <span
                        className="absolute top-0 bottom-0 left-5 -ml-px w-0.5 bg-gray-100"
                        aria-hidden="true"
                      />
                    )}
                    <div className="relative flex space-x-4 items-center">
                      <div className="flex-shrink-0">
                        <span
                          className={`h-10 w-10 rounded-xl flex items-center justify-center shadow-sm ${getEventColor(eventType)}`}
                        >
                          <svg className="h-5 w-5 text-white" fill="currentColor" viewBox="0 0 20 20" role="img" aria-label="Timeline event">
                            {getEventIcon(eventType)}
                          </svg>
                        </span>
                      </div>
                      <Link
                        to={`/mergers/${event.merger_id}`}
                        className="min-w-0 flex-1 bg-white rounded-2xl border border-gray-100 shadow-card p-4 hover:shadow-card-hover hover:border-gray-200 transition-all duration-200 block"
                        aria-label={`View merger details for ${event.merger_name}`}
                      >
                        <span className="text-sm font-semibold text-gray-900">
                          {event.merger_name}
                        </span>
                        <p className="text-sm text-gray-500 mt-1">
                          {event.display_title || event.title}
                        </p>
                        <p className="mt-1 text-xs text-gray-400">
                          {formatDate(event.date)}
                        </p>
                        {event.url_gh && (
                          <div className="mt-2">
                            <a
                              href={event.url_gh}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-xs text-primary hover:text-primary-dark transition-colors relative z-10"
                              aria-label={`View document for ${event.merger_name}`}
                              onClick={(e) => e.stopPropagation()}
                            >
                              View document
                              <ExternalLinkIcon className="h-3 w-3" />
                            </a>
                          </div>
                        )}
                      </Link>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>

        {hasMore && (
          <div className="text-center py-8">
            <p className="text-sm text-gray-400">
              {filtersActive
                ? `Showing ${filteredDisplayedEvents.length} of ${filteredAllEvents.length} matching events (${displayedEvents.length} of ${allEvents.length} loaded)`
                : `Showing ${displayedEvents.length} of ${allEvents.length} events`}
            </p>
            {loadingMore ? (
              <p className="text-xs text-gray-400 mt-1">Loading more...</p>
            ) : (
              <p className="text-xs text-gray-400 mt-1">Scroll down to load more</p>
            )}
          </div>
        )}

        {!hasMore && displayedEvents.length > 0 && (
          <div className="text-center py-8">
            <p className="text-gray-400 text-sm">
              {filtersActive
                ? `Showing all ${filteredAllEvents.length} matching events (of ${allEvents.length} total)`
                : `Showing all ${allEvents.length} events`}
            </p>
          </div>
        )}

        {!loading && filteredDisplayedEvents.length === 0 && !hasMore && (
          <div className="text-center py-16">
            <p className="text-gray-500">
              {filtersActive
                ? 'No events match the selected filters'
                : 'No timeline data available'}
            </p>
            {filtersActive && (
              <button
                onClick={clearFilters}
                className="mt-3 text-sm text-primary hover:text-primary-dark transition-colors"
              >
                Clear filters
              </button>
            )}
          </div>
        )}
      </div>
    </>
  );
}

export default Timeline;
