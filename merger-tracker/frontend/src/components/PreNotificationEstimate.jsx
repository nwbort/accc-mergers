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
      </p>
    </div>
  );
}

export default PreNotificationEstimate;
