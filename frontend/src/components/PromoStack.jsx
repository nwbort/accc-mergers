import { useState, useCallback } from 'react';
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

/**
 * A queue of dismissible promo banners, shown one at a time.
 *
 * `promos` is in priority order (see constants/promo.js). The reader sees the
 * first campaign they haven't dismissed; dismissing it brings the next one up
 * into the same spot, and once every campaign is dismissed nothing renders.
 * Each dismissal is remembered per campaign id, so adding a campaign to the
 * list shows it to readers who dismissed the others without resurfacing
 * those.
 */
function PromoStack({ promos }) {
  const [dismissed, setDismissed] = useState(() => readDismissed(promos));

  const current = promos.find(({ campaign }) => !dismissed.has(campaign));

  const dismissCurrent = useCallback(() => {
    if (!current) return;
    try {
      localStorage.setItem(storageKey(current.campaign), '1');
    } catch {
      // Ignore storage failures (private browsing, quota) - the card just
      // reappears next visit.
    }
    setDismissed((prev) => new Set(prev).add(current.campaign));
  }, [current]);

  if (!current) return null;

  // Keyed by campaign so the next card mounts fresh rather than inheriting
  // the dismissed one's DOM (and its hover state).
  const { campaign, ...card } = current;
  return <PromoCard key={campaign} {...card} onDismiss={dismissCurrent} />;
}

export default PromoStack;
