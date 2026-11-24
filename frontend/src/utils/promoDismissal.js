// Where a dismissed promo is remembered, per campaign. Shared by PromoStack and
// the prerendered homepage's head script (frontend/prerender.js), which reads
// the same keys to hide a dismissed promo before the page is first painted.
// The key predates PromoStack, so changing its shape would resurface every
// campaign for everyone who has already dismissed one.
export const PROMO_DISMISSED_PREFIX = 'promo_dismissed_';

export const promoDismissedKey = (campaign) => `${PROMO_DISMISSED_PREFIX}${campaign}`;

// The id of that head script's <style>. PromoStack removes it once mounted,
// when it has taken over deciding what shows: left in place, a rule hiding the
// whole stack (every campaign dismissed) would also hide a campaign that only
// went live after the build.
export const PROMO_HIDE_STYLE_ID = 'promo-hide';
