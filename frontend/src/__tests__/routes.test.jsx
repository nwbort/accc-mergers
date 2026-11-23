import { afterEach, describe, expect, it, vi } from 'vitest';
import { Suspense, startTransition } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import { ROUTES, preloadRoute, routeData, routeFor } from '../routes';
import { dataCache } from '../utils/dataCache';
import { DASHBOARD_STATS_KEY } from '../utils/pageData';

describe('routeFor', () => {
  it('picks the route <Routes> would, slugged or not, and the 404 otherwise', () => {
    expect(routeFor('/').path).toBe('/');
    expect(routeFor('/mergers').path).toBe('/mergers');
    expect(routeFor('/mergers/MN-01016').path).toBe('/mergers/:id');
    expect(routeFor('/mergers/MN-01016/a-b').path).toBe('/mergers/:id/:slug');
    expect(routeFor('/quarterly/26Q3').path).toBe('/quarterly/:quarter');
    expect(routeFor('/no/such/page').path).toBe('*');
  });

  it('lists each path once, with the 404 last', () => {
    const paths = ROUTES.map((r) => r.path);
    expect(new Set(paths).size).toBe(paths.length);
    expect(paths.at(-1)).toBe('*');
  });
});

describe('routeData', () => {
  it("gives each detail page's fetch from its URL, as the page itself builds it", () => {
    expect(routeData('/mergers/mn-01016/a-b')).toEqual([['merger-MN-01016', '/data/mergers/MN-01016.json']]);
    expect(routeData('/mergers')[0][0]).toBe('mergers-list');
    const [[industryKey, industryUrl]] = routeData('/industries/4110/supermarkets');
    expect(industryKey).toMatch(/^industry-division-/);
    expect(industryUrl).toMatch(/^\/data\/industries\/[A-Z_a-z]+\.json$/);
    // Decoded as useDecodedParam decodes the page's own param.
    const [[partyKey, partyUrl]] = routeData('/parties/coles%20group');
    expect(partyKey).toBe(`party-shard-${partyUrl}`);
    expect(routeData('/parties/coles group')).toEqual(routeData('/parties/coles%20group'));
  });

  it('is empty for a page whose first render waits on nothing', () => {
    expect(routeData('/nick-twort')).toEqual([]);
    expect(routeData('/no/such/page')).toEqual([]);
  });
});

describe('preloadRoute', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  it("fills the homepage's stats before the dashboard mounts", async () => {
    const stats = { total_mergers: 1 };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, json: async () => stats });
    vi.spyOn(routeFor('/').page, 'load').mockResolvedValue({ default: () => null });
    await preloadRoute('/');
    expect(dataCache.get(DASHBOARD_STATS_KEY)).toEqual(stats);
  });

  it('never rejects, whatever fails: the page then loads and reports it itself', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('offline'));
    vi.spyOn(routeFor('/').page, 'load').mockRejectedValue(new Error('chunk'));
    await expect(preloadRoute('/')).resolves.toBeDefined();
    expect(dataCache.has(DASHBOARD_STATS_KEY)).toBe(false);
  });
});

describe('a preloaded page', () => {
  // How main.jsx mounts a prerendered page: after preloadRoute, in a transition.
  async function mountAfterPreload(path) {
    const { page } = routeFor(path);
    await page.load();
    const el = document.createElement('div');
    el.innerHTML = '<p>prerendered</p>';
    const painted = [];
    new MutationObserver(() => painted.push(el.textContent)).observe(el, { childList: true, subtree: true });
    const root = createRoot(el);
    const render = () =>
      root.render(
        <HelmetProvider>
          <MemoryRouter initialEntries={[path]}>
            <Suspense fallback={<p>spinner</p>}>
              <page.Component />
            </Suspense>
          </MemoryRouter>
        </HelmetProvider>,
      );
    startTransition(render);
    await new Promise((r) => setTimeout(r, 50));
    const html = el.innerHTML;
    root.unmount();
    return { painted, html };
  }

  // The first render of this page in this file: React caches a lazy page as
  // resolved once rendered, so only a first render can show the difference.
  it('goes straight from the prerendered HTML to the page, never painting the fallback', async () => {
    const { painted, html } = await mountAfterPreload('/privacy');
    expect(painted.join(' ')).not.toContain('spinner');
    expect(html).toContain('<h1');
  });
});
