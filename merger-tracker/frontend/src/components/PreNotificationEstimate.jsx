import { FaRegClock } from 'react-icons/fa';
import { formatDateLong } from '../utils/dates';
import { getPreNotificationEstimate } from '../utils/preNotification';

/**
 * Callout on the merger detail page giving the estimated date a matter entered
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
        <FaRegClock className="h-4 w-4 text-gray-500" aria-hidden="true" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900">
          Our market intelligence suggests that this merger entered pre-notification
          around {formatDateLong(estimate.startDate)}
        </p>
        <p className="text-xs text-gray-500 mt-0.5">
          {estimate.bounds} before it was notified on {formatDateLong(estimate.notifiedDate)}
          {' · '}
          estimated from the order the ACCC issued case numbers in, not published by the ACCC
        </p>
      </div>
    </div>
  );
}

export default PreNotificationEstimate;
