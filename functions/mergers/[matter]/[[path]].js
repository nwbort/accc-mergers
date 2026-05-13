import { renderViewer } from '../../_lib/pdf-viewer.js';

const BOT_UA_RE = /LinkedInBot|facebookexternalhit|Twitterbot|Slackbot|Discordbot|TelegramBot|WhatsApp|Googlebot|bingbot|Pinterestbot|Applebot|Iframely|rogerbot|embedly|outbrain|quora link preview|Slack|vkShare|W3C_Validator|redditbot|flipboard|tumblr|bitlybot|SkypeUriPreview|nuzzel|Disqus|Google Page Speed|Qwantify|pinterestbot|Baiduspider/i;

function isBotRequest(request) {
  const ua = request.headers.get('User-Agent') || '';
  return BOT_UA_RE.test(ua);
}

function escapeHtml(str) {
  return String(str ?? '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
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

async function serveOgPage(matterId, canonicalUrl, env) {
  const dataUrl = new URL(`/data/mergers/${matterId}.json`, canonicalUrl);
  let merger;
  try {
    const resp = await env.ASSETS.fetch(new Request(dataUrl.toString()));
    if (!resp.ok) return null;
    merger = await resp.json();
  } catch {
    return null;
  }
  return new Response(buildOgHtml(merger, canonicalUrl), {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'public, max-age=3600',
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'strict-origin-when-cross-origin',
    },
  });
}

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const path = url.pathname;

  // For social/crawler bots hitting a top-level merger page, serve a minimal
  // HTML response with specific OG meta tags — bots don't run JS so they would
  // otherwise see only the generic tags in the SPA's index.html.
  const isTopLevel = /^\/mergers\/((MN|WA)-\d+)\/?$/i.test(path);
  if (isTopLevel && isBotRequest(request)) {
    const match = path.match(/^\/mergers\/((MN|WA)-\d+)/i);
    const matterId = match[1].toUpperCase();
    const canonicalUrl = `${url.origin}/mergers/${matterId}`;
    const ogResponse = await serveOgPage(matterId, canonicalUrl, env);
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
    const assetUrl = new URL(path, url.origin);
    return env.ASSETS.fetch(new Request(assetUrl.toString()));
  }

  // Mobile browsers (Android, iPhone, iPod) don't support inline PDF rendering
  // via <object> tags — serve the raw PDF directly instead of the viewer wrapper
  const ua = request.headers.get('User-Agent') || '';
  if (/Android|iPhone|iPod/i.test(ua)) {
    const assetUrl = new URL(path, url.origin);
    return env.ASSETS.fetch(new Request(assetUrl.toString()));
  }

  // Extract matter ID from the path: /mergers/{MN,WA}-XXXXX/filename.pdf
  const match = path.match(/^\/mergers\/((MN|WA)-\d+)\//i);
  if (!match) {
    return context.next();
  }

  const matterId = match[1];
  const displayName = decodeURIComponent(path.split('/').pop()).replace(/\.pdf$/i, '');

  const html = renderViewer({
    matterId,
    displayName,
    rawPdfUrl: `${path}?raw=1`,
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
