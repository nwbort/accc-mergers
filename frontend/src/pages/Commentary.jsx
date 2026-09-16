import { Link } from 'react-router';
import { mergerPath } from '../utils/slug';
import { FaComment } from 'react-icons/fa';
import ReactMarkdown from 'react-markdown';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import StatusBadge from '../components/StatusBadge';
import WaiverBadge from '../components/WaiverBadge';
import AppealBadge from '../components/AppealBadge';
import ExternalLinkIcon from '../components/ExternalLinkIcon';
import SEO from '../components/SEO';
import { formatDate } from '../utils/dates';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { getOutcomeRail } from '../constants/outcomeRail';
import { PROSE_MARKDOWN, CARD } from '../utils/classNames';
import { STATIC_PAGE_META } from '../utils/pageMeta';

// Title and description live in the shared table so this page and the
// build-time prerenderer emit the same <head>.
const PAGE_META = STATIC_PAGE_META['/commentary'];

function Commentary() {
  const { data, loading, error } = useFetchData(API_ENDPOINTS.commentary, {
    cacheKey: 'commentary-items',
  });
  const items = data?.items || [];

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;

  return (
    <>
      <SEO
        title={PAGE_META.title}
        description={PAGE_META.description}
        url="/commentary"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        {/* The page leads straight into content, so the document's h1 is
            visually hidden rather than dropped: it names the page for screen
            readers and keeps the heading outline starting at level 1. */}
        <h1 className="sr-only">Commentary</h1>

        {/* Results count */}
        <div className="mb-4">
          <p className="text-sm text-gray-500">
            {items.length} {items.length === 1 ? 'entry' : 'entries'}
          </p>
        </div>

        {/* Commentary List */}
        <div className="space-y-4">
          {items.map((item) => {
            // Mirrors the merger list card (Mergers.jsx): a solid outcome
            // badge leading the title, with a colour-matched rail down the
            // left edge, rather than the tinted status chip this page used
            // to show in the top-right corner.
            const railColor = getOutcomeRail({
              status: item.status,
              determination: item.accc_determination,
              appeal: item.appeal,
            });
            return (
              <div
                key={item.merger_id}
                className={`relative overflow-hidden ${CARD}`}
              >
                <span
                  className={`absolute inset-y-0 left-0 w-1.5 ${railColor}`}
                  aria-hidden="true"
                />
                {/* Header */}
                <div className="p-5 pl-6 border-b border-gray-50">
                  <div className="flex flex-wrap items-center gap-1.5 mb-2">
                    <StatusBadge
                      status={item.status}
                      determination={item.accc_determination}
                      appeal={item.appeal}
                      solid
                    />
                    {item.under_appeal && <AppealBadge solid />}
                    {item.is_waiver && <WaiverBadge solid />}
                  </div>
                  <Link
                    to={mergerPath(item.merger_id, item.merger_name)}
                    className="block text-base font-semibold text-gray-900 hover:text-primary transition-colors truncate"
                  >
                    {item.merger_name}
                  </Link>
                  <p className="text-xs text-gray-500 mt-1">
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

                {/* Comments */}
                {item.comments && item.comments.length > 0 && (
                  <div className="divide-y divide-blue-100/60">
                    {item.comments.map((comment, commentIdx) => (
                      <div key={commentIdx} className="p-5 bg-gradient-to-r from-blue-50/80 to-indigo-50/30">
                        <div className="flex items-start gap-3">
                          <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
                            <FaComment className="h-4 w-4 text-blue-600" aria-hidden="true" />
                          </div>
                          <div className="flex-1 min-w-0">
                            {comment.commentary && (
                              <div className={PROSE_MARKDOWN} role="article" aria-label={`Commentary on ${item.merger_name}`}>
                                <ReactMarkdown>{comment.commentary}</ReactMarkdown>
                              </div>
                            )}
                            {comment.tags && comment.tags.length > 0 && (
                              <div className="flex flex-wrap gap-1.5 mt-3">
                                {comment.tags.map((tag, tagIdx) => (
                                  <span
                                    key={`tag-${tag}-${tagIdx}`}
                                    className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium leading-none bg-blue-100/80 text-blue-700"
                                  >
                                    {tag}
                                  </span>
                                ))}
                              </div>
                            )}
                            <div className="flex items-center gap-3 mt-3">
                              {comment.date && (
                                <p className="text-xs text-gray-500">
                                  Updated {formatDate(comment.date)}
                                </p>
                              )}
                              {comment.author && (
                                <p className="text-xs text-gray-500">
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
            );
          })}
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
