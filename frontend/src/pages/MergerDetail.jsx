import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router';
import { FaChevronLeft, FaLink, FaComment, FaGavel, FaBalanceScale } from 'react-icons/fa';
import ReactMarkdown from 'react-markdown';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorCard from '../components/ErrorCard';
import StatusBadge from '../components/StatusBadge';
import TrackButton from '../components/TrackButton';
import WaiverBadge from '../components/WaiverBadge';
import AppealBadge from '../components/AppealBadge';
import BusinessDayProgress from '../components/BusinessDayProgress';
import Phase2OddsReveal from '../components/Phase2OddsReveal';
import PreNotificationEstimate from '../components/PreNotificationEstimate';
import { getBusinessDayProgress } from '../utils/businessDayProgress';
import SEO from '../components/SEO';
import ExternalLinkIcon from '../components/ExternalLinkIcon';
import QuestionnaireSection from '../components/QuestionnaireSection';
import DeterminationExplanationSection from '../components/DeterminationExplanationSection';
import Phase2NoticeMattersSection from '../components/Phase2NoticeMattersSection';
import MergerTimeline from '../components/MergerTimeline';
import MergerOutcomeHeading from '../components/MergerOutcomeHeading';
import { useTracking } from '../context/TrackingContext';
import { useFetchData } from '../hooks/useFetchData';
import { formatDate, formatDateLong } from '../utils/dates';
import { API_ENDPOINTS } from '../config';
import { PROSE_MARKDOWN, CARD, SECTION_HEADING } from '../utils/classNames';
import { slugify, mergerPath, industryPath, partyPath } from '../utils/slug';
import { mergerMeta } from '../utils/pageMeta';
import { getDecidedOutcome, getDeterminationDocUrl } from '../utils/mergerOutcome';
import { MERGER_STATUS } from '../constants/mergerStatus';
import { APPEAL_TYPE_LABELS, DEFAULT_APPEAL_LABEL, APPEAL_STATUS, APPEAL_OUTCOME_LABELS } from '../constants/appeal';
import { OUTCOME_DOT_COLORS, DEFAULT_OUTCOME_DOT, APPEAL_DOT, getOutcomeDot } from '../constants/outcomeDotColors';
import { getOutcomeHeaderStyle } from '../constants/outcomeHeader';

// Display text for each related-merger relationship. Keys match the
// `relationship` values produced by the data pipeline (see
// scripts/generate/static_data/loaders.py).
const RELATED_MERGER_LABELS = {
  refiled_as: 'Waiver declined – subsequently notified',
  refiled_from: 'Originally filed as a waiver application',
  suspended_refiled_as: 'Assessment suspended – subsequently refiled',
  suspended_refiled_from: 'Refiled after an earlier assessment was suspended',
};

