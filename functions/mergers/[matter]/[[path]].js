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
  const fileName = decodeURIComponent(path.split('/').pop());

  const html = renderViewer({
    matterId,
    displayName: fileName.replace(/\.pdf$/i, ''),
    fileName,
    rawPdfUrl: `${path}?raw=1`,
    mergerPageUrl: `/mergers/${matterId}`,
  });

  return new Response(html, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'public, max-age=3600',
    },
  });
}
