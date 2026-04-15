import { renderViewer } from '../../_lib/pdf-viewer.js';

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const path = url.pathname;

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
