import { useState } from 'react';
import { Link } from 'react-router';
import { FaRegQuestionCircle } from 'react-icons/fa';
import { formatDateLong } from '../utils/dates';
import {
  getPreNotificationEstimate,
  PRE_NOTIFICATION_AFTER,
  PRE_NOTIFICATION_NONE,
} from '../utils/preNotification';

/** What the question mark means, said in full wherever there's room to say it. */
const CORRECTION_PROMPT = 'Not quite right? Let us know what it should be';

const describe = ({ kind, startDate }) => {
  if (kind === PRE_NOTIFICATION_NONE) {
    return 'this merger had little or no pre-notification period';
  }
  if (kind === PRE_NOTIFICATION_AFTER) {
    return `this merger entered pre-notification sometime after ${formatDateLong(startDate)}`;
  }
  return `this merger entered pre-notification around ${formatDateLong(startDate)}`;
};

/**
 * The feedback page with the message box already naming the matter, so a
 * correction arrives attached to the estimate it is about rather than as an
 * orphaned "the date is wrong".
 */
const correctionLink = (mergerId) => {
  const message = `${mergerId} pre-notification estimate looks wrong. It should be `;
  return `/feedback?message=${encodeURIComponent(message)}`;
};

/**
 * The invitation to correct the estimate, kept to a muted red question mark
 * with the wording behind its tooltip. Rendered twice at different breakpoints
 * (see below) — only ever one of them visible, so only one reaches the
 * accessibility tree.
 */
function CorrectionLink({ mergerId, className, onClick }) {
  return (
    <Link
      to={correctionLink(mergerId)}
      title={CORRECTION_PROMPT}
      aria-label={`${CORRECTION_PROMPT} — pre-notification estimate for ${mergerId}`}
      onClick={onClick}
      className={`p-1 -m-1 text-red-500/60 hover:text-red-600 transition-colors ${className}`}
    >
      <FaRegQuestionCircle className="h-3.5 w-3.5" aria-hidden="true" />
    </Link>
  );
}

/**
 * Callout on the merger detail page giving the estimated start of a matter's
 * pre-notification — the stretch of ACCC engagement that precedes filing and
 * never appears on the public register. Renders nothing when the matter has no
 * usable estimate (see getPreNotificationEstimate).
 */
function PreNotificationEstimate({ merger }) {
  // Touch has no hover, so a tooltip never shows: on a narrow screen the first
  // tap spells out what the question mark is offering and the second acts on
  // it. Desktop keeps the tooltip and goes on the first click.
  const [promptShown, setPromptShown] = useState(false);
  const estimate = getPreNotificationEstimate(merger);
  if (!estimate) return null;

  const revealPrompt = (event) => {
    // Keyboard activation reports no click detail, and already had the wording
    // read out as the link's label — it goes straight through.
    if (promptShown || event.detail === 0) return;
    event.preventDefault();
    setPromptShown(true);
  };

  return (
    <div className="flex items-center gap-3 bg-gray-50/80 rounded-2xl border border-gray-200/60 shadow-card p-4 mb-6">
      <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-gray-100 flex items-center justify-center">
        <span className="text-lg leading-none" aria-hidden="true">✨</span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900">
          Our market intelligence suggests that {describe(estimate)}
          {/* On a narrow screen the sentence already fills the width, so the
              question mark trails the last word rather than stealing a column
              from the wrapping text. */}
          <CorrectionLink
            mergerId={merger.merger_id}
            onClick={revealPrompt}
            className="sm:hidden inline-flex align-baseline ml-1.5"
          />
        </p>
        {promptShown && (
          <Link
            to={correctionLink(merger.merger_id)}
            className="sm:hidden block mt-1.5 text-xs text-red-500/80 hover:text-red-600 transition-colors"
          >
            {CORRECTION_PROMPT} →
          </Link>
        )}
      </div>
      {/* With room to spare it sits out at the right edge instead, clear of the
          sentence. */}
      <CorrectionLink
        mergerId={merger.merger_id}
        className="hidden sm:inline-flex flex-shrink-0"
      />
    </div>
  );
}

export default PreNotificationEstimate;
