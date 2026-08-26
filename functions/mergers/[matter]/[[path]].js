import { renderViewer } from '../../_lib/pdf-viewer.js';

const BOT_UA_RE = /LinkedInBot|facebookexternalhit|Twitterbot|Slackbot|Discordbot|TelegramBot|WhatsApp|bingbot|Pinterestbot|Applebot|Iframely|rogerbot|embedly|outbrain|quora link preview|Slack|vkShare|W3C_Validator|redditbot|flipboard|tumblr|bitlybot|SkypeUriPreview|nuzzel|Disqus|Qwantify|pinterestbot|Baiduspider/i;

function isBotRequest(request) {
  const ua = request.headers.get('User-Agent') || '';
  return BOT_UA_RE.test(ua);
}

// Build the readable slug for a merger name. MUST stay in sync with
// merger-tracker/frontend/src/utils/slug.js and scripts/slug.py so the OG
// canonical matches the SPA's <link rel="canonical"> and the sitemap entry.
// slugify/mergerPath are exported solely so the sync test in
// merger-tracker/frontend/src/utils/__tests__/slug.test.js can assert this copy
// hasn't drifted; Cloudflare Pages only invokes `onRequest`, so the extra named
// exports are inert at runtime.
const MAX_SLUG_LENGTH = 80;
export function slugify(name) {
  if (!name) return '';
  return String(name)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, MAX_SLUG_LENGTH)
    .replace(/-+$/g, '');
}

export function mergerPath(id, name) {
  const slug = slugify(name);
  return slug ? `/mergers/${id}/${slug}` : `/mergers/${id}`;
}

