import { useState, useCallback } from 'react';
import { formatDate, getDaysRemaining, isDatePast } from '../utils/dates';
import CollapsibleCard from './CollapsibleCard';
import ExternalLinkIcon from './ExternalLinkIcon';
import { API_ENDPOINTS } from '../config';

const QuestionnaireIcon = () => (
  <svg className="h-5 w-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

function QuestionnaireSection({ mergerId, events }) {
  const [questionnaire, setQuestionnaire] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const fetchQuestionnaire = useCallback(async () => {
    if (questionnaire || loading) return;
    setLoading(true);
    setError(false);
    try {
      const response = await fetch(API_ENDPOINTS.questionnaire(mergerId));
      if (!response.ok) throw new Error('Failed to load');
      const data = await response.json();
      setQuestionnaire(data);
      setSelectedIndex(0);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [mergerId, questionnaire, loading]);

  const renderDeadlineCountdown = (deadlineIso) => {
    if (isDatePast(deadlineIso)) return 'responses now closed';
    const daysRemaining = getDaysRemaining(deadlineIso + 'T12:00:00Z');
    if (daysRemaining === null) return null;
    if (daysRemaining === 0) return 'today';
    return `${daysRemaining} day${daysRemaining === 1 ? '' : 's'}`;
  };

  // Find all questionnaire document links from events (some mergers have multiple)
  const questionnaireEvents = (events || [])
    .filter(
      (event) =>
        event.url_gh &&
        (event.title?.toLowerCase().includes('questionnaire') ||
          event.display_title?.toLowerCase().includes('questionnaire'))
    )
    .sort((a, b) => new Date(b.date) - new Date(a.date));

  // Strip re-download suffixes (_0, _1 …) before the extension so that
  // "EG - Questionnaire_0.pdf" matches the event URL "EG - Questionnaire.pdf".
  const normalizeFilename = (name) =>
    (name || '').replace(/_\d+(\.[^.]+)$/, '$1');

  // Return the questionnaire events that match this version's document.
  // Try exact filename first so that same-name re-releases (e.g. MN-30003,
  // where _0.pdf and the base file are different events) each get their own
  // link. Only fall back to normalised matching when there is no exact hit,
  // which handles the case where the scraper added a _N suffix but the event
  // still points to the original name.
  const getVersionEvents = (versionData) => {
    if (!versionData?.file_name) return questionnaireEvents;

    const exact = questionnaireEvents.filter((event) => {
      const basename = decodeURIComponent((event.url_gh || '').split('/').pop());
      return basename === versionData.file_name;
    });
    if (exact.length > 0) return exact;

    const normalized = normalizeFilename(versionData.file_name);
    return questionnaireEvents.filter((event) => {
      const basename = decodeURIComponent((event.url_gh || '').split('/').pop());
      return normalizeFilename(basename) === normalized;
    });
  };

  // Label a version tab with its release date (from the matching event),
  // falling back to the deadline date, then a generic ordinal.
  const getVersionLabel = (versionData, index, total) => {
    const matched = getVersionEvents(versionData);
    if (matched.length > 0) return formatDate(matched[0].date);
    if (versionData?.deadline_iso) return formatDate(versionData.deadline_iso + 'T12:00:00Z');
    return `Questionnaire ${total - index}`;
  };

  return (
    <CollapsibleCard
      icon={<QuestionnaireIcon />}
      iconBgClass="bg-amber-100"
      title="ACCC Questionnaire"
      subtitle="Click to view the questions asked by the ACCC"
      onExpand={fetchQuestionnaire}
    >
      {loading && (
        <div className="flex items-center gap-2 mt-4 text-sm text-gray-400">
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading questionnaire...
        </div>
      )}

      {error && (
        <div className="mt-4 text-sm text-gray-400">
          Could not load questionnaire data.{' '}
          <button
            type="button"
            onClick={fetchQuestionnaire}
            className="text-primary hover:text-primary-dark font-medium"
          >
            Retry
          </button>
        </div>
      )}

      {questionnaire && (() => {
        const allVersions = questionnaire.all_questionnaires || [questionnaire];
        const active = allVersions[selectedIndex] ?? allVersions[0];
        return (
          <>
            {allVersions.length > 1 && (
              <div className="flex gap-2 mt-4 flex-wrap">
                {allVersions.map((q, i) => (
                  <button
                    key={q.deadline_iso ?? i}
                    type="button"
                    onClick={() => setSelectedIndex(i)}
                    className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                      i === selectedIndex
                        ? 'bg-amber-100 border-amber-300 text-amber-800 font-medium'
                        : 'border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-700'
                    }`}
                  >
                    {getVersionLabel(q, i, allVersions.length)}
                  </button>
                ))}
              </div>
            )}
            {(() => {
              const activeEvents = getVersionEvents(active);
              return (
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mt-4 mb-4">
                  <p className="text-xs text-gray-400">
                    {active.questions_count} question{active.questions_count !== 1 ? 's' : ''}
                    {active.deadline_iso && (
                      <span>
                        {' · Responses due '}
                        {formatDate(active.deadline_iso + 'T12:00:00Z')}
                        {(() => {
                          const countdown = renderDeadlineCountdown(active.deadline_iso);
                          return countdown ? ` (${countdown})` : '';
                        })()}
                      </span>
                    )}
                  </p>
                  {activeEvents.map((event) => (
                    <a
                      key={event.url_gh}
                      href={event.url_gh}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-primary hover:text-primary-dark transition-colors font-medium"
                    >
                      View document
                      <ExternalLinkIcon className="h-3 w-3" />
                    </a>
                  ))}
                </div>
              );
            })()}
            <ol className="space-y-3">
              {active.questions.map((q, idx) => {
                const prevSection = idx > 0 ? active.questions[idx - 1].section : null;
                const showSectionHeader = q.section && q.section !== prevSection;
                return (
                  <li key={q.number}>
                    {showSectionHeader && (
                      <p className={`text-xs font-semibold text-gray-500 uppercase tracking-wider ${idx > 0 ? 'mt-3' : ''} mb-3`}>
                        {q.section}
                      </p>
                    )}
                    <div className="flex gap-3">
                      <span className="flex-shrink-0 w-6 h-6 rounded-full bg-gray-100 text-gray-500 text-xs font-medium flex items-center justify-center mt-0.5">
                        {q.number}
                      </span>
                      <p className="text-sm text-gray-600 leading-relaxed">{q.text}</p>
                    </div>
                  </li>
                );
              })}
            </ol>
          </>
        );
      })()}
    </CollapsibleCard>
  );
}

export default QuestionnaireSection;
