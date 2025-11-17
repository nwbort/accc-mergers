import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import { formatDate } from '../utils/dates';
import { API_ENDPOINTS } from '../config';

function Timeline() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchTimeline();
  }, []);

  const fetchTimeline = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.mergers);
      if (!response.ok) throw new Error('Failed to fetch timeline');
      const data = await response.json();

      // Flatten all events from all mergers
      const allEvents = [];
      data.mergers.forEach((merger) => {
        if (merger.events && merger.events.length > 0) {
          merger.events.forEach((event) => {
            allEvents.push({
              ...event,
              merger_id: merger.merger_id,
              merger_name: merger.merger_name,
            });
          });
        }
      });

      // Sort by date (most recent first)
      allEvents.sort((a, b) => new Date(b.date) - new Date(a.date));

      setEvents(allEvents);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getEventType = (title) => {
    if (title.includes('notified')) return 'notification';
    if (title.includes('Determination published')) return 'determination';
    return 'event';
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600">Error: {error}</div>;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Timeline</h1>
        <p className="mt-2 text-sm text-gray-600">
          Chronological view of all events across all merger reviews
        </p>
      </div>

      <div className="flow-root">
        <ul className="-mb-8">
          {events.map((event, idx) => {
            const eventType = getEventType(event.title);

            return (
              <li key={`${event.merger_id}-${event.date}-${idx}`}>
                <div className="relative pb-8">
                  {idx !== events.length - 1 && (
                    <span
                      className="absolute top-5 left-5 -ml-px h-full w-0.5 bg-gray-200"
                      aria-hidden="true"
                    />
                  )}
                  <div className="relative flex space-x-4 items-start">
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
                          {event.title}
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
                            View archived document →
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

      {events.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500">No timeline data available</p>
        </div>
      )}
    </div>
  );
}

export default Timeline;
