import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import SEO from '../components/SEO';
import { formatDate } from '../utils/dates';
import { API_ENDPOINTS } from '../config';

const ITEMS_PER_PAGE = 15;
const LOAD_MORE_COUNT = 10;

function Timeline() {
  const [allEvents, setAllEvents] = useState([]);
  const [displayedEvents, setDisplayedEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);
  const [hasMore, setHasMore] = useState(true);

  useEffect(() => {
    fetchTimeline();
  }, []);

  useEffect(() => {
    const handleScroll = () => {
      // Check if user is near bottom (within 300px)
      const scrollPosition = window.innerHeight + window.scrollY;
      const threshold = document.documentElement.scrollHeight - 300;

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

      setAllEvents(data.events);
      // Show initial batch
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

  const getEventType = (title) => {
    if (title.includes('notified')) return 'notification';
    if (title.includes('determination:')) return 'determination';
    return 'event';
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600">Error: {error}</div>;

  return (
    <>
      <SEO
        title="Timeline"
        description="Chronological timeline of all Australian merger and acquisition events, determinations, and public consultations monitored by the ACCC."
        url="/timeline"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Timeline</h1>
          <p className="mt-2 text-gray-600">
            All events across merger reviews ({allEvents.length} total)
          </p>
        </div>

        <div className="flow-root">
          <ul className="-mb-8">
            {displayedEvents.map((event, idx) => {
              const eventType = getEventType(event.title || '');

              return (
                <li key={`${event.merger_id}-${event.date}-${idx}`}>
                  <div className="relative pb-8">
                    {idx !== displayedEvents.length - 1 && (
                      <span
                        className="absolute top-5 left-5 -ml-px h-full w-0.5 bg-gray-200"
                        aria-hidden="true"
                      />
                    )}
                    <div className="relative flex space-x-4 items-center">
                      <div className="flex-shrink-0">
                        <span
                          className={`h-10 w-10 rounded-full flex items-center justify-center ring-8 ring-white ${
                            eventType === 'notification'
                              ? 'bg-blue-500'
                              : eventType === 'determination'
                              ? 'bg-green-500'
                              : 'bg-primary'
                          }`}
                        >
                          {eventType === 'notification' ? (
                            <svg
                              className="h-5 w-5 text-white"
                              fill="currentColor"
                              viewBox="0 0 20 20"
                            >
                              <path
                                fillRule="evenodd"
                                d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v2H7a1 1 0 100 2h2v2a1 1 0 102 0v-2h2a1 1 0 100-2h-2V7z"
                                clipRule="evenodd"
                              />
                            </svg>
                          ) : eventType === 'determination' ? (
                            <svg
                              className="h-5 w-5 text-white"
                              fill="currentColor"
                              viewBox="0 0 20 20"
                            >
                              <path
                                fillRule="evenodd"
                                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                clipRule="evenodd"
                              />
                            </svg>
                          ) : (
                            <svg
                              className="h-5 w-5 text-white"
                              fill="currentColor"
                              viewBox="0 0 20 20"
                            >
                              <path
                                fillRule="evenodd"
                                d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z"
                                clipRule="evenodd"
                              />
                            </svg>
                          )}
                        </span>
                      </div>
                      <div className="min-w-0 flex-1 bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow duration-200">
                        <div>
                          <Link
                            to={`/mergers/${event.merger_id}`}
                            className="text-sm font-medium text-gray-900 hover:text-primary-dark"
                          >
                            {event.merger_name}
                          </Link>
                          <p className="text-sm text-gray-600 mt-1">
                            {event.display_title || event.title}
                          </p>
                          <p className="mt-1 text-sm text-gray-500">
                            {formatDate(event.date)}
                          </p>
                        </div>
                        {event.url && event.status !== 'removed' && (
                          <div className="mt-2">
                            <a
                              href={event.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-primary hover:text-primary-dark"
                            >
                              View document on ACCC website →
                            </a>
                          </div>
                        )}
                        {event.url_gh && (
                          <div className="mt-1">
                            <a
                              href={event.url_gh}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-gray-600 hover:text-gray-900"
                            >
                              View document →
                            </a>
                          </div>
                        )}
                        {event.status === 'removed' && (
                          <span className="mt-1 text-xs text-gray-500 italic">
                            (document removed from ACCC website)
                          </span>
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
            <p className="text-sm text-gray-600">
              Showing {displayedEvents.length} of {allEvents.length} events
            </p>
            {loadingMore ? (
              <p className="text-xs text-gray-500 mt-1">Loading more...</p>
            ) : (
              <p className="text-xs text-gray-500 mt-1">Scroll down to load more</p>
            )}
          </div>
        )}

        {!hasMore && displayedEvents.length > 0 && (
          <div className="text-center py-8">
            <p className="text-gray-500 text-sm">
              Showing all {allEvents.length} events
            </p>
          </div>
        )}

        {!loading && displayedEvents.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-500">No timeline data available</p>
          </div>
        )}
      </div>
    </>
  );
}

export default Timeline;
