import { useState, useCallback } from 'react';
import { Link } from 'react-router';
import { FaXmark } from 'react-icons/fa6';

/**
 * A dismissible banner promoting one page of the site.
 *
 * Nothing about a particular campaign lives here - the pitch, its target and
 * its icon are all passed in (see constants/promo.js for the one the dashboard
 * currently runs), so pointing the card at something else is a config change
 * rather than an edit to this file.
 *
 * `campaign` is the dismissal identity: it keys the localStorage flag, so
 * giving a new campaign a new id resurfaces the card for everyone who
 * dismissed the previous one.
 *
 * `icon` is a component type (e.g. `FaGaugeHigh`), not an element, matching how
 * constants/outcomeIcons.js carries icons.
 */
function PromoCard({ campaign, to, icon: Icon, title, description }) {
  const storageKey = `promo_dismissed_${campaign}`;

  const [isDismissed, setIsDismissed] = useState(() => {
    try {
      return !!localStorage.getItem(storageKey);
    } catch {
      return false;
    }
  });

  const dismiss = useCallback(() => {
    try {
      localStorage.setItem(storageKey, '1');
    } catch {
      // Ignore storage failures (private browsing, quota) - the card just
      // reappears next visit.
    }
    setIsDismissed(true);
  }, [storageKey]);

  if (isDismissed) return null;

  return (
    <div className="relative mb-8 rounded-2xl shadow-card hover:shadow-card-hover transition-all duration-200 group bg-primary hover:bg-primary-dark">
      <Link to={to} className="flex items-center gap-4 p-6 pr-12 rounded-2xl">
        {Icon && (
          <div className="flex-shrink-0 w-11 h-11 rounded-xl bg-white/15 flex items-center justify-center text-xl text-white group-hover:scale-105 transition-transform duration-200">
            <Icon />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <h2 className="text-base font-semibold text-white">{title}</h2>
          {description && <p className="text-sm text-white/80 mt-0.5">{description}</p>}
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

export default PromoCard;
