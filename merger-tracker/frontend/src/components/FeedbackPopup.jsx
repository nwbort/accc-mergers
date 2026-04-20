import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';

// Set to false to hide the popup entirely (e.g. between feedback campaigns).
const ENABLED = false;

// Set to false to suppress the popup on mobile screens (< 768px).
const SHOW_ON_MOBILE = false;

// Bump this string to resurface the popup for everyone who dismissed a previous campaign.
// e.g. 'v1' → 'v2' shows it again to all previous dismissers.
const CAMPAIGN = 'v1';
const STORAGE_KEY = `feedback_dismissed_${CAMPAIGN}`;
const SHOW_DELAY_MS = 30_000;

function FeedbackPopup() {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const isMobile = window.innerWidth < 768;
    if (!ENABLED || (!SHOW_ON_MOBILE && isMobile) || localStorage.getItem(STORAGE_KEY)) return;
    const timer = setTimeout(() => setIsVisible(true), SHOW_DELAY_MS);
    return () => clearTimeout(timer);
  }, []);

  const dismiss = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, '1');
    setIsVisible(false);
  }, []);

  if (!isVisible) return null;

  return (
    <div
      role="dialog"
      aria-label="Share feedback"
      className="fixed bottom-4 right-4 z-50 w-72 rounded-2xl bg-white shadow-elevated border border-gray-200 overflow-hidden animate-slide-up"
    >
      <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-100">
        <h3 className="text-sm font-semibold text-gray-800">Got feedback?</h3>
        <button
          onClick={dismiss}
          aria-label="Dismiss"
          className="text-gray-400 hover:text-gray-600 transition-colors"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="p-4 flex flex-col gap-3">
        <p className="text-sm text-gray-600">
          Got a suggestion or spotted an issue? I'd love to hear it.
        </p>
        <Link
          to="/feedback"
          onClick={dismiss}
          className="inline-block w-full text-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary-dark"
        >
          Share feedback
        </Link>
      </div>
    </div>
  );
}

export default FeedbackPopup;
