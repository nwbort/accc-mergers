import { useState, useCallback } from 'react';
import { Link } from 'react-router';
import { FaEnvelope, FaXmark } from 'react-icons/fa6';

// Set to false to hide the card entirely (e.g. once digest signups plateau).
const ENABLED = true;

// Bump this string to resurface the card for everyone who dismissed a previous campaign.
const CAMPAIGN = 'v1';
const STORAGE_KEY = `digest_promo_dismissed_${CAMPAIGN}`;

function DigestPromoCard() {
  const [isDismissed, setIsDismissed] = useState(() => {
    try {
      return !!localStorage.getItem(STORAGE_KEY);
    } catch {
      return false;
    }
  });

  const dismiss = useCallback(() => {
    try {
      localStorage.setItem(STORAGE_KEY, '1');
    } catch {
      // Ignore storage failures (private browsing, quota) - the card just
      // reappears next visit.
    }
    setIsDismissed(true);
  }, []);

  if (!ENABLED || isDismissed) return null;

  return (
    <div className="relative mb-8 rounded-2xl shadow-card hover:shadow-card-hover transition-all duration-200 group bg-primary hover:bg-primary-dark overflow-hidden">
      <Link to="/digest" className="flex items-center gap-4 p-6 pr-12">
        <div className="flex-shrink-0 w-11 h-11 rounded-xl bg-white/15 flex items-center justify-center text-xl text-white group-hover:scale-105 transition-transform duration-200">
          <FaEnvelope />
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="text-base font-semibold text-white">
            Want a weekly round-up of ACCC merger activity?
          </h2>
          <p className="text-sm text-white/80 mt-0.5">
            Get the week's notifications, determinations and upcoming deadlines in one email.
          </p>
        </div>
      </Link>
      <button
        onClick={dismiss}
        aria-label="Dismiss"
        className="absolute top-1/2 right-4 -translate-y-1/2 text-white/70 hover:text-white transition-colors p-1"
      >
        <FaXmark className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </div>
  );
}

export default DigestPromoCard;
