// Where a dismissed promo is remembered, per campaign. Shared by PromoStack and
// the prerendered homepage's head script (frontend/prerender.js), which reads
// the same keys to hide a dismissed promo before the page is first painted.
export const PROMO_DISMISSED_PREFIX = 'promo_dismissed_';

export const promoDismissedKey = (campaign) => `${PROMO_DISMISSED_PREFIX}${campaign}`;
