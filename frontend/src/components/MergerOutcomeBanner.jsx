import { FaBan, FaCheck, FaTimes } from 'react-icons/fa';
import ExternalLinkIcon from './ExternalLinkIcon';
import { MERGER_STATUS } from '../constants/mergerStatus';
import { APPEAL_OUTCOME_LABELS, APPEAL_STATUS } from '../constants/appeal';
import { getOutcomeBannerStyle } from '../constants/outcomeBanner';
import { formatDateLong } from '../utils/dates';
import {
  acccDecisionSentence,
  durationSentence,
  getDecidedOutcome,
  getDeterminationDocUrl,
} from '../utils/mergerOutcome';

const OUTCOME_ICONS = {
  [MERGER_STATUS.APPROVED]: FaCheck,
  [MERGER_STATUS.NOT_OPPOSED]: FaCheck,
  [MERGER_STATUS.NOT_APPROVED]: FaTimes,
  [MERGER_STATUS.DECLINED]: FaTimes,
  [MERGER_STATUS.ASSESSMENT_CEASED]: FaBan,
};

/**
 * The headline block on a decided merger's detail page: a band in the outcome's
 * colour stating the result in one word, what the ACCC actually decided, and
 * how long it took. Renders nothing while a matter is still under assessment,
 * where the header's progress bar and status badge carry the story instead.
 *
 * It is meant to be dropped inside the detail header card's `p-6` padding — the
 * negative margin runs the colour to the card's edges so it reads as the card's
 * own state rather than a box sitting within it.
 */
function MergerOutcomeBanner({ merger }) {
  const decided = getDecidedOutcome(merger);
  if (!decided) return null;

  const { outcome, appealSuffix, ceased } = decided;
  const style = getOutcomeBannerStyle(outcome);
  const Icon = OUTCOME_ICONS[outcome] || FaCheck;

  const startDate =
    merger.effective_notification_datetime || merger.original_notification_datetime;
  const decidedDate = ceased ? merger.ceased_date : merger.determination_publication_date;

  // Mirrors StatusBadge: a stale conditions flag on any other outcome stays
  // hidden rather than reading as a conditional clearance.
  const showConditions =
    Boolean(merger.has_conditions) && merger.accc_determination === MERGER_STATUS.APPROVED;
  const duration = durationSentence(merger, startDate, decidedDate);
  const docUrl = getDeterminationDocUrl(merger);

  // A concluded appeal gets its own line: the headline already shows the
  // outcome that now stands, this says who changed it and when.
  const concludedAppeal =
    merger.appeal?.status === APPEAL_STATUS.CONCLUDED ? merger.appeal : null;
  const appealLine = concludedAppeal
    ? `Australian Competition Tribunal: ${
        APPEAL_OUTCOME_LABELS[concludedAppeal.outcome] || 'appeal concluded'
      }${concludedAppeal.concluded_date ? ` on ${formatDateLong(concludedAppeal.concluded_date)}` : ''}.`
    : null;

  return (
    <section
      aria-labelledby="merger-outcome-heading"
      className={`-mx-6 mt-6 px-6 py-5 ${style.bg} ${style.text}`}
    >
      {/* The icon stays beside the outcome at every width; only the document
          link drops below it on a narrow screen. */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
        <div className="flex items-start gap-4 min-w-0 flex-1">
          <span
            className={`flex-shrink-0 flex items-center justify-center w-12 h-12 rounded-2xl ${style.chip}`}
          >
            <Icon className="w-6 h-6" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              {/* aria-label so the heading reads as "Outcome: Approved" rather
                  than a bare adjective in a screen reader's heading list. */}
              <h2
                id="merger-outcome-heading"
                aria-label={`Outcome: ${outcome}`}
                className="text-2xl sm:text-3xl font-bold tracking-tight"
              >
                {outcome}
              </h2>
              {showConditions && (
                <span
                  className={`inline-flex items-center px-2 py-1 rounded-lg text-xs font-semibold ${style.chip}`}
                >
                  with conditions
                </span>
              )}
              {appealSuffix && (
                <span
                  className={`inline-flex items-center px-2 py-1 rounded-lg text-xs font-semibold ${style.chip}`}
                >
                  {appealSuffix}
                </span>
              )}
            </div>
            <p className={`mt-1.5 text-sm ${style.sub}`}>
              {acccDecisionSentence(merger, decidedDate)}
            </p>
            {appealLine && <p className={`mt-1 text-sm ${style.sub}`}>{appealLine}</p>}
            {duration && <p className={`mt-1 text-sm ${style.sub}`}>{duration}</p>}
          </div>
        </div>
        {docUrl && (
          <a
            href={docUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={`self-start inline-flex items-center gap-1.5 flex-shrink-0 px-3 py-2 rounded-xl text-sm font-medium transition-colors ${style.chip} ${style.chipHover} ${style.focus}`}
          >
            Read the reasons
            <ExternalLinkIcon className="h-3.5 w-3.5" />
            <span className="sr-only">(opens in new tab)</span>
          </a>
        )}
      </div>
    </section>
  );
}

export default MergerOutcomeBanner;
