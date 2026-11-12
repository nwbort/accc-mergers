import { FaBell, FaTimes } from 'react-icons/fa';
import { usePush } from '../context/PushContext';

const dismissButton = (onClick) => (
  <button
    type="button"
    onClick={onClick}
    aria-label="Dismiss notifications offer"
    title="Dismiss"
    className="p-1.5 -m-1 rounded-md text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
  >
    <FaTimes className="w-3 h-3" aria-hidden="true" />
  </button>
);

// Browser notifications at the foot of the notification panel. Asks once and
// gets out of the way: an "Enable browser notifications" button until its × is
// pressed, a quiet line while they're on. Following never depends on it.
function PushToggle() {
  const push = usePush();
  if (!push || push.status === 'unavailable') return null;
  const { status, busy, error, dismissed, turnOn, turnOff, dismiss } = push;

  if (status === 'on') {
    return (
      <p className="flex items-center gap-1.5 text-xs text-gray-500 mb-2">
        <FaBell className="w-3 h-3 text-primary" aria-hidden="true" />
        <span>Browser notifications are on.</span>
        <button
          type="button"
          onClick={turnOff}
          disabled={busy}
          className="font-medium text-primary hover:text-primary-dark hover:underline disabled:opacity-60"
        >
          Turn off
        </button>
      </p>
    );
  }

  // Refused from the button just now: say where to change it, once.
  if (status === 'blocked') {
    if (!error || dismissed) return null;
    return (
      <div className="flex items-start justify-between gap-3 mb-2">
        <p className="text-xs text-gray-500" role="alert">{error}</p>
        {dismissButton(dismiss)}
      </div>
    );
  }

  if (dismissed) return null;

  if (status === 'home-screen') {
    return (
      <div className="flex items-start justify-between gap-3 mb-2">
        <p className="text-xs text-gray-500">
          To get notifications on an iPhone or iPad, add mergers.fyi to your Home Screen
          (Share → Add to Home Screen) and open it from there.
        </p>
        {dismissButton(dismiss)}
      </div>
    );
  }

  return (
    <div className="mb-2.5">
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          // Never disabled while a request is out: one the person ignored never
          // settles, and pressing again should simply ask again.
          onClick={() => turnOn({ fromPanel: true })}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-primary-dark transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:opacity-60"
        >
          <FaBell className="w-3 h-3" aria-hidden="true" />
          Enable browser notifications
        </button>
        {dismissButton(dismiss)}
      </div>
      {error && (
        <p className="mt-1.5 text-xs text-red-700" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export default PushToggle;
