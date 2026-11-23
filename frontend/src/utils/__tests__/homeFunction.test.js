import { describe, it, expect } from 'vitest';

// The Pages Function that serves `/` from the prerendered homepage. Cloudflare
// only invokes onRequest, so this fakes the two pieces of the runtime it
// touches: the ASSETS binding and context.next().
import { HOME_CANONICAL_TAG, HOME_PAGE_PATH, onRequest } from '../../../../functions/index.js';
import { STATIC_PAGE_META, documentTitle } from '../pageMeta.js';
import { renderPage } from '../../../prerender.js';

const HOME_HTML = `<!doctype html><html><head>${HOME_CANONICAL_TAG}</head><body><div id="root"><h1>Australian Merger Tracker</h1></div></body></html>`;
const SHELL_HTML = '<!doctype html><html><head><title>x</title></head><body><div id="root"></div></body></html>';

// `homeCopy` is what the deployment holds at HOME_PAGE_PATH: a Response
// factory, or undefined for a deployment without it (Pages then answers with
// the SPA shell, 200, as it does for any miss).
function makeContext({ homeCopy, method = 'GET', headers = {} } = {}) {
  const seen = [];
  const request = new Request('https://mergers.fyi/', { method, headers });
  return {
    seen,
    context: {
      request,
      env: {
        ASSETS: {
          fetch: async (req) => {
            seen.push(req);
            if (new URL(req.url).pathname === HOME_PAGE_PATH && homeCopy) return homeCopy(req);
            return new Response(SHELL_HTML, { headers: { 'Content-Type': 'text/html' } });
          },
        },
      },
      next: async () => new Response(SHELL_HTML, { headers: { 'Content-Type': 'text/html', 'X-Fallback': '1' } }),
    },
  };
}

const servedCopy = () =>
  new Response(HOME_HTML, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      ETag: '"home-1"',
      'X-Robots-Tag': 'noindex',
      'Content-Security-Policy': "default-src 'self'",
    },
  });

describe('homepage Function', () => {
  it('serves the prerendered homepage at /, without its noindex', async () => {
    const { context } = makeContext({ homeCopy: servedCopy });
    const res = await onRequest(context);
    expect(res.status).toBe(200);
    expect(await res.text()).toBe(HOME_HTML);
    expect(res.headers.get('X-Robots-Tag')).toBeNull();
    expect(res.headers.get('X-Fallback')).toBeNull();
    // The copy's other headers (security, caching validators) carry over.
    expect(res.headers.get('Content-Security-Policy')).toBe("default-src 'self'");
    expect(res.headers.get('ETag')).toBe('"home-1"');
  });

  it('answers HEAD with the headers and no body', async () => {
    const { context } = makeContext({ homeCopy: servedCopy, method: 'HEAD' });
    const res = await onRequest(context);
    expect(res.status).toBe(200);
    expect(await res.text()).toBe('');
  });

  it('revalidates against the copy, forwarding only If-None-Match', async () => {
    const { context, seen } = makeContext({
      headers: { 'If-None-Match': '"home-1"', Cookie: 'a=b' },
      homeCopy: (req) =>
        req.headers.get('If-None-Match') === '"home-1"'
          ? new Response(null, { status: 304, headers: { ETag: '"home-1"', 'X-Robots-Tag': 'noindex' } })
          : servedCopy(),
    });
    const res = await onRequest(context);
    expect(res.status).toBe(304);
    expect(res.headers.get('X-Robots-Tag')).toBeNull();
    expect(seen[0].headers.get('Cookie')).toBeNull();
  });

  it('falls back to the SPA shell when the copy is missing from the deployment', async () => {
    const { context } = makeContext({ homeCopy: undefined });
    const res = await onRequest(context);
    expect(res.headers.get('X-Fallback')).toBe('1');
  });

  it('falls back to the SPA shell when ASSETS throws', async () => {
    const { context } = makeContext({
      homeCopy: () => {
        throw new Error('boom');
      },
    });
    expect((await onRequest(context)).headers.get('X-Fallback')).toBe('1');
  });

  it('leaves other methods to Pages', async () => {
    const { context, seen } = makeContext({ homeCopy: servedCopy, method: 'POST' });
    expect((await onRequest(context)).headers.get('X-Fallback')).toBe('1');
    expect(seen).toHaveLength(0);
  });

  it('recognises the canonical the prerenderer actually stamps on the homepage', () => {
    const meta = { ...STATIC_PAGE_META['/'], path: '/' };
    const html = renderPage('<html><head><title>x</title></head><body><div id="root"></div></body></html>', meta, '');
    expect(html).toContain(HOME_CANONICAL_TAG);
    expect(html).toContain(`<title>${documentTitle(meta).replace(/&/g, '&amp;')}</title>`);
  });
});
