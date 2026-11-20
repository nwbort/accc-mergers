import { useCallback } from 'react';
import { Link } from 'react-router';
import { FaXmark } from 'react-icons/fa6';
import { FEATURE_EVENTS, pingFeatureEvent } from '../utils/trackEvent';
import MaterialShape from './MaterialShape';

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
 *
 * `to` is a route inside the site; `href` an external URL, opened in a new tab.
 */
function PromoCard({ to, href, icon: Icon, title, description, onDismiss }) {
  const dismiss = useCallback(() => {
    pingFeatureEvent(FEATURE_EVENTS.PROMO_CARD_DISMISSED);
    onDismiss();
  }, [onDismiss]);

  const clickThrough = useCallback(() => {
    pingFeatureEvent(FEATURE_EVENTS.PROMO_CARD_CLICKED);
  }, []);

  const LinkTag = href ? 'a' : Link;
  const linkProps = href ? { href, target: '_blank', rel: 'noopener noreferrer' } : { to };

  return (
    <div className="relative overflow-hidden rounded-3xl press-morph hover:rounded-[2.5rem] group bg-primary hover:bg-primary-dark">
      {/* A large, faint Material shape behind the banner, turning on hover. */}
      <MaterialShape
        shape="softBurst"
        className="pointer-events-none absolute right-10 -bottom-24 h-48 w-48 text-white/[0.07] transition-transform duration-700 ease-spring group-hover:rotate-45"
      />
      <LinkTag {...linkProps} onClick={clickThrough} className="relative flex items-center gap-4 p-6 pr-12 rounded-3xl">
        {Icon && (
          <div className="flex-shrink-0 w-12 h-12 rounded-full bg-white/15 flex items-center justify-center text-xl text-white transition-all duration-300 ease-spring group-hover:rounded-xl">
            <Icon />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <h2 className="text-base font-semibold text-white">{title}</h2>
          {description && <p className="text-sm text-white/80 mt-0.5">{description}</p>}
        </div>
      </LinkTag>
      <button
        onClick={dismiss}
        aria-label={`Dismiss: ${title}`}
        className="absolute top-1/2 right-3 -translate-y-1/2 inline-flex items-center justify-center h-10 w-10 rounded-full text-white/80 hover:text-white hover:bg-white/10 transition-colors"
      >
        <FaXmark className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </div>
  );
}

export default PromoCard;
