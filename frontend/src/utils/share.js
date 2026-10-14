// Share links for a page: where each "share to …" option sends the reader, and
// whether to hand the job to the device's own share sheet instead.
//
// Pure apart from prefersNativeShare's defaults, so the URL shapes can be
// pinned in a test without a browser.

import { SITE_URL } from './pageMeta.js';

/** The absolute URL to share for a site path ("/mergers/MN-01016/acme"). */
export function shareUrl(path) {
  return `${SITE_URL}${path}`;
}

/**
 * The "share to" destinations offered in the menu, in display order.
 *
 * Bluesky takes one free-text field, so the link goes inside the post text;
 * LinkedIn reads everything it shows from the page's Open Graph tags and
 * takes only the URL.
 */
export function shareTargets({ url, title }) {
  const u = encodeURIComponent(url);
  const withLink = encodeURIComponent(`${title}\n${url}`);
  return [
    { id: 'linkedin', label: 'LinkedIn', href: `https://www.linkedin.com/sharing/share-offsite/?url=${u}` },
    { id: 'bluesky', label: 'Bluesky', href: `https://bsky.app/intent/compose?text=${withLink}` },
    {
      id: 'email',
      label: 'Email',
      href: `mailto:?subject=${encodeURIComponent(title)}&body=${withLink}`,
    },
  ];
}

/**
 * Whether to open the device's share sheet rather than the menu.
 *
 * Only on touch-first devices: desktop browsers increasingly implement
 * navigator.share too, but their share sheet offers fewer useful targets than
 * the menu does and has no "copy link", which is what a desktop reader wants.
 */
export function prefersNativeShare(nav = globalThis.navigator, win = globalThis.window) {
  if (typeof nav?.share !== 'function') return false;
  return Boolean(win?.matchMedia?.('(pointer: coarse)').matches);
}
