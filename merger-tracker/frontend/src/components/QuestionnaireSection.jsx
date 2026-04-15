import { useState, useCallback } from 'react';
import { formatDate, getBusinessDaysRemaining, isDatePast } from '../utils/dates';
import ExternalLinkIcon from './ExternalLinkIcon';
import { API_ENDPOINTS } from '../config';

function QuestionnaireSection({ mergerId, events }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [questionnaire, setQuestionnaire] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const fetchQuestionnaire = useCallback(async () => {
    if (questionnaire || loading) return;
    setLoading(true);
    setError(false);
    try {
      const response = await fetch(API_ENDPOINTS.questionnaire(mergerId));
      if (!response.ok) throw new Error('Failed to load');
      const data = await response.json();
      setQuestionnaire(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [mergerId, questionnaire, loading]);

  const handleToggle = () => {
    const willExpand = !isExpanded;
    setIsExpanded(willExpand);
    if (willExpand && !questionnaire && !error) {
      fetchQuestionnaire();
    }
  };

  const renderDeadlineCountdown = (deadlineIso) => {
    if (isDatePast(deadlineIso)) return 'responses now closed';
    const businessDaysRemaining = getBusinessDaysRemaining(deadlineIso);
    if (businessDaysRemaining === null) return null;
    if (businessDaysRemaining === 0) return 'today';
    return `${businessDaysRemaining} business day${businessDaysRemaining === 1 ? '' : 's'}`;
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

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-card mb-6 overflow-hidden">
      <button
        type="button"
        onClick={handleToggle}
        className="w-full text-left p-6 flex items-center justify-between gap-4 hover:bg-gray-50/50 transition-colors"
        aria-expanded={isExpanded}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-amber-100 flex items-center justify-center">
            <svg className="h-5 w-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider">
              ACCC Questionnaire
            </h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Click to view the questions asked by the ACCC
            </p>
          </div>
        </div>
        <svg
          className={`w-5 h-5 text-gray-400 flex-shrink-0 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isExpanded && (
        <div className="px-6 pb-6 border-t border-gray-100">
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

          {questionnaire && (
            <>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mt-4 mb-4">
                <p className="text-xs text-gray-400">
                  {questionnaire.questions_count} question{questionnaire.questions_count !== 1 ? 's' : ''}
                  {questionnaire.deadline_iso && (
                    <span>
                      {' · Responses due '}
                      {formatDate(questionnaire.deadline_iso + 'T12:00:00Z')}
                      {(() => {
                        const countdown = renderDeadlineCountdown(questionnaire.deadline_iso);
                        return countdown ? ` (${countdown})` : '';
                      })()}
                    </span>
                  )}
                </p>
                {questionnaireEvents.map((event, idx) => (
                  <a
                    key={event.url_gh}
                    href={event.url_gh}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-primary hover:text-primary-dark transition-colors font-medium"
                  >
                    {questionnaireEvents.length > 1
                      ? `View document (${formatDate(event.date)})`
                      : 'View document'}
                    <ExternalLinkIcon className="h-3 w-3" />
                  </a>
                ))}
              </div>
              <ol className="space-y-3">
                {questionnaire.questions.map((q, idx) => {
                  const prevSection = idx > 0 ? questionnaire.questions[idx - 1].section : null;
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
          )}
        </div>
      )}
    </div>
  );
}

export default QuestionnaireSection;
