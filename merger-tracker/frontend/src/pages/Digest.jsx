import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import LoadingSpinner from '../components/LoadingSpinner';
import ExternalLinkIcon from '../components/ExternalLinkIcon';
import WaiverBadge from '../components/WaiverBadge';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { formatDate } from '../utils/dates';
import { dataCache } from '../utils/dataCache';

const scrollToTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' });
};

function ScrollToTopButton() {
  return (
    <button
      onClick={scrollToTop}
      className="p-1 text-gray-400 hover:text-gray-600 transition-all"
      aria-label="Scroll to top"
      title="Back to top"
    >
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 10.5L12 3m0 0l7.5 7.5M12 3v18" />
      </svg>
    </button>
  );
}

function DigestSection({ id, title, emptyMessage, colorKey, mergers, columns, renderRow }) {
  return (
    <div id={id} className={`bg-white rounded-2xl border-l-4 border-l-${colorKey} border-t border-r border-b border-gray-100 shadow-card overflow-hidden`}>
      <div className={`px-5 sm:px-6 py-4 border-b border-${colorKey}-light/20 bg-gradient-to-r from-${colorKey}-pale/50 to-transparent`}>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
          <ScrollToTopButton />
        </div>
      </div>
      {mergers.length === 0 ? (
        <div className="px-5 sm:px-6 py-4">
          <p className={`text-${colorKey}/70 text-sm`}>{emptyMessage}</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-100">
            <thead>
              <tr className="bg-gray-50/80">
                {columns.map((col) => (
                  <th key={col} scope="col" className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {mergers.map((merger) => renderRow(merger))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function MergerNameCell({ merger, colorKey }) {
  return (
    <td className="px-5 sm:px-6 py-4 text-sm text-gray-900">
      <div className="flex items-start gap-2">
        <Link
          to={`/mergers/${merger.merger_id}`}
          className={`text-${colorKey} hover:text-${colorKey}-dark font-medium transition-colors after:absolute after:inset-0`}
          aria-label={`View merger details for ${merger.merger_name}`}
        >
          {merger.merger_name}
        </Link>
        {merger.is_waiver && <WaiverBadge className="relative z-10" />}
      </div>
      <div className="text-xs text-gray-400 mt-0.5">
        <span>{merger.merger_id}</span>
      </div>
    </td>
  );
}

function DeterminationCell({ merger, colorKey, defaultDetermination, getDeterminationPdf }) {
  const pdfUrl = getDeterminationPdf(merger.events);
  const determination = merger.accc_determination || merger.phase_1_determination || merger.phase_2_determination || defaultDetermination;
  return (
    <td className="px-5 sm:px-6 py-4 whitespace-nowrap text-sm">
      {pdfUrl ? (
        <a
          href={pdfUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={`text-${colorKey} hover:text-${colorKey}-dark font-medium transition-colors relative z-10 inline-flex items-center gap-1`}
          onClick={(e) => e.stopPropagation()}
        >
          {determination}
          <ExternalLinkIcon className="h-3.5 w-3.5" />
        </a>
      ) : (
        <span className="text-gray-600">{determination}</span>
      )}
    </td>
  );
}

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
      return `${startDay}-${endDay} ${startMonth} ${year}`;
    } else {
      return `${startDay} ${startMonth} to ${endDay} ${endMonth} ${year}`;
    }
  };

  const getFirstParagraph = (description) => {
    if (!description) return '';

    const paragraphs = description.split('\n\n').map(p => p.trim()).filter(p => p);

    for (const para of paragraphs) {
      const plainText = para.replace(/\*\*/g, '').replace(/\*/g, '').trim();
      const wordCount = plainText.split(/\s+/).length;

      if (wordCount > 1) {
        return para;
      }
    }

    return paragraphs[0] || '';
  };

  const getDeterminationPdf = (events) => {
    if (!events || events.length === 0) return null;

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

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;
  if (!digest) return null;

  const dateRange = formatDateRange(digest.period_start, digest.period_end);

  const summaryCards = [
    { id: 'new-mergers', colorKey: 'new-merger', count: digest.new_deals_notified.length, label: 'New deals notified' },
    { id: 'mergers-approved', colorKey: 'cleared', count: digest.deals_cleared.length, label: 'Deals cleared' },
    { id: 'mergers-declined', colorKey: 'declined', count: digest.deals_declined.length, label: 'Deals declined' },
    { id: 'ongoing-phase-1', colorKey: 'phase-1', count: digest.ongoing_phase_1.length, label: 'Ongoing phase 1' },
    { id: 'ongoing-phase-2', colorKey: 'phase-2', count: digest.ongoing_phase_2.length, label: 'Ongoing phase 2' },
  ];

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
          {summaryCards.map(({ id, colorKey, count, label }) => (
            <button
              key={id}
              onClick={() => scrollToSection(id)}
              className={`bg-gradient-to-br from-${colorKey}-pale to-${colorKey}-pale/50 rounded-lg shadow-card border border-${colorKey}-light/30 p-4 hover:shadow-card-hover hover:scale-105 transition-all cursor-pointer text-left group`}
            >
              <div className={`text-2xl font-bold text-${colorKey} group-hover:text-${colorKey}-dark transition-colors`}>
                {count}
              </div>
              <div className={`text-sm text-${colorKey}-dark/80 font-medium`}>{label}</div>
            </button>
          ))}
        </div>

        {/* Tables */}
        <div className="space-y-6">
          <DigestSection
            id="new-mergers"
            title="New mergers"
            emptyMessage="No new mergers this week"
            colorKey="new-merger"
            mergers={digest.new_deals_notified}
            columns={['Merger', 'Notification date', 'Summary']}
            renderRow={(merger) => (
              <tr key={merger.merger_id} className="relative hover:bg-new-merger-pale/40 transition-colors">
                <MergerNameCell merger={merger} colorKey="new-merger" />
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
            )}
          />

          <DigestSection
            id="mergers-approved"
            title="Mergers approved"
            emptyMessage="No mergers approved this week"
            colorKey="cleared"
            mergers={digest.deals_cleared}
            columns={['Merger', 'Determination date', 'Determination']}
            renderRow={(merger) => (
              <tr key={merger.merger_id} className="relative hover:bg-cleared-pale/40 transition-colors">
                <MergerNameCell merger={merger} colorKey="cleared" />
                <td className="px-5 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                  {merger.determination_publication_date
                    ? formatDate(merger.determination_publication_date)
                    : 'N/A'}
                </td>
                <DeterminationCell merger={merger} colorKey="cleared" defaultDetermination="Approved" getDeterminationPdf={getDeterminationPdf} />
              </tr>
            )}
          />

          <DigestSection
            id="mergers-declined"
            title="Mergers declined"
            emptyMessage="No mergers declined this week"
            colorKey="declined"
            mergers={digest.deals_declined}
            columns={['Merger', 'Determination date', 'Determination']}
            renderRow={(merger) => (
              <tr key={merger.merger_id} className="relative hover:bg-declined-pale/40 transition-colors">
                <MergerNameCell merger={merger} colorKey="declined" />
                <td className="px-5 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                  {merger.determination_publication_date
                    ? formatDate(merger.determination_publication_date)
                    : 'N/A'}
                </td>
                <DeterminationCell merger={merger} colorKey="declined" defaultDetermination="Not approved" getDeterminationPdf={getDeterminationPdf} />
              </tr>
            )}
          />

          <DigestSection
            id="ongoing-phase-1"
            title="Ongoing - phase 1 - initial assessment"
            emptyMessage="No ongoing phase 1 mergers"
            colorKey="phase-1"
            mergers={digest.ongoing_phase_1}
            columns={['Merger', 'Notification date', 'Determination due date', 'Summary']}
            renderRow={(merger) => (
              <tr key={merger.merger_id} className="relative hover:bg-phase-1-pale/40 transition-colors">
                <MergerNameCell merger={merger} colorKey="phase-1" />
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
            )}
          />

          <DigestSection
            id="ongoing-phase-2"
            title="Ongoing - phase 2 - detailed assessment"
            emptyMessage="No ongoing phase 2 mergers"
            colorKey="phase-2"
            mergers={digest.ongoing_phase_2}
            columns={['Merger', 'Notification date', 'Determination due date', 'Summary']}
            renderRow={(merger) => (
              <tr key={merger.merger_id} className="relative hover:bg-phase-2-pale/40 transition-colors">
                <MergerNameCell merger={merger} colorKey="phase-2" />
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
            )}
          />
        </div>
      </div>
    </div>
  );
}

export default Digest;
