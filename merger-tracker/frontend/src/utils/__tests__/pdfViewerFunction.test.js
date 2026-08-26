import { describe, it, expect } from 'vitest';

// The Pages Function that serves /mergers/{MN,WA}-XXXXX/<file>.pdf. Cloudflare
// only invokes onRequest, so exercising it here means faking the two pieces of
// the runtime it touches: the ASSETS binding and context.next().
import { onRequest } from '../../../../../functions/mergers/[matter]/[[path]].js';

const PDF_PATH = '/mergers/MN-01068/Affidavit of Benjamin James Welk.pdf';
const SOURCE_URL =
  'https://www.competitiontribunal.gov.au/__data/assets/pdf_file/0004/602167/Affidavit-of-Benjamin-James-Welk.pdf';

const MERGER_JSON = {
  merger_name: 'Woolworths / Coles Kalgoorlie',
  events: [
    {
      title: 'Affidavit of Benjamin James Welk',
      url: SOURCE_URL,
      url_gh: PDF_PATH,
    },
  ],
};

// Stands in for env.ASSETS: `assets` maps a pathname to the Response the
// deployment would return. Anything not listed is a miss, which Pages answers
// with the SPA shell (HTML, 200) rather than a 404 — the case the fallback in
// the Function has to recognise.
function makeEnv(assets) {
  return {
    ASSETS: {
      fetch: async (request) => {
        // Pathnames arrive percent-encoded; the asset map is keyed by the real
        // filename, as the deployment's file tree is.
        const pathname = decodeURIComponent(new URL(request.url).pathname);
        if (pathname in assets) return assets[pathname];
        return new Response('<!doctype html><title>Australian Merger Tracker</title>', {
          headers: { 'Content-Type': 'text/html; charset=utf-8' },
        });
      },
    },
  };
}

function pdfResponse() {
  return new Response('%PDF-1.7 ...', { headers: { 'Content-Type': 'application/pdf' } });
}

function jsonResponse(body) {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
  });
}

function makeContext({ url, env, userAgent = 'Mozilla/5.0 (Macintosh)' }) {
  return {
    request: new Request(url, { headers: { 'User-Agent': userAgent } }),
    env,
    next: async () => new Response('passed through', { status: 599 }),
  };
}

const rawUrl = `https://mergers.fyi${encodeURI(PDF_PATH)}?raw=1`;
const dataPath = '/data/mergers/MN-01068.json';

describe('PDF asset serving', () => {
  it('serves the deployed PDF when it is present', async () => {
    const env = makeEnv({ [PDF_PATH]: pdfResponse() });
    const response = await onRequest(makeContext({ url: rawUrl, env }));

    expect(response.status).toBe(200);
    expect(response.headers.get('Content-Type')).toBe('application/pdf');
  });

  it('redirects to the source URL when the PDF is too big to deploy', async () => {
    // No PDF asset — scripts/build.sh leaves files over 25 MiB out of dist/.
    const env = makeEnv({ [dataPath]: jsonResponse(MERGER_JSON) });
    const response = await onRequest(makeContext({ url: rawUrl, env }));

    expect(response.status).toBe(302);
    expect(response.headers.get('Location')).toBe(SOURCE_URL);
  });

  it('redirects on mobile too, where the viewer wrapper is skipped', async () => {
    const env = makeEnv({ [dataPath]: jsonResponse(MERGER_JSON) });
    const response = await onRequest(
      makeContext({
        url: `https://mergers.fyi${encodeURI(PDF_PATH)}`,
        env,
        userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',
      }),
    );

    expect(response.status).toBe(302);
    expect(response.headers.get('Location')).toBe(SOURCE_URL);
  });

  it('redirects a lowercase matter ID to its canonical uppercase form', async () => {
    const env = makeEnv({ [dataPath]: jsonResponse(MERGER_JSON) });
    const response = await onRequest(
      makeContext({
        url: `https://mergers.fyi${encodeURI(PDF_PATH.replace('MN-01068', 'mn-01068'))}?raw=1`,
        env,
      }),
    );

    expect(response.status).toBe(301);
    expect(response.headers.get('Location')).toBe(`https://mergers.fyi${encodeURI(PDF_PATH)}?raw=1`);
  });

  it('falls back to the asset response when no source URL is known', async () => {
    const env = makeEnv({
      [dataPath]: jsonResponse({ ...MERGER_JSON, events: [{ title: 'No link' }] }),
    });
    const response = await onRequest(makeContext({ url: rawUrl, env }));

    expect(response.status).toBe(200);
    expect(response.headers.get('Content-Type')).toContain('text/html');
  });

  it('refuses to redirect to a non-http(s) source URL', async () => {
    const env = makeEnv({
      [dataPath]: jsonResponse({
        events: [{ url: 'javascript:alert(1)', url_gh: PDF_PATH }],
      }),
    });
    const response = await onRequest(makeContext({ url: rawUrl, env }));

    expect(response.status).toBe(200);
    expect(response.headers.get('Content-Type')).toContain('text/html');
  });

  it('still renders the viewer wrapper for a desktop request', async () => {
    const env = makeEnv({ [PDF_PATH]: pdfResponse() });
    const response = await onRequest(
      makeContext({ url: `https://mergers.fyi${encodeURI(PDF_PATH)}`, env }),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get('Content-Type')).toContain('text/html');
    await expect(response.text()).resolves.toContain('?raw=1');
  });
});

describe('matter ID case redirect', () => {
  it('redirects a bare lowercase matter ID to its uppercase form', async () => {
    const env = makeEnv({});
    const response = await onRequest(
      makeContext({ url: 'https://mergers.fyi/mergers/mn-01068', env }),
    );

    expect(response.status).toBe(301);
    expect(response.headers.get('Location')).toBe('https://mergers.fyi/mergers/MN-01068');
  });

  it('redirects a lowercase matter ID followed by a slug, preserving the slug', async () => {
    const env = makeEnv({});
    const response = await onRequest(
      makeContext({ url: 'https://mergers.fyi/mergers/wa-70017/some-readable-slug', env }),
    );

    expect(response.status).toBe(301);
    expect(response.headers.get('Location')).toBe(
      'https://mergers.fyi/mergers/WA-70017/some-readable-slug',
    );
  });

  it('leaves an already-uppercase matter ID alone and passes it through', async () => {
    const env = makeEnv({ [dataPath]: jsonResponse(MERGER_JSON) });
    const response = await onRequest(
      makeContext({ url: 'https://mergers.fyi/mergers/MN-01068', env }),
    );

    // Not a bot, not a .pdf request — falls through to context.next(), whose
    // stand-in here returns the 599 sentinel (see makeContext above).
    expect(response.status).toBe(599);
  });
});
