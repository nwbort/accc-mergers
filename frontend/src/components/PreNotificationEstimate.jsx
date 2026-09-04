import { useState } from 'react';
import { Link } from 'react-router';
import { FaRegQuestionCircle } from 'react-icons/fa';
import { formatDateLong } from '../utils/dates';
import {
  getPreNotificationEstimate,
  PRE_NOTIFICATION_AFTER,
  PRE_NOTIFICATION_BEFORE,
  PRE_NOTIFICATION_CONFIDENCE,
  PRE_NOTIFICATION_NONE,
} from '../utils/preNotification';

/** What the question mark means, said in full wherever there's room to say it. */
const CORRECTION_PROMPT = 'Not quite right? Let us know what it should be';

/**
 * How much weight to put on the estimate, worn as the colour of the dotted rule
 * under the date it qualifies: the settled green, the phase-1 amber, then grey
 * where the date is barely pinned down at all. Deliberately not red — on this
 * callout red belongs to the "tell us it's wrong" link, and a shaky estimate
 * isn't an error.
 *
 * The rule is dotted rather than solid so it reads as a hedge on the date
 * rather than as a link, and the text above it keeps its own colour: the
 * sentence says the same thing however well evidenced it is.
 */
const CONFIDENCE_UNDERLINES = {
  // Deep shades, not the 500s: the rule is the only thing carrying the rating
  // on screen, so it has to clear 3:1 against the card the way any meaningful
  // non-text mark does (WCAG 1.4.11).
  [PRE_NOTIFICATION_CONFIDENCE.HIGH]: 'decoration-emerald-700',
  [PRE_NOTIFICATION_CONFIDENCE.MEDIUM]: 'decoration-amber-700',
  [PRE_NOTIFICATION_CONFIDENCE.LOW]: 'decoration-gray-500',
};

const CONFIDENCE_LABELS = {
  [PRE_NOTIFICATION_CONFIDENCE.HIGH]: 'High confidence',
  [PRE_NOTIFICATION_CONFIDENCE.MEDIUM]: 'Medium confidence',
  [PRE_NOTIFICATION_CONFIDENCE.LOW]: 'Low confidence',
};

/**
 * The part of the claim the confidence is about — the date, or the whole thing
 * where there is no date — underlined in the colour of its rating, and naming
 * that rating when asked: on hover or keyboard focus with a pointer, on a tap
 * with a finger.
 *
 * A native `title` would strand the wording on touch, where there is no hover,
 * so the label is a real element toggled by the handlers a tap fires. The
 * rating rides in the accessible name too, since neither hovering nor reading a
 * colour is available to everyone.
 */
function ConfidenceMark({ confidence, children }) {
  const [shown, setShown] = useState(false);
  const label = CONFIDENCE_LABELS[confidence];

  return (
    <span className="relative inline-block">
      <button
        type="button"
        aria-label={`${children}, ${label.toLowerCase()}`}
        onMouseEnter={() => setShown(true)}
        onMouseLeave={() => setShown(false)}
        onFocus={() => setShown(true)}
        onBlur={() => setShown(false)}
        // Reveal rather than toggle: a tap on a touch device fires a synthetic
        // mouseenter first, and toggling would close what that just opened.
        // Moving the pointer away, or tapping elsewhere, dismisses it.
        onClick={() => setShown(true)}
        className={`underline decoration-dotted decoration-2 underline-offset-4 rounded-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary ${CONFIDENCE_UNDERLINES[confidence]}`}
      >
        {children}
      </button>
      {shown && (
        // Hidden from assistive tech: it repeats the button's own name, which
        // has already been announced.
        // Below the mark, not above: the sentence wraps on a narrow screen, and
        // above would put the label over the words it is annotating.
        <span
          aria-hidden="true"
          className="absolute top-full left-1/2 z-10 mt-2 -translate-x-1/2 whitespace-nowrap rounded-md bg-gray-900 px-2 py-1 text-xs font-medium text-white shadow-lg"
        >
          {label}
        </span>
      )}
    </span>
  );
}

/**
 * The claim, split at the part the confidence rating is about: everything up to
 * it, then the span the dotted rule goes under.
 */
const describe = ({ kind, startDate }) => {
  if (kind === PRE_NOTIFICATION_NONE) {
    return { lead: 'this merger had ', marked: 'little or no pre-notification period' };
  }
  if (kind === PRE_NOTIFICATION_AFTER) {
    return {
      lead: 'this merger entered pre-notification sometime after ',
      marked: formatDateLong(startDate),
    };
  }
  if (kind === PRE_NOTIFICATION_BEFORE) {
    return {
      lead: 'this merger entered pre-notification sometime before ',
      marked: formatDateLong(startDate),
    };
  }
  return {
    lead: 'this merger entered pre-notification around ',
    marked: formatDateLong(startDate),
  };
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
  const claim = describe(estimate);

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
          Our market intelligence suggests that {claim.lead}
          <ConfidenceMark confidence={estimate.confidence}>{claim.marked}</ConfidenceMark>
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
