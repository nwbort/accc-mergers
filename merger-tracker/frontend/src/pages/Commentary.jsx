import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import LoadingSpinner from '../components/LoadingSpinner';
import StatusBadge from '../components/StatusBadge';
import WaiverBadge from '../components/WaiverBadge';
import ExternalLinkIcon from '../components/ExternalLinkIcon';
import SEO from '../components/SEO';
import { formatDate } from '../utils/dates';
import { API_ENDPOINTS } from '../config';
import { dataCache } from '../utils/dataCache';
import { PROSE_MARKDOWN } from '../utils/classNames';

function Commentary() {
  const [items, setItems] = useState(() => dataCache.get('commentary-items') || []);
  const [loading, setLoading] = useState(() => !dataCache.has('commentary-items'));
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchCommentary();
  }, []);

  const fetchCommentary = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.commentary);
      if (!response.ok) throw new Error('Failed to fetch commentary');
      const data = await response.json();
      dataCache.set('commentary-items', data.items);
      setItems(data.items);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;

  return (
    <>
      <SEO
        title="Commentary"
        description="Analysis and commentary on Australian mergers and acquisitions reviewed by the ACCC."
        url="/commentary"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        {/* Results count */}
        <div className="mb-4">
          <p className="text-sm text-gray-400">
            {items.length} {items.length === 1 ? 'entry' : 'entries'}
          </p>
        </div>

        {/* Commentary List */}
        <div className="space-y-4">
          {items.map((item) => (
            <div
              key={item.merger_id}
              className="bg-white rounded-2xl border border-gray-100 shadow-card overflow-hidden"
            >
              {/* Header */}
              <div className="p-5 border-b border-gray-50">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <Link
                        to={`/mergers/${item.merger_id}`}
                        className="text-base font-semibold text-gray-900 hover:text-primary transition-colors truncate"
                      >
                        {item.merger_name}
                      </Link>
                      {item.is_waiver && <WaiverBadge className="flex-shrink-0" />}
                    </div>
                    <p className="text-xs text-gray-400 mt-1">
                      {item.merger_id} · {item.stage || 'N/A'} · {item.is_waiver ? 'Applied' : 'Notified'}: {formatDate(item.effective_notification_datetime)}
                      {item.determination_publication_date && (
                        <>
                          {' · '}
                          {item.determination_url ? (
                            <a
                              href={item.determination_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-primary hover:text-primary-dark transition-colors"
                              aria-label="View determination document"
                            >
                              Determined: {formatDate(item.determination_publication_date)}
                              <ExternalLinkIcon className="h-3 w-3" />
                            </a>
                          ) : (
                            `Determined: ${formatDate(item.determination_publication_date)}`
                          )}
                        </>
                      )}
                    </p>
                  </div>
                  <StatusBadge
                    status={item.status}
                    determination={item.accc_determination}
                  />
                </div>
              </div>

              {/* Comments */}
              {item.comments && item.comments.length > 0 && (
                <div className="divide-y divide-blue-100/60">
                  {item.comments.map((comment, commentIdx) => (
                    <div key={commentIdx} className="p-5 bg-gradient-to-r from-blue-50/80 to-indigo-50/30">
                      <div className="flex items-start gap-3">
                        <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
                          <svg className="h-4 w-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                          </svg>
                        </div>
                        <div className="flex-1 min-w-0">
                          {comment.commentary && (
                            <div className={PROSE_MARKDOWN}>
                              <ReactMarkdown>{comment.commentary}</ReactMarkdown>
                            </div>
                          )}
                          {comment.tags && comment.tags.length > 0 && (
                            <div className="flex flex-wrap gap-1.5 mt-3">
                              {comment.tags.map((tag, tagIdx) => (
                                <span
                                  key={`tag-${tag}-${tagIdx}`}
                                  className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-blue-100/80 text-blue-700"
                                >
                                  {tag}
                                </span>
                              ))}
                            </div>
                          )}
                          <div className="flex items-center gap-3 mt-3">
                            {comment.date && (
                              <p className="text-xs text-gray-400">
                                Updated {formatDate(comment.date)}
                              </p>
                            )}
                            {comment.author && (
                              <p className="text-xs text-gray-400">
                                by {comment.author}
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {items.length === 0 && (
          <div className="text-center py-16">
            <p className="text-gray-500 font-medium">No commentary available yet</p>
          </div>
        )}
      </div>
    </>
  );
}

export default Commentary;
