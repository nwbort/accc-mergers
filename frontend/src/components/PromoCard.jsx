import { useCallback } from 'react';
import { Link } from 'react-router';
import { FaXmark } from 'react-icons/fa6';
import { FEATURE_EVENTS, pingFeatureEvent } from '../utils/trackEvent';

/**
 * A banner promoting one page of the site.
 *
 * Nothing about a particular campaign lives here - the pitch, its target and
 * its icon are all passed in (see constants/promo.js), and whether it has been
 * dismissed is PromoStack's business, which tells this card through
 * `onDismiss`. Render a campaign through PromoStack rather than on its own,
 * so the dismissal is remembered.
 *
 * `icon` is a component type (e.g. `FaGaugeHigh`), not an element, matching how
 * constants/outcomeIcons.js carries icons.
 */
function PromoCard({ to, icon: Icon, title, description, onDismiss }) {
  const dismiss = useCallback(() => {
    pingFeatureEvent(FEATURE_EVENTS.PROMO_CARD_DISMISSED);
    onDismiss();
  }, [onDismiss]);

  const clickThrough = useCallback(() => {
    pingFeatureEvent(FEATURE_EVENTS.PROMO_CARD_CLICKED);
  }, []);

  return (
    <div className="relative rounded-2xl shadow-card hover:shadow-card-hover transition-all duration-200 group bg-primary hover:bg-primary-dark">
      <Link to={to} onClick={clickThrough} className="flex items-center gap-4 p-6 pr-12 rounded-2xl">
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
        aria-label={`Dismiss: ${title}`}
        className="absolute top-1/2 right-4 -translate-y-1/2 text-white/70 hover:text-white transition-colors p-1"
      >
        <FaXmark className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </div>
  );
}

export default PromoCard;
