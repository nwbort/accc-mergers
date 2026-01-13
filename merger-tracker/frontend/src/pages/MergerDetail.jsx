import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import LoadingSpinner from '../components/LoadingSpinner';
import StatusBadge from '../components/StatusBadge';
import SEO from '../components/SEO';
import { formatDate, calculateDuration, getDaysRemaining, calculateBusinessDays, getBusinessDaysRemaining } from '../utils/dates';
import { API_ENDPOINTS } from '../config';

function MergerDetail() {
  const { id } = useParams();
  const [merger, setMerger] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchMerger();
  }, [id]);

  const fetchMerger = async () => {
    try {
      // Load all mergers and find by ID (static JSON approach)
      const response = await fetch(API_ENDPOINTS.mergers);
      if (!response.ok) {
        throw new Error('Failed to fetch merger details');
      }
      const data = await response.json();
      const found = data.mergers.find(m => m.merger_id === id);
      
      if (!found) {
        throw new Error('not_found');
      }
      
      setMerger(found);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (error) {
    return (
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-lg shadow-lg p-8 text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">
            {error === 'not_found' ? "Hmm...merger not found" : "Error loading merger"}
          </h1>
          <p className="text-gray-600 mb-6">
            {error === 'not_found'
              ? `We couldn't find a merger with ID "${id}". It may have been removed or the ID might be incorrect.`
              : error
            }
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              to="/mergers"
              className="inline-flex items-center px-4 py-2 border border-transparent text-base font-medium rounded-md text-white bg-primary hover:bg-primary-dark transition-colors"
            >
              ← Back to all mergers
            </Link>
            <span className="text-gray-500">or</span>
            <a
              href={`https://www.accc.gov.au/public-registers/mergers-and-acquisitions-registers/acquisitions-register?init=1&query=${id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-4 py-2 border border-gray-300 text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 transition-colors"
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

  // Sort events by date (newest first)
  const sortedEvents = merger.events
    ? [...merger.events].sort((a, b) => new Date(b.date) - new Date(a.date))
    : [];

  // Create structured data for SEO
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
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Back button */}
        <Link
          to="/mergers"
          className="text-primary hover:text-primary-dark mb-4 inline-flex items-center"
        >
          ← Back to all mergers
        </Link>

        {/* Header */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-2xl font-bold text-gray-900">
                  {merger.merger_name}
                </h1>
                {merger.is_waiver && (
                  <span className="inline-flex items-center px-2.5 py-1 rounded text-sm font-medium bg-amber-100 text-amber-800">
                    waiver
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4">
                <p className="text-sm text-gray-500">{merger.merger_id}</p>
                {merger.url && (
                  <a
                    href={merger.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-primary hover:text-primary-dark"
                  >
                    View on ACCC website →
                  </a>
                )}
              </div>
            </div>
            <StatusBadge
              status={merger.status}
              determination={merger.accc_determination}
            />
          </div>

          {/* Key Information Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
            <div>
              <h3 className="text-sm font-medium text-gray-500 mb-2">Stage</h3>
              <p className="text-base text-gray-900">{merger.stage || 'N/A'}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-500 mb-2">
                {merger.is_waiver ? 'Waiver Application Date' : 'Effective Notification'}
              </h3>
              <p className="text-base text-gray-900">
                {formatDate(merger.effective_notification_datetime)}
              </p>
            </div>
            {/* Only show End of Determination Period for non-waiver mergers */}
            {!merger.is_waiver && (
              <div>
                <h3 className="text-sm font-medium text-gray-500 mb-2">
                  End of Determination Period
                </h3>
                <p className="text-base text-gray-900">
                  {formatDate(merger.end_of_determination_period)}
                  {daysRemaining !== null && daysRemaining > 0 && !merger.determination_publication_date && (
                    <span className="ml-2 text-sm text-gray-500">
                      ({daysRemaining} calendar days, {businessDaysRemaining} business days remaining)
                    </span>
                  )}
                </p>
              </div>
            )}
            {merger.determination_publication_date && (
              <div>
                <h3 className="text-sm font-medium text-gray-500 mb-2">
                  Determination Published
                </h3>
                <p className="text-base text-gray-900">
                  {formatDate(merger.determination_publication_date)}
                  {duration !== null && businessDuration !== null && (
                    <span className="ml-2 text-sm text-gray-500">
                      ({duration} calendar days, {businessDuration} business days)
                    </span>
                  )}
                </p>
              </div>
            )}
            {merger.accc_determination && (
              <div>
                <h3 className="text-sm font-medium text-gray-500 mb-2">
                  Determination
                </h3>
                <p className="text-base text-gray-900">
                  {merger.accc_determination}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Parties */}
        <div className={`grid grid-cols-1 ${merger.other_parties && merger.other_parties.length > 0 ? 'md:grid-cols-3' : 'md:grid-cols-2'} gap-6 mb-6`}>
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Acquirers
            </h2>
            {merger.acquirers.map((acquirer, idx) => (
              <div key={idx} className="mb-3">
                <p className="font-medium text-gray-900">{acquirer.name}</p>
                {acquirer.identifier && (
                  <p className="text-sm text-gray-500">
                    {acquirer.identifier_type ? `${acquirer.identifier_type}: ` : ''}{acquirer.identifier}
                  </p>
                )}
              </div>
            ))}
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Targets
            </h2>
            {merger.targets.map((target, idx) => (
              <div key={idx} className="mb-3">
                <p className="font-medium text-gray-900">{target.name}</p>
                {target.identifier && (
                  <p className="text-sm text-gray-500">
                    {target.identifier_type ? `${target.identifier_type}: ` : ''}{target.identifier}
                  </p>
                )}
              </div>
            ))}
          </div>

          {merger.other_parties && merger.other_parties.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Other parties
              </h2>
              {merger.other_parties.map((party, idx) => (
                <div key={idx} className="mb-3">
                  <p className="font-medium text-gray-900">{party.name}</p>
                  {party.identifier && (
                    <p className="text-sm text-gray-500">
                      {party.identifier_type ? `${party.identifier_type}: ` : ''}{party.identifier}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Description */}
        {merger.merger_description && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Description
            </h2>
            <div className="text-gray-700 prose prose-sm max-w-none [&>p]:mb-4 [&>ul]:mb-4 [&>ul]:list-disc [&>ul]:pl-5 [&>ul>li]:mb-2 [&>ol]:mb-4 [&>ol]:list-decimal [&>ol]:pl-5 [&>ol>li]:mb-2">
              <ReactMarkdown>{merger.merger_description}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* Industries */}
        {merger.anzsic_codes && merger.anzsic_codes.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Industries
            </h2>
            <div className="flex flex-wrap gap-2">
              {merger.anzsic_codes.map((code, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center px-3 py-1 rounded-md text-sm bg-gray-100 text-gray-700"
                >
                  <span className="font-medium mr-1">{code.code}:</span>
                  {code.name}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Timeline */}
        {sortedEvents.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Timeline & Events
            </h2>
            <div className="flow-root">
              <ul className="-mb-8">
                {sortedEvents.map((event, idx) => (
                  <li key={idx}>
                    <div className="relative pb-8">
                      {idx !== sortedEvents.length - 1 && (
                        <span
                          className="absolute top-4 left-4 -ml-px h-full w-0.5 bg-gray-200"
                          aria-hidden="true"
                        />
                      )}
                      <div className="relative flex space-x-3">
                        <div>
                          <span className="h-8 w-8 rounded-full bg-primary flex items-center justify-center ring-8 ring-white">
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
                          </span>
                        </div>
                        <div className="min-w-0 flex-1 pt-1.5">
                          <div className="flex items-center justify-between">
                            <p className="text-sm font-medium text-gray-900">
                              {event.display_title || event.title}
                            </p>
                          </div>
                          <p className="text-sm text-gray-500">
                            {formatDate(event.date)}
                          </p>
                          {(event.url || event.url_gh) && (
                            <div className="mt-2 space-x-2">
                              {event.url && event.status !== 'removed' && (
                                <a
                                  href={event.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-sm text-primary hover:text-primary-dark"
                                >
                                  View document on ACCC website →
                                </a>
                              )}
                              {event.url_gh && (
                                <a
                                  href={event.url_gh}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-sm text-primary hover:text-primary-dark"
                                >
                                  View document →
                                </a>
                              )}
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
