import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { FaChevronLeft, FaLink, FaComment } from 'react-icons/fa';
import ReactMarkdown from 'react-markdown';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorCard from '../components/ErrorCard';
import StatusBadge from '../components/StatusBadge';
import BellIcon from '../components/BellIcon';
import WaiverBadge from '../components/WaiverBadge';
import SEO from '../components/SEO';
import ExternalLinkIcon from '../components/ExternalLinkIcon';
import QuestionnaireSection from '../components/QuestionnaireSection';
import DeterminationExplanationSection from '../components/DeterminationExplanationSection';
import MergerTimeline from '../components/MergerTimeline';
import { useTracking } from '../context/TrackingContext';
import { useFetchData } from '../hooks/useFetchData';
import { formatDate } from '../utils/dates';
import { API_ENDPOINTS } from '../config';
import { PROSE_MARKDOWN } from '../utils/classNames';
import { slugify, mergerPath, industryPath } from '../utils/slug';

// Display text for each related-merger relationship. Keys match the
// `relationship` values produced by the data pipeline (see
// scripts/static_data/loaders.py).
const RELATED_MERGER_LABELS = {
  refiled_as: 'Waiver declined – subsequently notified',
  refiled_from: 'Originally filed as a waiver application',
  suspended_refiled_as: 'Assessment suspended – subsequently refiled',
  suspended_refiled_from: 'Refiled after an earlier assessment was suspended',
};

