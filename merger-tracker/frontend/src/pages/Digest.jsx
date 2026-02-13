import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import LoadingSpinner from '../components/LoadingSpinner';
import ExternalLinkIcon from '../components/ExternalLinkIcon';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { formatDate } from '../utils/dates';
import { dataCache } from '../utils/dataCache';

function Digest() {
  const [digest, setDigest] = useState(() => dataCache.get('digest') || null);
  const [loading, setLoading] = useState(() => !dataCache.has('digest'));
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDigest();
  }, []);

  const fetchDigest = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.digest);
      if (!response.ok) throw new Error('Failed to fetch digest');
      const data = await response.json();
      dataCache.set('digest', data);
      setDigest(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const formatDateRange = (startDate, endDate) => {
    if (!startDate || !endDate) return '';

    const start = new Date(startDate);
    const end = new Date(endDate);

    const startDay = start.getDate();
    const endDay = end.getDate();
    const startMonth = start.toLocaleDateString('en-AU', { month: 'long' });
    const endMonth = end.toLocaleDateString('en-AU', { month: 'long' });
    const year = end.getFullYear();

    if (startMonth === endMonth) {
      // Same month: "5-12 February 2026"
      return `${startDay}-${endDay} ${startMonth} ${year}`;
    } else {
      // Different months: "27 February to 4 March 2026"
      return `${startDay} ${startMonth} to ${endDay} ${endMonth} ${year}`;
    }
  };

  const getFirstParagraph = (description) => {
    if (!description) return '';

    // Split by double newline or first paragraph
    const paragraphs = description.split('\n\n').map(p => p.trim()).filter(p => p);

    // Skip single-word paragraphs (especially ones like **Acquisition**)
    for (const para of paragraphs) {
      // Remove markdown formatting to check word count
      const plainText = para.replace(/\*\*/g, '').replace(/\*/g, '').trim();
      const wordCount = plainText.split(/\s+/).length;

      // If the paragraph has more than one word, use it
      if (wordCount > 1) {
        return para;
      }
    }

    // If all paragraphs are single words, just return the first one
    return paragraphs[0] || '';
  };

  const getDeterminationPdf = (events) => {
    if (!events || events.length === 0) return null;

    // Find the most recent determination event with a URL
    const determinationEvent = events
      .filter(e => e.display_title && e.display_title.includes('determination') && e.url_gh)
      .sort((a, b) => new Date(b.date) - new Date(a.date))[0];

    return determinationEvent?.url_gh || null;
  };

  const scrollToSection = (sectionId) => {
    const element = document.getElementById(sectionId);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const renderNewMergersTable = (mergers) => {
    if (mergers.length === 0) {
      return (
        <div id="new-mergers" className="bg-white rounded-2xl border-l-4 border-l-new-merger border-t border-r border-b border-gray-100 shadow-card overflow-hidden">
          <div className="px-5 sm:px-6 py-4 border-b border-new-merger-light/20 bg-gradient-to-r from-new-merger-pale/50 to-transparent">
            <h2 className="text-lg font-semibold text-gray-900">New mergers</h2>
          </div>
          <div className="px-5 sm:px-6 py-4">
            <p className="text-new-merger/70 text-sm">No new mergers this week</p>
          </div>
        </div>
      );
    }

    return (
      <div id="new-mergers" className="bg-white rounded-2xl border-l-4 border-l-new-merger border-t border-r border-b border-gray-100 shadow-card overflow-hidden">
        <div className="px-5 sm:px-6 py-4 border-b border-new-merger-light/20 bg-gradient-to-r from-new-merger-pale/50 to-transparent">
          <h2 className="text-lg font-semibold text-gray-900">New mergers</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-100">
            <thead>
              <tr className="bg-gray-50/80">
                <th scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Merger
                </th>
                <th scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Notification date
                </th>
                <th scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Summary
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {mergers.map((merger) => (
                <tr key={merger.merger_id} className="relative hover:bg-new-merger-pale/40 transition-colors">
                  <td className="px-5 sm:px-6 py-4 text-sm text-gray-900">
                    <Link
                      to={`/mergers/${merger.merger_id}`}
                      className="text-new-merger hover:text-new-merger-dark font-medium transition-colors after:absolute after:inset-0"
                      aria-label={`View merger details for ${merger.merger_name}`}
                    >
                      {merger.merger_name}
                    </Link>
                    <div className="text-xs text-gray-400 mt-0.5">
                      <span>{merger.merger_id}</span>
                    </div>
                  </td>
                  <td className="px-5 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {merger.effective_notification_datetime
                      ? formatDate(merger.effective_notification_datetime)
                      : 'N/A'}
                  </td>
                  <td className="px-5 sm:px-6 py-4 text-sm text-gray-600">
                    <ReactMarkdown className="prose prose-sm max-w-none">
                      {getFirstParagraph(merger.merger_description)}
                    </ReactMarkdown>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const renderApprovedMergersTable = (mergers) => {
    if (mergers.length === 0) {
      return (
        <div id="mergers-approved" className="bg-white rounded-2xl border-l-4 border-l-cleared border-t border-r border-b border-gray-100 shadow-card overflow-hidden">
          <div className="px-5 sm:px-6 py-4 border-b border-cleared-light/20 bg-gradient-to-r from-cleared-pale/50 to-transparent">
            <h2 className="text-lg font-semibold text-gray-900">Mergers approved</h2>
          </div>
          <div className="px-5 sm:px-6 py-4">
            <p className="text-cleared/70 text-sm">No mergers approved this week</p>
          </div>
        </div>
      );
    }

    return (
      <div id="mergers-approved" className="bg-white rounded-2xl border-l-4 border-l-cleared border-t border-r border-b border-gray-100 shadow-card overflow-hidden">
        <div className="px-5 sm:px-6 py-4 border-b border-cleared-light/20 bg-gradient-to-r from-cleared-pale/50 to-transparent">
          <h2 className="text-lg font-semibold text-gray-900">Mergers approved</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-100">
            <thead>
              <tr className="bg-gray-50/80">
                <th scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Merger
                </th>
                <th scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Determination date
                </th>
                <th scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Determination
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {mergers.map((merger) => {
                const pdfUrl = getDeterminationPdf(merger.events);
                const determination = merger.accc_determination || merger.phase_1_determination || merger.phase_2_determination || 'Approved';
                return (
                  <tr key={merger.merger_id} className="relative hover:bg-cleared-pale/40 transition-colors">
                    <td className="px-5 sm:px-6 py-4 text-sm text-gray-900">
                      <div className="flex items-start gap-2">
                        <Link
                          to={`/mergers/${merger.merger_id}`}
                          className="text-cleared hover:text-cleared-dark font-medium transition-colors after:absolute after:inset-0"
                          aria-label={`View merger details for ${merger.merger_name}`}
                        >
                          {merger.merger_name}
                        </Link>
                        {merger.is_waiver && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200/60 relative z-10">
                            Waiver
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-gray-400 mt-0.5">
                        <span>{merger.merger_id}</span>
                      </div>
                    </td>
                    <td className="px-5 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {merger.determination_publication_date
                        ? formatDate(merger.determination_publication_date)
                        : 'N/A'}
                    </td>
                    <td className="px-5 sm:px-6 py-4 whitespace-nowrap text-sm">
                      {pdfUrl ? (
                        <a
                          href={pdfUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-cleared hover:text-cleared-dark font-medium transition-colors relative z-10 inline-flex items-center gap-1"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {determination}
                          <ExternalLinkIcon className="h-3.5 w-3.5" />
                        </a>
                      ) : (
                        <span className="text-gray-600">{determination}</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const renderDeclinedMergersTable = (mergers) => {
    if (mergers.length === 0) {
      return (
        <div id="mergers-declined" className="bg-white rounded-2xl border-l-4 border-l-declined border-t border-r border-b border-gray-100 shadow-card overflow-hidden">
          <div className="px-5 sm:px-6 py-4 border-b border-declined-light/20 bg-gradient-to-r from-declined-pale/50 to-transparent">
            <h2 className="text-lg font-semibold text-gray-900">Mergers declined</h2>
          </div>
          <div className="px-5 sm:px-6 py-4">
            <p className="text-declined/70 text-sm">No mergers declined this week</p>
          </div>
        </div>
      );
    }

    return (
      <div id="mergers-declined" className="bg-white rounded-2xl border-l-4 border-l-declined border-t border-r border-b border-gray-100 shadow-card overflow-hidden">
        <div className="px-5 sm:px-6 py-4 border-b border-declined-light/20 bg-gradient-to-r from-declined-pale/50 to-transparent">
          <h2 className="text-lg font-semibold text-gray-900">Mergers declined</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-100">
            <thead>
              <tr className="bg-gray-50/80">
                <th scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Merger
                </th>
                <th scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Determination date
                </th>
                <th scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Determination
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {mergers.map((merger) => {
                const pdfUrl = getDeterminationPdf(merger.events);
                const determination = merger.accc_determination || merger.phase_1_determination || merger.phase_2_determination || 'Not approved';
                return (
                  <tr key={merger.merger_id} className="relative hover:bg-declined-pale/40 transition-colors">
                    <td className="px-5 sm:px-6 py-4 text-sm text-gray-900">
                      <div className="flex items-start gap-2">
                        <Link
                          to={`/mergers/${merger.merger_id}`}
                          className="text-declined hover:text-declined-dark font-medium transition-colors after:absolute after:inset-0"
                          aria-label={`View merger details for ${merger.merger_name}`}
                        >
                          {merger.merger_name}
                        </Link>
                        {merger.is_waiver && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200/60 relative z-10">
                            Waiver
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-gray-400 mt-0.5">
                        <span>{merger.merger_id}</span>
                      </div>
                    </td>
                    <td className="px-5 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {merger.determination_publication_date
                        ? formatDate(merger.determination_publication_date)
                        : 'N/A'}
                    </td>
                    <td className="px-5 sm:px-6 py-4 whitespace-nowrap text-sm">
                      {pdfUrl ? (
                        <a
                          href={pdfUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-declined hover:text-declined-dark font-medium transition-colors relative z-10 inline-flex items-center gap-1"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {determination}
                          <ExternalLinkIcon className="h-3.5 w-3.5" />
                        </a>
                      ) : (
                        <span className="text-gray-600">{determination}</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const renderOngoingPhase1Table = (mergers) => {
    if (mergers.length === 0) {
      return (
        <div id="ongoing-phase-1" className="bg-white rounded-2xl border-l-4 border-l-phase-1 border-t border-r border-b border-gray-100 shadow-card overflow-hidden">
          <div className="px-5 sm:px-6 py-4 border-b border-phase-1-light/20 bg-gradient-to-r from-phase-1-pale/50 to-transparent">
            <h2 className="text-lg font-semibold text-gray-900">Ongoing - phase 1 - initial assessment</h2>
          </div>
          <div className="px-5 sm:px-6 py-4">
            <p className="text-phase-1/70 text-sm">No ongoing phase 1 mergers</p>
          </div>
        </div>
      );
    }

    return (
      <div id="ongoing-phase-1" className="bg-white rounded-2xl border-l-4 border-l-phase-1 border-t border-r border-b border-gray-100 shadow-card overflow-hidden">
        <div className="px-5 sm:px-6 py-4 border-b border-phase-1-light/20 bg-gradient-to-r from-phase-1-pale/50 to-transparent">
          <h2 className="text-lg font-semibold text-gray-900">Ongoing - phase 1 - initial assessment</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-100">
            <thead>
              <tr className="bg-gray-50/80">
                <th scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Merger
                </th>
                <th scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Notification date
                </th>
                <th scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Determination due date
                </th>
                <th scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Summary
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {mergers.map((merger) => (
                <tr key={merger.merger_id} className="relative hover:bg-phase-1-pale/40 transition-colors">
                  <td className="px-5 sm:px-6 py-4 text-sm text-gray-900">
                    <Link
                      to={`/mergers/${merger.merger_id}`}
                      className="text-phase-1 hover:text-phase-1-dark font-medium transition-colors after:absolute after:inset-0"
                      aria-label={`View merger details for ${merger.merger_name}`}
                    >
                      {merger.merger_name}
                    </Link>
                    <div className="text-xs text-gray-400 mt-0.5">
                      <span>{merger.merger_id}</span>
                    </div>
                  </td>
                  <td className="px-5 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {merger.effective_notification_datetime
                      ? formatDate(merger.effective_notification_datetime)
                      : 'N/A'}
                  </td>
                  <td className="px-5 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {merger.end_of_determination_period
                      ? formatDate(merger.end_of_determination_period)
                      : 'N/A'}
                  </td>
                  <td className="px-5 sm:px-6 py-4 text-sm text-gray-600">
                    <ReactMarkdown className="prose prose-sm max-w-none">
                      {getFirstParagraph(merger.merger_description)}
                    </ReactMarkdown>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const renderOngoingPhase2Table = (mergers) => {
    if (mergers.length === 0) {
      return (
        <div id="ongoing-phase-2" className="bg-white rounded-2xl border-l-4 border-l-phase-2 border-t border-r border-b border-gray-100 shadow-card overflow-hidden">
          <div className="px-5 sm:px-6 py-4 border-b border-phase-2-light/20 bg-gradient-to-r from-phase-2-pale/50 to-transparent">
            <h2 className="text-lg font-semibold text-gray-900">Ongoing - phase 2 - detailed assessment</h2>
          </div>
          <div className="px-5 sm:px-6 py-4">
            <p className="text-phase-2/70 text-sm">No ongoing phase 2 mergers</p>
          </div>
        </div>
      );
    }

    return (
      <div id="ongoing-phase-2" className="bg-white rounded-2xl border-l-4 border-l-phase-2 border-t border-r border-b border-gray-100 shadow-card overflow-hidden">
        <div className="px-5 sm:px-6 py-4 border-b border-phase-2-light/20 bg-gradient-to-r from-phase-2-pale/50 to-transparent">
          <h2 className="text-lg font-semibold text-gray-900">Ongoing - phase 2 - detailed assessment</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-100">
            <thead>
              <tr className="bg-gray-50/80">
                <th scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Merger
                </th>
                <th scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Notification date
                </th>
                <th scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Determination due date
                </th>
                <th scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Summary
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {mergers.map((merger) => (
                <tr key={merger.merger_id} className="relative hover:bg-phase-2-pale/40 transition-colors">
                  <td className="px-5 sm:px-6 py-4 text-sm text-gray-900">
                    <Link
                      to={`/mergers/${merger.merger_id}`}
                      className="text-phase-2 hover:text-phase-2-dark font-medium transition-colors after:absolute after:inset-0"
                      aria-label={`View merger details for ${merger.merger_name}`}
                    >
                      {merger.merger_name}
                    </Link>
                    <div className="text-xs text-gray-400 mt-0.5">
                      <span>{merger.merger_id}</span>
                    </div>
                  </td>
                  <td className="px-5 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {merger.effective_notification_datetime
                      ? formatDate(merger.effective_notification_datetime)
                      : 'N/A'}
                  </td>
                  <td className="px-5 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {merger.end_of_determination_period
                      ? formatDate(merger.end_of_determination_period)
                      : 'N/A'}
                  </td>
                  <td className="px-5 sm:px-6 py-4 text-sm text-gray-600">
                    <ReactMarkdown className="prose prose-sm max-w-none">
                      {getFirstParagraph(merger.merger_description)}
                    </ReactMarkdown>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;
  if (!digest) return null;

  const dateRange = formatDateRange(digest.period_start, digest.period_end);

  return (
    <div className="min-h-screen bg-gray-50">
      <SEO
        title="Catch me up - ACCC Merger Tracker"
        description="Weekly digest of ACCC merger activity including new deals, cleared deals, declined deals, and ongoing assessments"
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Catch me up</h1>
          <p className="text-gray-600">
            Weekly digest of merger activity from {dateRange}
          </p>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
          <button
            onClick={() => scrollToSection('new-mergers')}
            className="bg-gradient-to-br from-new-merger-pale to-new-merger-pale/50 rounded-lg shadow-card border border-new-merger-light/30 p-4 hover:shadow-card-hover hover:scale-105 transition-all cursor-pointer text-left group"
          >
            <div className="text-2xl font-bold text-new-merger group-hover:text-new-merger-dark transition-colors">
              {digest.new_deals_notified.length}
            </div>
            <div className="text-sm text-new-merger-dark/80 font-medium">New deals notified</div>
          </button>
          <button
            onClick={() => scrollToSection('mergers-approved')}
            className="bg-gradient-to-br from-cleared-pale to-cleared-pale/50 rounded-lg shadow-card border border-cleared-light/30 p-4 hover:shadow-card-hover hover:scale-105 transition-all cursor-pointer text-left group"
          >
            <div className="text-2xl font-bold text-cleared group-hover:text-cleared-dark transition-colors">
              {digest.deals_cleared.length}
            </div>
            <div className="text-sm text-cleared-dark/80 font-medium">Deals cleared</div>
          </button>
          <button
            onClick={() => scrollToSection('mergers-declined')}
            className="bg-gradient-to-br from-declined-pale to-declined-pale/50 rounded-lg shadow-card border border-declined-light/30 p-4 hover:shadow-card-hover hover:scale-105 transition-all cursor-pointer text-left group"
          >
            <div className="text-2xl font-bold text-declined group-hover:text-declined-dark transition-colors">
              {digest.deals_declined.length}
            </div>
            <div className="text-sm text-declined-dark/80 font-medium">Deals declined</div>
          </button>
          <button
            onClick={() => scrollToSection('ongoing-phase-1')}
            className="bg-gradient-to-br from-phase-1-pale to-phase-1-pale/50 rounded-lg shadow-card border border-phase-1-light/30 p-4 hover:shadow-card-hover hover:scale-105 transition-all cursor-pointer text-left group"
          >
            <div className="text-2xl font-bold text-phase-1 group-hover:text-phase-1-dark transition-colors">
              {digest.ongoing_phase_1.length}
            </div>
            <div className="text-sm text-phase-1-dark/80 font-medium">Ongoing phase 1</div>
          </button>
          <button
            onClick={() => scrollToSection('ongoing-phase-2')}
            className="bg-gradient-to-br from-phase-2-pale to-phase-2-pale/50 rounded-lg shadow-card border border-phase-2-light/30 p-4 hover:shadow-card-hover hover:scale-105 transition-all cursor-pointer text-left group"
          >
            <div className="text-2xl font-bold text-phase-2 group-hover:text-phase-2-dark transition-colors">
              {digest.ongoing_phase_2.length}
            </div>
            <div className="text-sm text-phase-2-dark/80 font-medium">Ongoing phase 2</div>
          </button>
        </div>

        {/* Tables */}
        <div className="space-y-6">
          {renderNewMergersTable(digest.new_deals_notified)}
          {renderApprovedMergersTable(digest.deals_cleared)}
          {renderDeclinedMergersTable(digest.deals_declined)}
          {renderOngoingPhase1Table(digest.ongoing_phase_1)}
          {renderOngoingPhase2Table(digest.ongoing_phase_2)}
        </div>
      </div>
    </div>
  );
}

export default Digest;