function MergerDetail() {
  const { id, slug } = useParams();
  const navigate = useNavigate();
  // Merger IDs (e.g. MN-01016) are always uppercase in the static data files,
  // so a lowercase/mixed-case URL would otherwise 404. Fetch by the
  // normalised ID and let the effect below fix up the visible URL.
  const normalizedId = id ? id.toUpperCase() : id;
  const { data: merger, loading, error } = useFetchData(
    API_ENDPOINTS.mergerDetail(normalizedId),
    { cacheKey: `merger-${normalizedId}` }
  );
  const isNotFound = error === 'HTTP 404';

  // Keep the address bar on the canonical `/mergers/{id}/{slug}` form. When the
  // page is reached via a bare-id link, a lowercase/mixed-case ID, or a
  // stale/incorrect slug, rewrite the URL (history replace, no extra entry)
  // once the merger data has loaded so the visible URL matches the
  // <link rel="canonical"> and sitemap entry.
  useEffect(() => {
    if (!merger) return;
    const canonicalSlug = slugify(merger.merger_name);
    if (id !== merger.merger_id || (slug || '') !== canonicalSlug) {
      navigate(mergerPath(merger.merger_id, merger.merger_name), { replace: true });
    }
  }, [merger, id, slug, navigate]);
  const [expandedParties, setExpandedParties] = useState({});
  const [expandedAppealRuns, setExpandedAppealRuns] = useState(() => new Set());
  const toggleAppealRun = (startIdx) => {
    setExpandedAppealRuns(prev => {
      const next = new Set(prev);
      if (next.has(startIdx)) next.delete(startIdx);
      else next.add(startIdx);
      return next;
    });
  };
  const { isTracked, toggleTracking } = useTracking();
  const tracked = isTracked(normalizedId);
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
      <div className={`${CARD} p-6`}>
        <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">{title}</h2>
        {visibleParties.map((party, idx) => (
          <div key={`${partyType}-${party.name}-${party.identifier || idx}`} className="mb-3 last:mb-0">
            {party.party_page?.id ? (
              <Link
                to={partyPath(party.party_page.id, party.party_page.name)}
                className={party.canonical?.name
                  ? 'font-medium text-primary hover:text-primary-dark transition-colors'
                  : 'font-medium text-gray-900 hover:text-primary transition-colors'}
                title={`View the party page for ${party.party_page.name || party.name}`}
              >
                {party.name}
              </Link>
            ) : (
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
            )}
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
          href: `https://www.accc.gov.au/public-registers/acquisitions-and-mergers-registers/acquisitions-register?init=1&query=${id}`,
          label: 'Check ACCC website →',
          ariaLabel: `Search for ${id} on ACCC website`,
        }}
      />
    );
  }
  if (!merger) return null;

  const businessDayProgress = getBusinessDayProgress(merger);

  const sortedEvents = merger.events
    ? [...merger.events].sort((a, b) => new Date(b.date) - new Date(a.date))
    : [];

  // Tribunal appeal documents tend to arrive in a burst and clutter the
  // timeline. When more than two land back-to-back (most recent first,
  // since sortedEvents is date-descending), keep only the newest one visible
  // and collapse the rest behind a toggle. appealRunLength maps the run's
  // start index to its size; appealRunStart maps every other member of that
  // run back to the start index so it can be hidden until expanded.
  const appealRunLength = new Map();
  const appealRunStart = new Map();
  for (let i = 0; i < sortedEvents.length; i++) {
    if (!sortedEvents[i].is_appeal) continue;
    let j = i;
    while (j < sortedEvents.length && sortedEvents[j].is_appeal) j++;
    if (j - i > 2) {
      appealRunLength.set(i, j - i);
      for (let k = i + 1; k < j; k++) appealRunStart.set(k, i);
    }
    i = j - 1;
  }

  // Flatten sortedEvents into the rows the timeline actually renders: hidden
  // run members are dropped, and a toggle row is inserted right after the
  // visible head of each collapsed run.
  const timelineRows = [];
  for (let i = 0; i < sortedEvents.length; i++) {
    const runStart = appealRunStart.get(i);
    if (runStart !== undefined && !expandedAppealRuns.has(runStart)) continue;
    timelineRows.push({ type: 'event', event: sortedEvents[i], idx: i });
    const runLength = appealRunLength.get(i);
    if (runLength) {
      timelineRows.push({ type: 'appeal-toggle', idx: i, runLength, expanded: expandedAppealRuns.has(i) });
    }
  }

  // The event marking referral to Phase 2 — the same point the header timeline
  // flags with an amber marker (both keyed off phase_1_determination_date). It
  // gets the matching amber dot in the events list below.
  const isPhase2ReferralEvent = (event) =>
    event.phase === 'Phase 2'
    && merger.phase_1_determination_date
    && event.date === merger.phase_1_determination_date;

  // The event marking the assessment being ceased — the same point the header
  // timeline flags with a purple endpoint (both keyed off ceased_date). It gets
  // the matching purple dot in the events list below.
  const isCeasedEvent = (event) =>
    merger.ceased_date && event.date === merger.ceased_date;

  // Dot styling for an event: the ceased and Phase 2 referral events keep their
  // amber/purple, the final determination event (a Phase 1 approval or the
  // Phase 2 determination) is coloured by outcome to match the header timeline's
  // endpoint, and everything else falls back to the primary colour.
  const dotStyleForEvent = (event) => {
    if (event.is_appeal) return APPEAL_DOT;
    if (isCeasedEvent(event)) return OUTCOME_DOT_COLORS[MERGER_STATUS.ASSESSMENT_CEASED];
    if (isPhase2ReferralEvent(event)) return OUTCOME_DOT_COLORS[MERGER_STATUS.REFERRED_TO_PHASE_2];
    if (event.is_determination_event) {
      return getOutcomeDot({ determination: merger.accc_determination });
    }
    return DEFAULT_OUTCOME_DOT;
  };

  // Once a matter is decided the header card's title block is filled with the
  // outcome's colour and MergerOutcomeHeading states the result above the
  // title. Everything in that block flips to its on-dark treatment, the card's
  // top rule takes the same colour, the status badge and "Determination" field
  // stand down rather than repeat what the block already says, and the
  // timeline drops the divider it would otherwise draw under the fill.
  const decidedOutcome = getDecidedOutcome(merger);
  const outcomeStyle = decidedOutcome ? getOutcomeHeaderStyle(decidedOutcome.outcome) : null;
  // Kept for the rare matter carrying a determination that getDecidedOutcome
  // doesn't recognise as an ending; otherwise the header block is the only
  // place the outcome appears.
  const showDeterminationField = Boolean(merger.accc_determination) && !decidedOutcome;
  const determinationDocUrl = getDeterminationDocUrl(merger);
  const headerLinkClass = outcomeStyle
    ? `inline-flex items-center gap-1 text-sm transition-colors ${outcomeStyle.link} ${outcomeStyle.focus}`
    : 'inline-flex items-center gap-1 text-sm text-primary hover:text-primary-dark transition-colors';

  // The appeal card links to the Application for Review — the document that
  // initiated the appeal — rather than the tribunal matter page itself.
  // Tribunal document lists aren't reliably date-sorted, so match on the
  // document's title/description instead of assuming a fixed position;
  // fall back to the last-listed document, which is where it typically sits.
  const appealDocuments = merger.appeal?.documents;
  const appealDocument = appealDocuments?.find(doc =>
    doc.description?.toLowerCase().includes('application for review')
  ) ?? appealDocuments?.[appealDocuments.length - 1];
  const appealDocumentUrl = appealDocument?.url_gh ?? appealDocument?.url ?? merger.appeal?.tribunal_url;

  // Built by the same helper the build-time prerenderer uses, so the raw HTML
  // crawlers read and the head React renders here cannot drift apart.
  const meta = mergerMeta(merger);

  return (
    <>
      <SEO
        title={meta.title}
        description={meta.description}
        url={meta.path}
        type={meta.type}
        publishedTime={meta.publishedTime}
        modifiedTime={meta.modifiedTime}
        section={meta.section}
        structuredData={meta.structuredData}
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
        <div
          className={`${CARD} p-6 mb-6 card-accent`}
          style={outcomeStyle ? { '--card-accent': outcomeStyle.accent } : undefined}
        >
          {/* Title block. For a decided matter it is pulled out to the card's
              edges and filled with the outcome's colour, so the result is the
              first thing the page says; the card's own p-6 keeps the padding
              identical either way. */}
          <div
            className={outcomeStyle
              ? `-mt-6 -mx-6 px-6 pt-6 pb-6 ${outcomeStyle.bg} ${outcomeStyle.text}`
              : undefined}
          >
            <div className="flex items-start justify-between gap-4 pt-1">
              <div className="min-w-0">
                <MergerOutcomeHeading merger={merger} />
                {/* The badge trails the title's last word rather than sitting
                    in a flex row beside it: a title long enough to wrap would
                    otherwise push the badge onto a line of its own, leaving a
                    loose gap above the ID row. Inline siblings inside a block,
                    so the h1's accessible name stays the merger name alone. */}
                <div className="mb-2">
                  <h1 className={`inline text-2xl font-bold tracking-tight ${outcomeStyle ? '' : 'text-gray-900'}`}>
                    {merger.merger_name}
                  </h1>
                  {merger.is_waiver && (
                    <WaiverBadge className="ml-3 align-middle px-2.5 py-1 rounded-lg text-sm" />
                  )}
                </div>
                <div className="flex items-center gap-4 flex-wrap">
                  <p className={`text-sm ${outcomeStyle ? outcomeStyle.sub : 'text-gray-500'}`}>
                    {merger.merger_id}
                  </p>
                  {merger.url && (
                    <a
                      href={merger.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={headerLinkClass}
                      aria-label={`View ${merger.merger_name} on ACCC website`}
                    >
                      View on ACCC website
                      <ExternalLinkIcon />
                    </a>
                  )}
                  {/* The determination document moves up here for a decided
                      matter, since the "Determination" field that used to
                      carry it stands down below. */}
                  {decidedOutcome && determinationDocUrl && (
                    <a
                      href={determinationDocUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={headerLinkClass}
                      aria-label={`View the determination document for ${merger.merger_name}`}
                    >
                      View determination
                      <ExternalLinkIcon />
                    </a>
                  )}
                </div>
              </div>
              <div className="flex flex-col items-end gap-2 flex-shrink-0">
                <div className="flex items-center gap-2 flex-wrap justify-end">
                  {merger.under_appeal && <AppealBadge />}
                  {!decidedOutcome && (
                    <Phase2OddsReveal merger={merger}>
                      <StatusBadge
                        status={merger.status}
                        determination={merger.accc_determination}
                        hasConditions={merger.has_conditions}
                        appeal={merger.appeal}
                      />
                    </Phase2OddsReveal>
                  )}
                </div>
                <TrackButton
                  active={tracked}
                  onClick={() => toggleTracking(normalizedId)}
                  activeLabel="Tracking"
                  inactiveLabel="Track"
                  activeAriaLabel="Stop tracking this merger"
                  inactiveAriaLabel="Track this merger for updates"
                  onDark={Boolean(outcomeStyle)}
                />
              </div>
            </div>
          </div>

          {/* Business day progress (non-waiver matters under assessment) */}
          {businessDayProgress && (
            <div className="mt-4">
              <BusinessDayProgress merger={merger} />
            </div>
          )}

          {/* Assessment timeline */}
          <div className={decidedOutcome ? 'mt-6' : 'mt-6 pt-6 border-t border-gray-100'}>
            <MergerTimeline merger={merger} />
          </div>

          {/* Stage & determination */}
          <div className={`grid grid-cols-1 ${
            showDeterminationField && merger.appeal
              ? 'md:grid-cols-3'
              : (showDeterminationField || merger.appeal)
                ? 'md:grid-cols-2'
                : 'md:grid-cols-1'
          } gap-6 mt-6 pt-6 border-t border-gray-100`}>
            <div>
              <h2 className={`${SECTION_HEADING} mb-1.5`}>Stage</h2>
              <p className="text-sm font-medium text-gray-900">{merger.stage || 'N/A'}</p>
            </div>
            {showDeterminationField && (
              <div>
                <h2 className={`${SECTION_HEADING} mb-1.5`}>
                  Determination
                </h2>
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
            {merger.appeal && (
              <div>
                <h2 className={`${SECTION_HEADING} mb-1.5`}>
                  Tribunal appeal
                </h2>
                <p className="text-sm font-medium text-gray-900">
                  {merger.appeal.tribunal_url ? (
                    <a
                      href={merger.appeal.tribunal_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-primary hover:text-primary-dark transition-colors"
                      aria-label={`View this matter on the Australian Competition Tribunal website${merger.appeal.tribunal_number ? ` (${merger.appeal.tribunal_number})` : ''}`}
                    >
                      {merger.appeal.status === APPEAL_STATUS.CONCLUDED
                        ? (APPEAL_OUTCOME_LABELS[merger.appeal.outcome] || 'Concluded')
                        : 'Ongoing'}
                      <ExternalLinkIcon />
                    </a>
                  ) : (
                    merger.appeal.status === APPEAL_STATUS.CONCLUDED
                      ? (APPEAL_OUTCOME_LABELS[merger.appeal.outcome] || 'Concluded')
                      : 'Ongoing'
                  )}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Estimated start of pre-notification (inferred, mandatory-regime
            notifications only) */}
        <PreNotificationEstimate merger={merger} />

        {/* Related Merger Link */}
        {merger.related_merger && (
          <Link
            to={mergerPath(merger.related_merger.merger_id, merger.related_merger.merger_name)}
            className="flex items-center gap-3 bg-amber-50/80 rounded-2xl border border-amber-200/60 shadow-card p-4 mb-6 hover:bg-amber-50 hover:border-amber-300/60 transition-all group"
          >
            <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-amber-100 flex items-center justify-center">
              <FaLink className="h-5 w-5 text-amber-700" aria-hidden="true" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900">
                {RELATED_MERGER_LABELS[merger.related_merger.relationship]
                  ?? RELATED_MERGER_LABELS.refiled_from}
              </p>
            </div>
          </Link>
        )}

        {/* Tribunal appeal link — mirrors the related-merger link styling, but
            points to the appeal document itself (e.g. the Application for
            Review) rather than the tribunal matter page, which is linked from
            the "Tribunal appeal" field in the header card instead. */}
        {merger.appeal && appealDocumentUrl && (
          <a
            href={appealDocumentUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 bg-amber-50/80 rounded-2xl border border-amber-200/60 shadow-card p-4 mb-6 hover:bg-amber-50 hover:border-amber-300/60 transition-all group"
            aria-label={`View the appeal document${merger.appeal.appellant ? ` filed by ${merger.appeal.appellant}` : ''}`}
          >
            <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-amber-100 flex items-center justify-center">
              <FaGavel className="h-4 w-4 text-amber-700" aria-hidden="true" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900">
                {merger.appeal.appellant ? `Decision appealed by ${merger.appeal.appellant}` : (APPEAL_TYPE_LABELS[merger.appeal.appeal_type] || DEFAULT_APPEAL_LABEL)}
                {merger.appeal.filed_date ? ` on ${formatDateLong(merger.appeal.filed_date)}` : ''}
                {merger.appeal.status === APPEAL_STATUS.CONCLUDED && (
                  <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium bg-gray-100 text-gray-600 align-middle">
                    Concluded
                  </span>
                )}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">
                Australian Competition Tribunal
                {merger.appeal.tribunal_number ? ` · ${merger.appeal.tribunal_number}` : ''}
                {merger.appeal.status === APPEAL_STATUS.CONCLUDED && merger.appeal.outcome
                  ? ` · ${APPEAL_OUTCOME_LABELS[merger.appeal.outcome] || merger.appeal.outcome}`
                  : ''}
              </p>
            </div>
            <ExternalLinkIcon className="h-3.5 w-3.5 text-amber-700 flex-shrink-0" />
          </a>
        )}

        {/* Judicial review link — a Federal Court review is a separate avenue
            from a Tribunal appeal, so this links straight to the court's own
            case page on the Commonwealth Courts Portal rather than to any
            locally-hosted document. */}
        {merger.judicial_review?.case_url && (
          <a
            href={merger.judicial_review.case_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 bg-amber-50/80 rounded-2xl border border-amber-200/60 shadow-card p-4 mb-6 hover:bg-amber-50 hover:border-amber-300/60 transition-all group"
            aria-label={`View the judicial review case${merger.judicial_review.applicant ? ` requested by ${merger.judicial_review.applicant}` : ''} on the Commonwealth Courts Portal`}
          >
            <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-amber-100 flex items-center justify-center">
              <FaBalanceScale className="h-4 w-4 text-amber-600" aria-hidden="true" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900">
                {merger.judicial_review.applicant ? `Judicial review requested by ${merger.judicial_review.applicant}` : 'Judicial review requested'}
                {merger.judicial_review.filed_date ? ` on ${formatDateLong(merger.judicial_review.filed_date)}` : ''}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">
                {merger.judicial_review.case_number}
              </p>
            </div>
            <ExternalLinkIcon className="h-3.5 w-3.5 text-amber-600 flex-shrink-0" />
          </a>
        )}

        {/* Determination explanation (waivers and Phase 1 approved notifications) */}
        <DeterminationExplanationSection merger={merger} />

        {/* Matters the ACCC intends to investigate (Phase 2 Notice) */}
        <Phase2NoticeMattersSection merger={merger} />

        {/* Commentary */}
        {merger.comments && merger.comments.length > 0 && (
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50/50 rounded-2xl border border-blue-100/60 shadow-card mb-6 overflow-hidden divide-y divide-blue-100/60">
            {[...merger.comments]
              .sort((a, b) => (b.date || '').localeCompare(a.date || ''))
              .map((comment, commentIdx) => (
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
          <div className={`${CARD} p-6 mb-6`}>
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
          <div className={`${CARD} p-6 mb-6`}>
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
          <div className={`${CARD} p-6`}>
            <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-6">
              Timeline & Events
            </h2>
            <div className="flow-root">
              <ul className="-mb-8">
                {timelineRows.map((row, rowIdx) => {
                  const isLastRow = rowIdx === timelineRows.length - 1;
                  const connector = !isLastRow && (
                    <span
                      className="absolute top-4 left-4 -ml-px h-full w-0.5 bg-gray-100"
                      aria-hidden="true"
                    />
                  );

                  if (row.type === 'appeal-toggle') {
                    return (
                      <li key={`appeal-toggle-${row.idx}`}>
                        <div className="relative pb-8">
                          {connector}
                          <div className="relative flex space-x-3">
                            <div className="h-8 w-8 flex items-center justify-center" aria-hidden="true" />
                            <div className="min-w-0 flex-1 pt-1">
                              <button
                                type="button"
                                onClick={() => toggleAppealRun(row.idx)}
                                className="text-xs font-medium text-primary hover:text-primary-dark transition-colors"
                                aria-expanded={row.expanded}
                              >
                                {row.expanded
                                  ? 'Show fewer tribunal appeal documents'
                                  : `Show ${row.runLength - 1} more tribunal appeal documents`}
                              </button>
                            </div>
                          </div>
                        </div>
                      </li>
                    );
                  }

                  const { event, idx } = row;
                  const dot = dotStyleForEvent(event);
                  return (
                  <li key={`event-${event.date}-${event.display_title || event.title}-${idx}`}>
                    <div className="relative pb-8">
                      {connector}
                      <div className="relative flex space-x-3">
                        <div>
                          <span className={`h-8 w-8 rounded-full flex items-center justify-center ring-4 ring-white ${dot.ring}`}>
                            <div className={`h-2.5 w-2.5 rounded-full ${dot.dot}`} />
                          </span>
                        </div>
                        <div className="min-w-0 flex-1 pt-1">
                          <p className="text-sm font-medium text-gray-900">
                            {event.display_title || event.title}
                          </p>
                          <p className="text-xs text-gray-500 mt-0.5">
                            {formatDate(event.date)}
                          </p>
                          {event.is_appeal && (event.appeal_filed_by || event.appeal_confidentiality) && (
                            <p className="text-xs text-gray-500 mt-0.5">
                              {[event.appeal_filed_by, event.appeal_confidentiality].filter(Boolean).join(' · ')}
                            </p>
                          )}
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
                  );
                })}
              </ul>
            </div>
          </div>
        )}

        {/* Similar Mergers */}
        {merger.similar_mergers && merger.similar_mergers.length > 0 && (
          <div className={`${CARD} p-6 mt-6`}>
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
                        ...(similar.acquirers || []),
                        '→',
                        ...(similar.targets || []),
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
