import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import LoadingSpinner from '../components/LoadingSpinner';
import StatusBadge from '../components/StatusBadge';
import SEO from '../components/SEO';
import { formatDate } from '../utils/dates';
import { API_ENDPOINTS } from '../config';

function Commentary() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchCommentary();
  }, []);

  const fetchCommentary = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.commentary);
      if (!response.ok) throw new Error('Failed to fetch commentary');
      const data = await response.json();
      setItems(data.items);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600">Error: {error}</div>;

  return (
    <>
      <SEO
        title="Commentary"
        description="Analysis and commentary on Australian mergers and acquisitions reviewed by the ACCC."
        url="/commentary"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Commentary</h1>
          <p className="mt-2 text-gray-600">
            Analysis and notes on mergers reviewed by the ACCC.
          </p>
        </div>

        {/* Results count */}
        <div className="mb-4">
          <p className="text-sm text-gray-600">
            {items.length} {items.length === 1 ? 'entry' : 'entries'}
          </p>
        </div>

        {/* Commentary List */}
        <div className="space-y-6">
          {items.map((item) => (
            <div
              key={item.merger_id}
              className="bg-white rounded-lg shadow"
            >
              {/* Header */}
              <div className="p-6 border-b border-gray-100">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <Link
                        to={`/mergers/${item.merger_id}`}
                        className="text-lg font-semibold text-gray-900 hover:text-primary"
                      >
                        {item.merger_name}
                      </Link>
                      {item.is_waiver && (
                        <span
                          className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800"
                          role="status"
                          aria-label="Merger type: Waiver application"
                        >
                          Waiver
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      {item.merger_id} • {item.stage || 'N/A'}
                    </p>
                  </div>
                  <StatusBadge
                    status={item.status}
                    determination={item.accc_determination}
                  />
                </div>

                <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <p className="text-xs text-gray-500">Acquirers</p>
                    <p className="text-sm font-medium text-gray-900">
                      {item.acquirers.map((a) => a.name).join(', ')}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Targets</p>
                    <p className="text-sm font-medium text-gray-900">
                      {item.targets.map((t) => t.name).join(', ')}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">
                      {item.is_waiver ? 'Application date' : 'Notification date'}
                    </p>
                    <p className="text-sm font-medium text-gray-900">
                      {formatDate(item.effective_notification_datetime)}
                    </p>
                  </div>
                </div>
              </div>

              {/* Commentary Content */}
              <div className="p-6 bg-blue-50 border-l-4 border-blue-400">
                <div className="flex items-start">
                  <div className="flex-shrink-0">
                    <svg className="h-6 w-6 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                    </svg>
                  </div>
                  <div className="ml-3 flex-1">
                    {item.commentary && (
                      <div className="text-gray-700 prose prose-sm max-w-none [&>p]:mb-4 [&>ul]:mb-4 [&>ul]:list-disc [&>ul]:pl-5 [&>ul>li]:mb-2 [&>ol]:mb-4 [&>ol]:list-decimal [&>ol]:pl-5 [&>ol>li]:mb-2">
                        <ReactMarkdown>{item.commentary}</ReactMarkdown>
                      </div>
                    )}
                    {item.tags && item.tags.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-3">
                        {item.tags.map((tag, idx) => (
                          <span
                            key={`tag-${tag}-${idx}`}
                            className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-800"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                    <div className="flex items-center gap-4 mt-3">
                      {item.last_updated && (
                        <p className="text-xs text-gray-500">
                          Last updated: {formatDate(item.last_updated)}
                        </p>
                      )}
                      {item.author && (
                        <p className="text-xs text-gray-500">
                          By: {item.author}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {items.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-500">No commentary available yet.</p>
          </div>
        )}
      </div>
    </>
  );
}

export default Commentary;
