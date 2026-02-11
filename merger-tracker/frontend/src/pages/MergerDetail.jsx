import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import LoadingSpinner from '../components/LoadingSpinner';
import StatusBadge from '../components/StatusBadge';
import SEO from '../components/SEO';
import ExternalLinkIcon from '../components/ExternalLinkIcon';
import { useTracking } from '../context/TrackingContext';
import { formatDate, calculateDuration, getDaysRemaining, calculateBusinessDays, getBusinessDaysRemaining } from '../utils/dates';
import { API_ENDPOINTS } from '../config';

function MergerDetail() {
  const { id } = useParams();
  const [merger, setMerger] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedParties, setExpandedParties] = useState({});
  const { isTracked, toggleTracking } = useTracking();
  const tracked = isTracked(id);
  const savedParams = sessionStorage.getItem('mergers_filter_params');
  const backToMergers = savedParams ? `/mergers?${savedParams}` : '/mergers';

  useEffect(() => {
    fetchMerger();
  }, [id]);

  const fetchMerger = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.mergerDetail(id));
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('not_found');
        }
        throw new Error('Failed to fetch merger details');
      }
      const data = await response.json();
      setMerger(data);
    } catch (err) {
      if (err.name === 'TypeError') {
        setError('not_found');
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const togglePartyExpand = (partyType) => {
    setExpandedParties(prev => ({
      ...prev,
      [partyType]: !prev[partyType]
    }));
  };

  const renderPartyList = (parties, partyType, title) => {
    const VISIBLE_COUNT = 2;
    const isExpanded = expandedParties[partyType];
    const hasMore = parties.length > VISIBLE_COUNT;
    const visibleParties = hasMore && !isExpanded ? parties.slice(0, VISIBLE_COUNT) : parties;
    const hiddenCount = parties.length - VISIBLE_COUNT;

    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6">
        <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">{title}</h2>
        {visibleParties.map((party, idx) => (
          <div key={`${partyType}-${party.name}-${party.identifier || idx}`} className="mb-3 last:mb-0">
            <p className="font-medium text-gray-900">{party.name}</p>
            {party.identifier && (
              <p className="text-sm text-gray-400">
                {party.identifier_type ? `${party.identifier_type}: ` : ''}{party.identifier}
              </p>
            )}
          </div>
        ))}
        {hasMore && (
          <button
            type="button"
            onClick={() => togglePartyExpand(partyType)}
            className="text-sm text-primary hover:text-primary-dark font-medium mt-2 transition-colors"
            aria-expanded={isExpanded}
          >
            {isExpanded ? 'Show less' : `Show ${hiddenCount} more`}
          </button>
        )}
      </div>
    );
  };

  if (loading) return <LoadingSpinner />;
  if (error) {
    return (
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-10 text-center">
          <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-gray-100 flex items-center justify-center">
            <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-gray-900 mb-3">
            {error === 'not_found' ? "Merger not found" : "Error loading merger"}
          </h1>
          <p className="text-gray-500 mb-6 max-w-md mx-auto">
            {error === 'not_found'
              ? `We couldn't find a merger with ID "${id}". It may have been removed or the ID might be incorrect.`
              : error
            }
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              to={backToMergers}
              className="inline-flex items-center px-5 py-2.5 text-sm font-medium rounded-xl text-white bg-primary hover:bg-primary-dark transition-colors shadow-sm"
              aria-label="Return to all mergers list"
            >
              ← Back to all mergers
            </Link>
            <span className="text-gray-400 text-sm">or</span>
            <a
              href={`https://www.accc.gov.au/public-registers/mergers-and-acquisitions-registers/acquisitions-register?init=1&query=${id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-5 py-2.5 text-sm font-medium rounded-xl text-gray-700 bg-white border border-gray-200 hover:bg-gray-50 transition-colors"
              aria-label={`Search for ${id} on ACCC website`}
            >
              Check ACCC website →
            </a>
          </div>
        </div>
      </div>
    );
  }
  if (!merger) return null;

  const duration = calculateDuration(
    merger.effective_notification_datetime,
    merger.determination_publication_date
  );

  const businessDuration = calculateBusinessDays(
    merger.effective_notification_datetime,
    merger.determination_publication_date
  );

  const daysRemaining = getDaysRemaining(merger.end_of_determination_period);
  const businessDaysRemaining = getBusinessDaysRemaining(merger.end_of_determination_period);

  const sortedEvents = merger.events
    ? [...merger.events].sort((a, b) => new Date(b.date) - new Date(a.date))
    : [];

  const determinationEvent = merger.determination_publication_date && merger.events
    ? merger.events.find(event =>
        event.date === merger.determination_publication_date &&
        event.title?.toLowerCase().includes('determination')
      )
    : null;

  const structuredData = {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": merger.merger_name,
    "description": merger.merger_description || `Merger between ${merger.acquirers.map(a => a.name).join(', ')} and ${merger.targets.map(t => t.name).join(', ')}`,
    "datePublished": merger.effective_notification_datetime,
    "author": {
      "@type": "Person",
      "name": "Nick Twort",
      "url": "https://mergers.fyi"
    },
    "about": {
      "@type": "MergerAcquisition",
      "name": merger.merger_name,
      "acquirer": merger.acquirers.map(a => ({
        "@type": "Organization",
        "name": a.name
      })),
      "target": merger.targets.map(t => ({
        "@type": "Organization",
        "name": t.name
      }))
    }
  };

  return (
    <>
      <SEO
        title={merger.merger_name}
        description={merger.merger_description || `ACCC merger review: ${merger.acquirers.map(a => a.name).join(', ')} acquiring ${merger.targets.map(t => t.name).join(', ')}. Status: ${merger.status}`}
        url={`/mergers/${merger.merger_id}`}
        structuredData={structuredData}
      />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        {/* Back button */}
        <Link
          to={backToMergers}
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-primary mb-5 transition-colors"
          aria-label="Return to all mergers list"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
          Back to all mergers
        </Link>

        {/* Header */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6 mb-6 card-accent">
          <div className="flex items-start justify-between gap-4 pt-1">
            <div className="min-w-0">
              <div className="flex items-center gap-3 mb-2 flex-wrap">
                <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
                  {merger.merger_name}
                </h1>
                {merger.is_waiver && (
                  <span
                    className="inline-flex items-center px-2.5 py-1 rounded-lg text-sm font-medium bg-amber-50 text-amber-700 border border-amber-200/60"
                    role="status"
                    aria-label="Merger type: Waiver application"
                  >
                    Waiver
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4 flex-wrap">
                <p className="text-sm text-gray-400">{merger.merger_id}</p>
                {merger.url && (
                  <a
                    href={merger.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-sm text-primary hover:text-primary-dark transition-colors"
                    aria-label={`View ${merger.merger_name} on ACCC website`}
                  >
                    View on ACCC website
                    <ExternalLinkIcon />
                  </a>
                )}
              </div>
            </div>
            <div className="flex flex-col items-end gap-2 flex-shrink-0">
              <StatusBadge
                status={merger.status}
                determination={merger.accc_determination}
              />
              <button
                onClick={() => toggleTracking(id)}
                className={`inline-flex items-center justify-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-lg border transition-all duration-200 ${
                  tracked
                    ? 'bg-primary text-white border-primary hover:bg-primary-dark shadow-sm'
                    : 'bg-gray-100 text-gray-600 border-gray-200/60 hover:bg-gray-200'
                }`}
                aria-pressed={tracked}
                aria-label={tracked ? 'Stop tracking this merger' : 'Track this merger for updates'}
              >
                {tracked ? (
                  <>
                    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
                    </svg>
                    Tracking
                  </>
                ) : (
                  <>
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
                    </svg>
                    Track
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Key Information Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6 pt-6 border-t border-gray-100">
            <div>
              <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1.5">Stage</h3>
              <p className="text-sm font-medium text-gray-900">{merger.stage || 'N/A'}</p>
            </div>
            <div>
              <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1.5">
                {merger.is_waiver ? 'Waiver Application Date' : 'Effective Notification'}
              </h3>
              <p className="text-sm font-medium text-gray-900">
                {formatDate(merger.effective_notification_datetime)}
              </p>
            </div>
            {!merger.is_waiver && (
              <div>
                <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1.5">
                  End of Determination Period
                </h3>
                <p className="text-sm font-medium text-gray-900">
                  {formatDate(merger.end_of_determination_period)}
                  {daysRemaining !== null && daysRemaining > 0 && !merger.determination_publication_date && (
                    <span className="ml-2 text-xs text-gray-400 font-normal">
                      ({daysRemaining} cal / {businessDaysRemaining} bus. days remaining)
                    </span>
                  )}
                </p>
              </div>
            )}
            {merger.determination_publication_date && (
              <div>
                <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1.5">
                  Determination Published
                </h3>
                <p className="text-sm font-medium text-gray-900">
                  {formatDate(merger.determination_publication_date)}
                  {duration !== null && businessDuration !== null && (
                    <span className="ml-2 text-xs text-gray-400 font-normal">
                      ({duration} cal / {businessDuration} bus. days)
                    </span>
                  )}
                </p>
              </div>
            )}
            {merger.accc_determination && (
              <div>
                <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1.5">
                  Determination
                </h3>
                <p className="text-sm font-medium text-gray-900">
                  {determinationEvent?.url_gh ? (
                    <a
                      href={determinationEvent.url_gh}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-primary hover:text-primary-dark transition-colors"
                      aria-label={`View determination document: ${merger.accc_determination}`}
                    >
                      {merger.accc_determination}
                      <ExternalLinkIcon />
                    </a>
                  ) : (
                    merger.accc_determination
                  )}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Parties */}
        <div className={`grid grid-cols-1 ${merger.other_parties && merger.other_parties.length > 0 ? 'md:grid-cols-3' : 'md:grid-cols-2'} gap-4 mb-6`}>
          {renderPartyList(merger.acquirers, 'acquirers', 'Acquirers')}
          {renderPartyList(merger.targets, 'targets', 'Targets')}
          {merger.other_parties && merger.other_parties.length > 0 &&
            renderPartyList(merger.other_parties, 'other_parties', 'Other parties')
          }
        </div>

        {/* Description */}
        {merger.merger_description && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6 mb-6">
            <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">
              Description
            </h2>
            <div className="text-gray-600 prose prose-sm max-w-none leading-relaxed [&>p]:mb-4 [&>ul]:mb-4 [&>ul]:list-disc [&>ul]:pl-5 [&>ul>li]:mb-2 [&>ol]:mb-4 [&>ol]:list-decimal [&>ol]:pl-5 [&>ol>li]:mb-2">
              <ReactMarkdown>{merger.merger_description}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* Commentary */}
        {merger.commentary && (
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50/50 rounded-2xl border border-blue-100/60 shadow-card p-6 mb-6">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-blue-100 flex items-center justify-center">
                <svg className="h-5 w-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-3">
                  Commentary
                </h2>
                {merger.commentary.commentary && (
                  <div className="text-gray-600 prose prose-sm max-w-none leading-relaxed [&>p]:mb-4 [&>ul]:mb-4 [&>ul]:list-disc [&>ul]:pl-5 [&>ul>li]:mb-2 [&>ol]:mb-4 [&>ol]:list-decimal [&>ol]:pl-5 [&>ol>li]:mb-2">
                    <ReactMarkdown>{merger.commentary.commentary}</ReactMarkdown>
                  </div>
                )}
                {merger.commentary.tags && merger.commentary.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {merger.commentary.tags.map((tag, idx) => (
                      <span
                        key={`tag-${tag}-${idx}`}
                        className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-blue-100/80 text-blue-700"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                <div className="flex items-center gap-3 mt-3">
                  {merger.commentary.last_updated && (
                    <p className="text-xs text-gray-400">
                      Updated {formatDate(merger.commentary.last_updated)}
                    </p>
                  )}
                  {merger.commentary.author && (
                    <p className="text-xs text-gray-400">
                      by {merger.commentary.author}
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Industries */}
        {merger.anzsic_codes && merger.anzsic_codes.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6 mb-6">
            <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">
              Industries
            </h2>
            <div className="flex flex-wrap gap-2">
              {merger.anzsic_codes.map((code, idx) => (
                <Link
                  key={`anzsic-${code.code || code.name}`}
                  to={`/mergers?q=${encodeURIComponent(code.name)}`}
                  className="inline-flex items-center px-3 py-1.5 rounded-lg text-sm bg-gray-50 text-gray-600 border border-gray-100 hover:bg-primary/5 hover:text-primary hover:border-primary/20 transition-all"
                >
                  {code.name}
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* Timeline */}
        {sortedEvents.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6">
            <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-6">
              Timeline & Events
            </h2>
            <div className="flow-root">
              <ul className="-mb-8">
                {sortedEvents.map((event, idx) => (
                  <li key={`event-${event.date}-${event.display_title || event.title}-${idx}`}>
                    <div className="relative pb-8">
                      {idx !== sortedEvents.length - 1 && (
                        <span
                          className="absolute top-4 left-4 -ml-px h-full w-0.5 bg-gray-100"
                          aria-hidden="true"
                        />
                      )}
                      <div className="relative flex space-x-3">
                        <div>
                          <span className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center ring-4 ring-white">
                            <div className="h-2.5 w-2.5 rounded-full bg-primary" />
                          </span>
                        </div>
                        <div className="min-w-0 flex-1 pt-1">
                          <p className="text-sm font-medium text-gray-900">
                            {event.display_title || event.title}
                          </p>
                          <p className="text-xs text-gray-400 mt-0.5">
                            {formatDate(event.date)}
                          </p>
                          {event.url_gh && (
                            <div className="mt-1.5">
                              <a
                                href={event.url_gh}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-xs text-primary hover:text-primary-dark transition-colors"
                                aria-label={`View document: ${event.display_title || event.title}`}
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
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

export default MergerDetail;
