import { afterEach, describe, expect, it } from 'vitest';
import { renderHome } from '../renderStatic.jsx';
import { promoHideScript } from '../../../prerender.js';
import { promoDismissedKey } from '../../utils/promoDismissal';
import realStats from '../../../public/data/stats.json';

// The prerendered homepage's head script, run against the dashboard top the
// build renders, as a browser would before first paint. Rendered once, up
// front and with nothing dismissed, as the build (which has no storage) does.
const built = renderHome(realStats);
function load() {
  document.body.innerHTML = built;
  const campaigns = [...document.querySelectorAll('[data-promo-campaign]')].map((el) => el.dataset.promoCampaign);
  const script = promoHideScript(campaigns).replace(/^<script>|<\/script>$/g, '');
  new Function(script)();
  return campaigns;
}
const shown = (el) => getComputedStyle(el).display !== 'none';

describe('promoHideScript', () => {
  afterEach(() => {
    localStorage.clear();
    document.head.querySelectorAll('style').forEach((s) => s.remove());
    document.body.innerHTML = '';
  });

  it('shows every promo to a visitor who dismissed none', () => {
    const campaigns = load();
    expect(campaigns.length).toBeGreaterThan(0);
    for (const el of document.querySelectorAll('[data-promo-campaign], [data-promo-stack]')) {
      expect(shown(el)).toBe(true);
    }
  });

  it('hides a dismissed promo, and the stack once all are, before React mounts', () => {
    const campaigns = [...built.matchAll(/data-promo-campaign="([^"]+)"/g)].map((m) => m[1]);
    for (const c of campaigns) localStorage.setItem(promoDismissedKey(c), '1');
    load();
    for (const el of document.querySelectorAll('[data-promo-campaign]')) expect(shown(el)).toBe(false);
    expect(shown(document.querySelector('[data-promo-stack]'))).toBe(false);
  });

  it('writes nothing when the page was built without promos', () => {
    expect(promoHideScript([])).toBe('');
  });
});
