import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import StatusBadge from '../components/StatusBadge';
import { formatDate } from '../utils/dates';
import { API_ENDPOINTS } from '../config';

function Timeline() {
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchTimeline();
  }, []);

  const fetchTimeline = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.timeline);
      if (!response.ok) throw new Error('Failed to fetch timeline');
      const data = await response.json();
      setTimeline(data.timeline);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600">Error: {error}</div>;

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Timeline</h1>
        <p className="mt-2 text-sm text-gray-600">
          Chronological view of all merger reviews and their progress
        </p>
      </div>

      <div className="flow-root">
        <ul className="-mb-8">
          {timeline.map((merger, idx) => (
            <li key={merger.merger_id}>
              <div className="relative pb-8">
                {idx !== timeline.length - 1 && (
                  <span
                    className="absolute top-5 left-5 -ml-px h-full w-0.5 bg-gray-200"
                    aria-hidden="true"
                  />
                )}
                <div className="relative">
                  <div className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow duration-200">
                    <div className="p-6">
                      <div className="flex items-start space-x-4">
                        {/* Timeline dot */}
                        <div className="flex-shrink-0">
                          <div className="h-10 w-10 rounded-full bg-primary flex items-center justify-center ring-8 ring-white">
                            <svg
                              className="h-6 w-6 text-white"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                              />
                            </svg>
                          </div>
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between">
                            <Link
                              to={`/mergers/${merger.merger_id}`}
                              className="group"
                            >
                              <h3 className="text-lg font-semibold text-gray-900 group-hover:text-primary">
                                {merger.merger_name}
                              </h3>
                              <p className="text-sm text-gray-500 mt-1">
                                {merger.merger_id} • {merger.stage || 'N/A'}
                              </p>
                            </Link>
                            <StatusBadge
                              status={merger.status}
                              determination={merger.accc_determination}
                            />
                          </div>

                          {/* Key dates */}
                          <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
                            <div>
                              <p className="text-xs text-gray-500">
                                Notified
                              </p>
                              <p className="text-sm font-medium text-gray-900">
                                {formatDate(
                                  merger.effective_notification_datetime
                                )}
                              </p>
                            </div>
                            {merger.end_of_determination_period && (
                              <div>
                                <p className="text-xs text-gray-500">
                                  Determination Due
                                </p>
                                <p className="text-sm font-medium text-gray-900">
                                  {formatDate(
                                    merger.end_of_determination_period
                                  )}
                                </p>
                              </div>
                            )}
                            {merger.determination_publication_date && (
                              <div>
                                <p className="text-xs text-gray-500">
                                  Determined
                                </p>
                                <p className="text-sm font-medium text-gray-900">
                                  {formatDate(
                                    merger.determination_publication_date
                                  )}
                                </p>
                              </div>
                            )}
                          </div>

                          {/* Key events */}
                          {merger.key_events &&
                            merger.key_events.length > 0 && (
                              <div className="mt-4">
                                <p className="text-xs text-gray-500 mb-2">
                                  Recent Events
                                </p>
                                <div className="space-y-1">
                                  {merger.key_events
                                    .slice(-3)
                                    .reverse()
                                    .map((event, eventIdx) => (
                                      <div
                                        key={eventIdx}
                                        className="flex items-center text-sm"
                                      >
                                        <span className="text-gray-400 mr-2">
                                          •
                                        </span>
                                        <span className="text-gray-700">
                                          {event.title}
                                        </span>
                                        <span className="text-gray-400 ml-2">
                                          ({formatDate(event.date)})
                                        </span>
                                      </div>
                                    ))}
                                </div>
                              </div>
                            )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {timeline.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500">No merger data available</p>
        </div>
      )}
    </div>
  );
}

export default Timeline;
