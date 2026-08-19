import { Link } from 'react-router';
import { FaPencilAlt } from 'react-icons/fa';
import { formatDateLong } from '../utils/dates';
import {
  getPreNotificationEstimate,
  PRE_NOTIFICATION_AFTER,
  PRE_NOTIFICATION_NONE,
} from '../utils/preNotification';

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
 * Callout on the merger detail page giving the estimated start of a matter's
 * pre-notification — the stretch of ACCC engagement that precedes filing and
 * never appears on the public register. Renders nothing when the matter has no
 * usable estimate (see getPreNotificationEstimate).
 */
function PreNotificationEstimate({ merger }) {
  const estimate = getPreNotificationEstimate(merger);
  if (!estimate) return null;

  return (
    <div className="flex items-center gap-3 bg-gray-50/80 rounded-2xl border border-gray-200/60 shadow-card p-4 mb-6">
      <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-gray-100 flex items-center justify-center">
        <span className="text-lg leading-none" aria-hidden="true">✨</span>
      </div>
      <p className="flex-1 min-w-0 text-sm font-medium text-gray-900">
        Our market intelligence suggests that {describe(estimate)}
        {/* Kept to a faint pencil: an invitation for the handful of readers who
            know better, with the wording behind its tooltip rather than in
            everyone's way. */}
        <Link
          to={correctionLink(merger.merger_id)}
          title="Not quite right? Let us know what it should be"
          aria-label={`Not quite right? Let us know what the pre-notification estimate for ${merger.merger_id} should be`}
          className="inline-flex align-baseline ml-1.5 p-1 -m-1 text-gray-300 hover:text-primary transition-colors"
        >
          <FaPencilAlt className="h-3 w-3" aria-hidden="true" />
        </Link>
      </p>
    </div>
  );
}

export default PreNotificationEstimate;
