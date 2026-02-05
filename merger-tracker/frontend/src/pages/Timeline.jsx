import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import SEO from '../components/SEO';
import ExternalLinkIcon from '../components/ExternalLinkIcon';
import { formatDate } from '../utils/dates';
import { API_ENDPOINTS } from '../config';
import { dataCache } from '../utils/dataCache';

const ITEMS_PER_PAGE = 15;
const LOAD_MORE_COUNT = 10;
const SCROLL_THRESHOLD_PX = 300;

function Timeline() {
  const navigate = useNavigate();
  const cachedEvents = dataCache.get('timeline-events');
  const [allEvents, setAllEvents] = useState(() => cachedEvents || []);
  const [displayedEvents, setDisplayedEvents] = useState(() =>
    cachedEvents ? cachedEvents.slice(0, ITEMS_PER_PAGE) : []
  );
  const [loading, setLoading] = useState(() => !cachedEvents);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);
  const [hasMore, setHasMore] = useState(() =>
    cachedEvents ? cachedEvents.length > ITEMS_PER_PAGE : true
  );

  useEffect(() => {
    fetchTimeline();
  }, []);

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
  }, [hasMore, loadingMore, displayedEvents.length, allEvents.length]);

  const fetchTimeline = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.timeline);
      if (!response.ok) throw new Error('Failed to fetch timeline');
      const data = await response.json();

      dataCache.set('timeline-events', data.events);
      setAllEvents(data.events);
      setDisplayedEvents(data.events.slice(0, ITEMS_PER_PAGE));
      setHasMore(data.events.length > ITEMS_PER_PAGE);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadMoreEvents = () => {
    if (loadingMore || !hasMore) return;

    setLoadingMore(true);

    const currentLength = displayedEvents.length;
    const nextBatch = allEvents.slice(currentLength, currentLength + LOAD_MORE_COUNT);

    if (nextBatch.length > 0) {
      setDisplayedEvents(prev => [...prev, ...nextBatch]);
      setHasMore(currentLength + nextBatch.length < allEvents.length);
    } else {
      setHasMore(false);
    }

    setLoadingMore(false);
  };

  const getEventType = (title, displayTitle) => {
    if (title.includes('notified')) return 'notification';
    if (displayTitle.includes('determination:') || displayTitle.includes('subject to Phase 2 review')) {
      const fullText = (displayTitle || title).toLowerCase();
      if (fullText.includes('not approved') || fullText.includes('declined') || fullText.includes('not opposed')) {
        return 'determination-not-approved';
      }
      if (fullText.includes('subject to phase 2 review')) {
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
        description="Chronological timeline of all Australian merger and acquisition events, determinations, and public consultations monitored by the ACCC."
        url="/timeline"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <div className="flow-root">
          <ul className="-mb-8">
            {displayedEvents.map((event, idx) => {
              const eventType = getEventType(event.title || '', event.display_title || '');

              return (
                <li key={`${event.merger_id}-${event.date}-${idx}`}>
                  <div className="relative pb-8">
                    {idx !== displayedEvents.length - 1 && (
                      <span
                        className="absolute top-5 left-5 -ml-px h-full w-0.5 bg-gray-100"
                        aria-hidden="true"
                      />
                    )}
                    <div className="relative flex space-x-4 items-start">
                      <div className="flex-shrink-0 pt-0.5">
                        <span
                          className={`h-10 w-10 rounded-xl flex items-center justify-center shadow-sm ${getEventColor(eventType)}`}
                        >
                          <svg className="h-5 w-5 text-white" fill="currentColor" viewBox="0 0 20 20" role="img" aria-label="Timeline event">
                            {getEventIcon(eventType)}
                          </svg>
                        </span>
                      </div>
                      <div
                        className="min-w-0 flex-1 bg-white rounded-2xl border border-gray-100 shadow-card p-4 hover:shadow-card-hover hover:border-gray-200 transition-all duration-200 cursor-pointer"
                        onClick={() => navigate(`/mergers/${event.merger_id}`)}
                        role="link"
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
                              className="inline-flex items-center gap-1 text-xs text-primary hover:text-primary-dark transition-colors"
                              aria-label={`View document for ${event.merger_name}`}
                              onClick={(e) => e.stopPropagation()}
                            >
                              View document
                              <ExternalLinkIcon className="h-3 w-3" />
                            </a>
                          </div>
                        )}
                      </div>
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
              Showing {displayedEvents.length} of {allEvents.length} events
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
              Showing all {allEvents.length} events
            </p>
          </div>
        )}

        {!loading && displayedEvents.length === 0 && (
          <div className="text-center py-16">
            <p className="text-gray-500">No timeline data available</p>
          </div>
        )}
      </div>
    </>
  );
}

export default Timeline;