function MergerDetail() {
  const { id, slug } = useParams();
  const navigate = useNavigate();
  const { data: merger, loading, error } = useFetchData(
    API_ENDPOINTS.mergerDetail(id),
    { cacheKey: `merger-${id}` }
  );
  const isNotFound = error === 'HTTP 404';

  // Keep the address bar on the canonical `/mergers/{id}/{slug}` form. When the
  // page is reached via a bare-id link or a stale/incorrect slug, rewrite the
  // URL (history replace, no extra entry) once the merger data has loaded so the
  // visible URL matches the <link rel="canonical"> and sitemap entry.
  useEffect(() => {
    if (!merger) return;
    const canonicalSlug = slugify(merger.merger_name);
    if ((slug || '') !== canonicalSlug) {
      navigate(mergerPath(merger.merger_id, merger.merger_name), { replace: true });
    }
  }, [merger, slug, navigate]);
  const [expandedParties, setExpandedParties] = useState({});
  const { isTracked, toggleTracking } = useTracking();
  const tracked = isTracked(id);
  const savedParams = sessionStorage.getItem('mergers_filter_params');
  const backToMergers = savedParams ? `/mergers?${savedParams}` : '/mergers';

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
            <Link
              to={`/mergers?q=${encodeURIComponent(party.canonical?.name || party.name)}`}
              className={party.canonical?.name
                ? 'font-medium text-primary hover:text-primary-dark transition-colors'
                : 'font-medium text-gray-900 hover:text-primary transition-colors'}
              title={party.canonical?.name
                ? `See all mergers involving ${party.canonical.name}`
                : `Search mergers for ${party.name}`}
            >
              {party.name}
            </Link>
            {party.identifier && (
              <p className="text-sm text-gray-500">
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
      <ErrorCard
        title={isNotFound ? "Merger not found" : "Error loading merger"}
        message={isNotFound
          ? `We couldn't find a merger with ID "${id}". It may have been removed or the ID might be incorrect.`
          : error
        }
        backTo={backToMergers}
        backLabel="← Back to all mergers"
        secondaryAction={{
          href: `https://www.accc.gov.au/public-registers/mergers-and-acquisitions-registers/acquisitions-register?init=1&query=${id}`,
          label: 'Check ACCC website →',
          ariaLabel: `Search for ${id} on ACCC website`,
        }}
      />
    );
  }
  if (!merger) return null;

  const sortedEvents = merger.events
    ? [...merger.events].sort((a, b) => new Date(b.date) - new Date(a.date))
    : [];

  const determinationEvent = merger.events
    ? merger.events.find(event => event.is_determination_event)
    : null;

  const statementOfReasonsEvent = merger.phase_2_determination
    ? merger.events?.find(e => e.url_gh && e.title?.toLowerCase().includes('statement of reasons'))
    : null;
  const determinationDocUrl = statementOfReasonsEvent?.url_gh ?? determinationEvent?.url_gh;

  const siteUrl = 'https://mergers.fyi';
  const pagePath = mergerPath(merger.merger_id, merger.merger_name);
  const pageUrl = `${siteUrl}${pagePath}`;
  const modifiedTime = merger.determination_publication_date || merger.effective_notification_datetime;
  const articleSection = merger.anzsic_codes?.[0]?.name;

  const articleSchema = {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": merger.merger_name,
    "description": merger.merger_description || `Merger between ${merger.acquirers.map(a => a.name).join(', ')} and ${merger.targets.map(t => t.name).join(', ')}`,
    "datePublished": merger.effective_notification_datetime,
    "dateModified": modifiedTime,
    "mainEntityOfPage": {
      "@type": "WebPage",
      "@id": pageUrl
    },
    "author": {
      "@type": "Person",
      "name": "Nick Twort",
      "url": siteUrl
    },
    "publisher": {
      "@type": "Organization",
      "name": "Australian Merger Tracker",
      "url": siteUrl,
      "logo": {
        "@type": "ImageObject",
        "url": `${siteUrl}/og-image.png`
      }
    },
    "about": [
      ...merger.acquirers.map(a => ({ "@type": "Organization", "name": a.name })),
      ...merger.targets.map(t => ({ "@type": "Organization", "name": t.name }))
    ]
  };

  const breadcrumbSchema = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      { "@type": "ListItem", "position": 1, "name": "Home", "item": siteUrl },
      { "@type": "ListItem", "position": 2, "name": "Mergers", "item": `${siteUrl}/mergers` },
      { "@type": "ListItem", "position": 3, "name": merger.merger_name, "item": pageUrl }
    ]
  };

  const structuredData = [articleSchema, breadcrumbSchema];

  return (
    <>
      <SEO
        title={merger.merger_name}
        description={merger.merger_description || `ACCC merger review: ${merger.acquirers.map(a => a.name).join(', ')} acquiring ${merger.targets.map(t => t.name).join(', ')}. Status: ${merger.status}`}
        url={pagePath}
        type="article"
        publishedTime={merger.effective_notification_datetime}
        modifiedTime={modifiedTime}
        section={articleSection}
        structuredData={structuredData}
      />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        {/* Back button */}
        <Link
          to={backToMergers}
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-primary mb-5 transition-colors"
          aria-label="Return to all mergers list"
        >
          <FaChevronLeft className="w-4 h-4" aria-hidden="true" />
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
                {merger.is_waiver && <WaiverBadge className="px-2.5 py-1 rounded-lg text-sm" />}
              </div>
              <div className="flex items-center gap-4 flex-wrap">
                <p className="text-sm text-gray-500">{merger.merger_id}</p>
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
                <BellIcon filled={tracked} className="w-3.5 h-3.5" />
                {tracked ? 'Tracking' : 'Track'}
              </button>
            </div>
          </div>

          {/* Assessment timeline */}
          <div className="mt-6 pt-6 border-t border-gray-100">
            <MergerTimeline merger={merger} />
          </div>

          {/* Stage & determination */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6 pt-6 border-t border-gray-100">
            <div>
              <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">Stage</h3>
              <p className="text-sm font-medium text-gray-900">{merger.stage || 'N/A'}</p>
            </div>
            {merger.accc_determination && (
              <div>
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">
                  Determination
                </h3>
                <p className="text-sm font-medium text-gray-900">
                  {determinationDocUrl ? (
                    <a
                      href={determinationDocUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-primary hover:text-primary-dark transition-colors"
                      aria-label={`View determination document: ${merger.accc_determination} (opens in new tab)`}
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

        {/* Related Merger Link */}
        {merger.related_merger && (
          <Link
            to={mergerPath(merger.related_merger.merger_id, merger.related_merger.merger_name)}
            className="flex items-center gap-3 bg-amber-50/80 rounded-2xl border border-amber-200/60 shadow-card p-4 mb-6 hover:bg-amber-50 hover:border-amber-300/60 transition-all group"
          >
            <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-amber-100 flex items-center justify-center">
              <FaLink className="h-5 w-5 text-amber-600" aria-hidden="true" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900">
                {RELATED_MERGER_LABELS[merger.related_merger.relationship]
                  ?? RELATED_MERGER_LABELS.refiled_from}
              </p>
            </div>
          </Link>
        )}

        {/* Determination explanation (waivers and Phase 1 approved notifications) */}
        <DeterminationExplanationSection merger={merger} />

        {/* Commentary */}
        {merger.comments && merger.comments.length > 0 && (
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50/50 rounded-2xl border border-blue-100/60 shadow-card mb-6 overflow-hidden divide-y divide-blue-100/60">
            {merger.comments.map((comment, commentIdx) => (
              <div key={commentIdx} className="p-6">
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-blue-100 flex items-center justify-center">
                    <FaComment className="h-5 w-5 text-blue-600" aria-hidden="true" />
                  </div>
                  <div className="flex-1 min-w-0">
                    {commentIdx === 0 && (
                      <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-3">
                        Commentary
                      </h2>
                    )}
                    {comment.commentary && (
                      <div className={PROSE_MARKDOWN}>
                        <ReactMarkdown>{comment.commentary}</ReactMarkdown>
                      </div>
                    )}
                    {comment.tags && comment.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-3">
                        {comment.tags.map((tag, idx) => (
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
            <div className={PROSE_MARKDOWN}>
              <ReactMarkdown>{merger.merger_description}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* Questionnaire */}
        {merger.has_questionnaire && (
          <QuestionnaireSection mergerId={merger.merger_id} events={merger.events} />
        )}

        {/* Industries */}
        {merger.anzsic_codes && merger.anzsic_codes.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6 mb-6">
            <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">
              Industries
            </h2>
            <div className="flex flex-wrap gap-2">
              {merger.anzsic_codes.map((code) => (
                <Link
                  key={`anzsic-${code.code || code.name}`}
                  to={code.code ? industryPath(code.code, code.name) : `/mergers?q=${encodeURIComponent(code.name)}`}
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
                          <p className="text-xs text-gray-500 mt-0.5">
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

        {/* Similar Mergers */}
        {merger.similar_mergers && merger.similar_mergers.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6 mt-6">
            <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">
              You might be interested in
            </h2>
            <div className="divide-y divide-gray-50">
              {merger.similar_mergers.map((similar) => (
                <Link
                  key={similar.merger_id}
                  to={mergerPath(similar.merger_id, similar.merger_name)}
                  className="flex items-start gap-3 py-3 first:pt-0 last:pb-0 hover:opacity-75 transition-opacity group"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 group-hover:text-primary transition-colors truncate">
                      {similar.merger_name}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5 truncate">
                      {[
                        ...(similar.acquirers || []).map(a => a.name),
                        '→',
                        ...(similar.targets || []).map(t => t.name),
                      ].join(' ')}
                    </p>
                  </div>
                  {similar.accc_determination ? (
                    <span className="flex-shrink-0 text-xs text-gray-500 mt-0.5">{similar.accc_determination}</span>
                  ) : similar.status ? (
                    <span className="flex-shrink-0 text-xs text-gray-500 mt-0.5">{similar.status}</span>
                  ) : null}
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  );
}

export default MergerDetail;
