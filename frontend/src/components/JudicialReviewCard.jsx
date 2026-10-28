import { FaBalanceScale } from 'react-icons/fa';
import ExternalLinkIcon from './ExternalLinkIcon';
import { formatDateLong } from '../utils/dates';
import {
  JUDICIAL_REVIEW_STATUS,
  judicialReviewState,
  nextJudicialReviewHearing,
} from '../constants/judicialReview';

/**
 * A Federal Court judicial review of the ACCC's decision, linking to its file
 * on the Commonwealth Courts Portal: who sought it and when, how it ended once
 * it has, and while it runs, the next hearing.
 *
 * Styled and built as the Tribunal appeal cards beside it — the whole card is
 * the link. The court's listings, orders and judgments and the documents filed
 * are all on the timeline, so the card doesn't repeat them.
 */
function JudicialReviewCard({ review }) {
  const concluded = review.status === JUDICIAL_REVIEW_STATUS.CONCLUDED;
  const nextHearing = concluded ? null : nextJudicialReviewHearing(review);
  const heading = `${review.applicant ? `Judicial review requested by ${review.applicant}` : 'Judicial review requested'}${
    review.filed_date ? ` on ${formatDateLong(review.filed_date)}` : ''
  }`;
  const ending = concluded
    ? `${judicialReviewState(review)}${review.concluded_date ? ` on ${formatDateLong(review.concluded_date)}` : ''}`
    : null;
  const body = (
    <>
      <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-amber-100 flex items-center justify-center">
        <FaBalanceScale className="h-4 w-4 text-amber-700" aria-hidden="true" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900">{heading}</p>
        <p className="text-xs text-gray-500 mt-0.5">
          {['Federal Court of Australia', review.case_number, ending].filter(Boolean).join(' · ')}
        </p>
        {nextHearing && (
          <p className="text-xs text-gray-700 mt-1">
            Next hearing {formatDateLong(nextHearing.date)}
            {[nextHearing.reason, nextHearing.time, nextHearing.location]
              .filter(Boolean)
              .map((part) => ` · ${part}`)
              .join('')}
          </p>
        )}
      </div>
    </>
  );
  const className =
    'flex items-center gap-3 bg-amber-50/80 rounded-2xl border border-amber-200/60 shadow-card p-4 mb-6';

  if (!review.case_url) return <div className={className}>{body}</div>;
  return (
    <a
      href={review.case_url}
      target="_blank"
      rel="noopener noreferrer"
      className={`${className} hover:bg-amber-50 hover:border-amber-300/60 transition-all group`}
    >
      {/* No aria-label: the card's own text, outcome and next hearing
          included, is the link's name, with where it goes appended. */}
      {body}
      <span className="sr-only">(Commonwealth Courts Portal, opens in new tab)</span>
      <ExternalLinkIcon className="h-3.5 w-3.5 text-amber-700 flex-shrink-0" />
    </a>
  );
}

export default JudicialReviewCard;