function escapeHtml(str) {
  return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function buildOgHtml(merger, canonicalUrl) {
  const title = `${escapeHtml(merger.merger_name)} | Australian Merger Tracker`;
  const statusLabel = merger.accc_determination
    ? `ACCC decision: ${escapeHtml(merger.accc_determination)}`
    : escapeHtml(merger.status ?? '');
  const stage = merger.stage ? ` - ${escapeHtml(merger.stage)}` : '';
  const description = `Status: ${statusLabel}${stage}.&#10;Find merger analysis, commentary, decisions and more. Track ACCC merger reviews on mergers.fyi`;
  const publishDate = merger.effective_notification_datetime ?? merger.original_notification_datetime ?? '';

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>${title}</title>
<meta name="description" content="${description}" />
<meta name="author" content="Nick Twort" />
<meta property="og:type" content="article" />
<meta property="og:title" content="${title}" />
<meta property="og:description" content="${description}" />
<meta property="og:url" content="${escapeHtml(canonicalUrl)}" />
<meta property="og:site_name" content="Australian Merger Tracker" />
<meta property="og:image" content="https://mergers.fyi/og-image.png" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
${publishDate ? `<meta property="article:published_time" content="${escapeHtml(publishDate)}" />` : ''}
<meta property="article:author" content="Nick Twort" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="${title}" />
<meta name="twitter:description" content="${description}" />
<meta name="twitter:image" content="https://mergers.fyi/og-image.png" />
<link rel="canonical" href="${escapeHtml(canonicalUrl)}" />
</head>
<body>
<script>window.location.replace(${JSON.stringify(canonicalUrl)});</script>
</body>
</html>`;
}

async function serveOgPage(matterId, origin, env) {
  const dataUrl = new URL(`/data/mergers/${matterId}.json`, origin);
  let merger;
  try {
    const resp = await env.ASSETS.fetch(new Request(dataUrl.toString()));
    if (!resp.ok) return null;
    merger = await resp.json();
  } catch {
    return null;
  }
  // Canonical URL includes the readable slug derived from the merger name, so
  // it matches what the SPA renders and what the sitemap lists.
  const canonicalUrl = `${origin}${mergerPath(matterId, merger.merger_name)}`;
  return new Response(buildOgHtml(merger, canonicalUrl), {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'public, max-age=3600',
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'strict-origin-when-cross-origin',
    },
  });
}

function safeDecode(str) {
  try {
    return decodeURIComponent(str);
  } catch {
    return str;
  }
}

// Normalise the matter ID to uppercase: the static data files and SPA routes
// are uppercase, so a hand-typed lowercase URL would otherwise produce a viewer
// whose PDF fetch and back-link 404.
function canonicalisePath(path) {
  const match = path.match(/^\/mergers\/((MN|WA)-\d+)\//i);
  if (!match) return path;
  return path.replace(/^\/mergers\/(?:MN|WA)-\d+\//i, `/mergers/${match[1].toUpperCase()}/`);
}

// The source URL on the ACCC/Tribunal site that this document was scraped from,
// or null if we don't have one. Each event in the matter's JSON carries both the
// upstream `url` and the `url_gh` path we serve it under.
async function sourceUrlForDocument(path, origin, env) {
  const match = path.match(/^\/mergers\/((MN|WA)-\d+)\//i);
  if (!match) return null;
  const matterId = match[1].toUpperCase();

  let merger;
  try {
    const dataUrl = new URL(`/data/mergers/${matterId}.json`, origin);
    const resp = await env.ASSETS.fetch(new Request(dataUrl.toString()));
    if (!resp.ok) return null;
    merger = await resp.json();
  } catch {
    return null;
  }

  // url_gh is stored unencoded ("/mergers/MN-01068/NOCC - March 2026.pdf") while
  // the request path arrives percent-encoded, so compare both sides decoded.
  const wanted = safeDecode(canonicalisePath(path));
  const event = (merger.events || []).find(
    (e) => e.url_gh && e.url && safeDecode(canonicalisePath(e.url_gh)) === wanted,
  );
  if (!event) return null;

  // Only ever bounce to http(s) — the events are scraped from accc.gov.au and
  // competitiontribunal.gov.au, but this is a redirect built from data, so it
  // shouldn't be able to emit anything but a web URL.
  try {
    const parsed = new URL(event.url);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.toString() : null;
  } catch {
    return null;
  }
}

// Serve the PDF itself from the deployment's static assets.
//
// Documents over Cloudflare Pages' 25 MiB per-asset limit are left out of the
// deployment by scripts/build.sh (the whole deploy is rejected otherwise), so
// for those the asset lookup misses and Pages answers with the SPA shell rather
// than a 404. Treat "didn't come back as a PDF" as the miss and redirect to the
// document's source URL, so the link still resolves for the reader.
async function serveRawPdf(path, origin, env) {
  const assetUrl = new URL(path, origin);
  const response = await env.ASSETS.fetch(new Request(assetUrl.toString()));

  const contentType = response.headers.get('Content-Type') || '';
  if (response.ok && contentType.toLowerCase().includes('application/pdf')) {
    return response;
  }

  const sourceUrl = await sourceUrlForDocument(path, origin, env);
  return sourceUrl ? Response.redirect(sourceUrl, 302) : response;
}

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const path = url.pathname;

  // A hand-typed or pasted lowercase matter ID (e.g. /mergers/mn-01016, or
  // with a slug/PDF filename after it) would otherwise 404 against the
  // uppercase-named static data and SPA routes. Redirect to the canonical
  // uppercase form before any other handling — only the ID segment is
  // case-normalised, so a slug or filename after it is left untouched.
  const idCaseMatch = path.match(/^(\/mergers\/)((?:MN|WA)-\d+)((?:\/.*)?)$/i);
  if (idCaseMatch) {
    const [, prefix, matterId, rest] = idCaseMatch;
    const upperMatterId = matterId.toUpperCase();
    if (matterId !== upperMatterId) {
      url.pathname = `${prefix}${upperMatterId}${rest}`;
      return Response.redirect(url.toString(), 301);
    }
  }

  // For social/crawler bots hitting a merger detail page, serve a minimal
  // HTML response with specific OG meta tags — bots don't run JS so they would
  // otherwise see only the generic tags in the SPA's index.html. This matches
  // both the bare `/mergers/{id}` form and the readable `/mergers/{id}/{slug}`
  // form, but never the `/mergers/{id}/{file}.pdf` document paths (handled
  // below as PDF requests).
  const detailMatch = path.match(/^\/mergers\/((MN|WA)-\d+)(?:\/[^/]+)?\/?$/i);
  if (detailMatch && !path.toLowerCase().endsWith('.pdf') && isBotRequest(request)) {
    const matterId = detailMatch[1].toUpperCase();
    const ogResponse = await serveOgPage(matterId, url.origin, env);
    if (ogResponse) return ogResponse;
    // Fall through if the merger data couldn't be fetched
  }

  // Only intercept .pdf requests — let everything else (SPA routes, etc.) pass through
  if (!path.toLowerCase().endsWith('.pdf')) {
    return context.next();
  }

  // If ?raw param is present, serve the actual PDF from static assets
  // (used by the embedded viewer and direct download links)
  if (url.searchParams.has('raw')) {
    return serveRawPdf(path, url.origin, env);
  }

  // Mobile browsers (Android, iPhone, iPod) don't support inline PDF rendering
  // via <object> tags — serve the raw PDF directly instead of the viewer wrapper
  const ua = request.headers.get('User-Agent') || '';
  if (/Android|iPhone|iPod/i.test(ua)) {
    return serveRawPdf(path, url.origin, env);
  }

  // Extract matter ID from the path: /mergers/{MN,WA}-XXXXX/filename.pdf
  const match = path.match(/^\/mergers\/((MN|WA)-\d+)\//i);
  if (!match) {
    return context.next();
  }

  const matterId = match[1].toUpperCase();
  const canonicalPath = canonicalisePath(path);
  const displayName = safeDecode(path.split('/').pop()).replace(/\.pdf$/i, '');

  const html = renderViewer({
    matterId,
    displayName,
    rawPdfUrl: `${canonicalPath}?raw=1`,
    mergerPageUrl: `/mergers/${matterId}`,
  });

  // Security headers — Pages Functions override the top-level _headers file for
  // any response they produce, so we repeat the baseline set here. The CSP
  // mirrors public/_headers with the additions needed by this inline viewer:
  //   • style-src 'unsafe-inline' for the <style> block rendered in the HTML
  //   • object-src 'self' for the <object data="...pdf"> preview
  const csp = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self' data:",
    "connect-src 'self'",
    "object-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "upgrade-insecure-requests",
  ].join('; ');

  return new Response(html, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'public, max-age=3600',
      'Content-Security-Policy': csp,
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'Referrer-Policy': 'strict-origin-when-cross-origin',
    },
  });
}
