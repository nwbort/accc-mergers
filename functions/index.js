// The homepage, served from its prerendered copy.
//
// dist/index.html can't carry the homepage's own canonical or body: Cloudflare
// Pages serves that same file for every URL without one of its own (the SPA
// fallback — /feedback, unslugged merger URLs, 404s), so whatever it says, it
// says for all of them. frontend/prerender.js therefore writes the stamped
// homepage to HOME_PAGE_PATH instead, and this Function — which Pages routes
// for `/` alone — serves it there. Every other URL still gets the bare shell.
//
// The copy's own URL is marked noindex in public/_headers; that header is
// dropped here, since it must not reach `/`. Anything unexpected (the copy
// missing from the deployment, an error) falls through to the shell, which is
// what `/` served before this Function existed.

export const HOME_PAGE_PATH = '/prerendered/home';

// Only the stamped homepage carries this. A miss on HOME_PAGE_PATH comes back
// as the SPA shell with a 200, which doesn't, so it identifies a real copy.
export const HOME_CANONICAL_TAG = '<link rel="canonical" href="https://mergers.fyi/" />';

function servedHeaders(source) {
  const headers = new Headers(source);
  headers.delete('X-Robots-Tag');
  headers.delete('Content-Length');
  return headers;
}

export async function onRequest({ request, env, next }) {
  if (request.method !== 'GET' && request.method !== 'HEAD') return next();

  let page;
  try {
    // Only the validator is forwarded, so a browser's cached copy of `/` can
    // be revalidated against the copy's ETag.
    const headers = new Headers();
    const etag = request.headers.get('If-None-Match');
    if (etag) headers.set('If-None-Match', etag);
    page = await env.ASSETS.fetch(new Request(new URL(HOME_PAGE_PATH, request.url), { headers }));
  } catch {
    return next();
  }

  if (page.status === 304) {
    return new Response(null, { status: 304, headers: servedHeaders(page.headers) });
  }
  if (!page.ok) return next();

  const html = await page.text();
  if (!html.includes(HOME_CANONICAL_TAG)) return next();

  return new Response(request.method === 'HEAD' ? null : html, {
    status: 200,
    headers: servedHeaders(page.headers),
  });
}
