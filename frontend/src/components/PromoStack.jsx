import { useState, useCallback, useEffect } from 'react';
import PromoCard from './PromoCard';

// The localStorage flag recording that a reader dismissed a campaign. The key
// predates PromoStack, so changing its shape would resurface every campaign
// for everyone who has already dismissed one.
function storageKey(campaign) {
  return `promo_dismissed_${campaign}`;
}

function readDismissed(promos) {
  const dismissed = new Set();
  for (const { campaign } of promos) {
    try {
      if (localStorage.getItem(storageKey(campaign))) dismissed.add(campaign);
    } catch {
      // Unreadable storage (private browsing): treat as not dismissed.
    }
  }
  return dismissed;
}

// The current time, re-read every minute while `ticking` - only needed when a
// campaign's wording follows the clock.
function useMinuteClock(ticking) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    if (!ticking) return undefined;
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, [ticking]);
  return now;
}

// A campaign as it should show at `now`: its `resolve(now)` merged over it,
// or null when that hides it.
function atTime({ resolve, ...promo }, now) {
  if (!resolve) return promo;
  const props = resolve(now);
  return props ? { ...promo, ...props } : null;
}

/**
 * The dismissible promo banners, stacked.
 *
 * `promos` is in priority order (see constants/promo.js), top to bottom. Every
 * campaign the reader hasn't dismissed is shown; dismissing one closes the gap
 * and the ones below move up. Once every campaign is dismissed nothing
 * renders. Each dismissal is remembered per campaign id, so adding a campaign
 * to the list shows it to readers who dismissed the others without
 * resurfacing those. A campaign with `resolve` is re-read every minute, so its
 * wording follows the clock in an open tab.
 */
function PromoStack({ promos }) {
  const [dismissed, setDismissed] = useState(() => readDismissed(promos));
  const now = useMinuteClock(promos.some((promo) => promo.resolve));

  const live = promos
    .filter(({ campaign }) => !dismissed.has(campaign))
    .map((promo) => atTime(promo, now))
    .filter(Boolean);

  const dismiss = useCallback((campaign) => {
    try {
      localStorage.setItem(storageKey(campaign), '1');
    } catch {
      // Ignore storage failures (private browsing, quota) - the card just
      // reappears next visit.
    }
    setDismissed((prev) => new Set(prev).add(campaign));
  }, []);

  if (live.length === 0) return null;

  return (
    <div className="mb-8 space-y-3">
      {live.map(({ campaign, ...card }) => (
        <PromoCard key={campaign} {...card} onDismiss={() => dismiss(campaign)} />
      ))}
    </div>
  );
}

export default PromoStack;
