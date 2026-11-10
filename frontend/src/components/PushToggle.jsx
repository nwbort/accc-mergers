import { usePush } from '../context/PushContext';

// The browser-notifications switch at the foot of the notification panel.
// Following doesn't depend on it: with notifications off or blocked, news
// still shows in the panel on the next visit, and the copy says so.
function PushToggle() {
  const push = usePush();
  if (!push || push.status === 'unavailable') return null;
  const { status, busy, error, turnOn, turnOff } = push;

  if (status === 'home-screen') {
    return (
      <p className="text-xs text-gray-500 mb-2">
        To get notifications on an iPhone or iPad, add mergers.fyi to your Home Screen
        (Share → Add to Home Screen) and open it from there.
      </p>
    );
  }

  if (status === 'blocked') {
    return (
      <p className="text-xs text-gray-500 mb-2">
        Notifications are blocked for mergers.fyi in this browser. Following still works:
        updates show here when you visit.
      </p>
    );
  }

  const on = status === 'on';
  return (
    <div className="mb-2">
      <div className="flex items-center justify-between gap-3">
        <span id="push-toggle-label" className="text-xs font-medium text-gray-700">
          Browser notifications
        </span>
        <button
          type="button"
          role="switch"
          aria-checked={on}
          aria-labelledby="push-toggle-label"
          aria-describedby="push-toggle-hint"
          disabled={busy}
          onClick={on ? turnOff : turnOn}
          className={`relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:opacity-60 ${
            on ? 'bg-primary' : 'bg-gray-300'
          }`}
        >
          <span
            aria-hidden="true"
            className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
              on ? 'translate-x-4' : 'translate-x-0.5'
            }`}
          />
        </button>
      </div>
      <p id="push-toggle-hint" className="mt-1 text-xs text-gray-500">
        {on
          ? 'This browser is notified when something you follow changes.'
          : 'Get a notification when something you follow changes, even with the site closed.'}
      </p>
      {error && (
        <p className="mt-1 text-xs text-red-700" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export default PushToggle;
