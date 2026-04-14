const DOWNLOAD_ICON = '<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';

const DOCUMENT_ICON = '<svg width="28" height="28" fill="none" stroke="#9ca3af" stroke-width="1.5" viewBox="0 0 24 24"><path d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"/></svg>';

const CSS = `
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f8f9fa}
.banner{display:flex;align-items:center;justify-content:space-between;height:52px;padding:0 20px;background:#335145;color:#fff;font-size:14px;gap:16px}
.banner a{color:#a7f3d0;text-decoration:none}
.banner a:hover{color:#fff;text-decoration:underline}
.left{display:flex;align-items:center;gap:10px;min-width:0}
.site{font-weight:600;white-space:nowrap}
.sep{color:rgba(255,255,255,.3)}
.doc{color:rgba(255,255,255,.75);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.right{display:flex;align-items:center;gap:10px;flex-shrink:0}
.btn{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border-radius:8px;font-size:13px;font-weight:500;text-decoration:none!important;white-space:nowrap;transition:background .15s,border-color .15s}
.btn-ghost{border:1px solid rgba(255,255,255,.25);color:#fff}
.btn-ghost:hover{background:rgba(255,255,255,.1);border-color:rgba(255,255,255,.4);color:#fff}
.btn-primary{background:#10b981;color:#fff}
.btn-primary:hover{background:#059669;color:#fff}
.viewer{height:calc(100vh - 52px)}
.viewer object{width:100%;height:100%;border:none}
.fallback{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:16px;padding:32px;text-align:center;color:#4b5563}
.fallback-icon{width:64px;height:64px;border-radius:16px;background:#f3f4f6;display:flex;align-items:center;justify-content:center}
.fallback p{max-width:360px;line-height:1.5}
.fallback .btn-dl{background:#335145;color:#fff;padding:10px 20px;font-size:14px;border-radius:10px;text-decoration:none!important}
.fallback .btn-dl:hover{background:#223a30;color:#fff}
@media(max-width:640px){.banner{padding:0 12px;gap:8px}.doc,.sep{display:none}.btn span.label{display:none}}
`.trim();

function esc(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function renderViewer({ matterId, displayName, fileName, rawPdfUrl, mergerPageUrl }) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>${esc(displayName)} – ${esc(matterId)} | Australian Merger Tracker</title>
  <meta name="description" content="Document from ACCC merger review ${esc(matterId)}: ${esc(displayName)}. View the full merger details on mergers.fyi.">
  <link rel="canonical" href="https://mergers.fyi${mergerPageUrl}">
  <style>${CSS}</style>
</head>
<body>
  <div class="banner">
    <div class="left">
      <a href="/" class="site">mergers.fyi</a>
      <span class="sep">|</span>
      <span class="doc">${esc(displayName)}</span>
    </div>
    <div class="right">
      <a href="${esc(rawPdfUrl)}" class="btn btn-ghost" download="${esc(fileName)}">
        ${DOWNLOAD_ICON}
        <span class="label">Download</span>
      </a>
      <a href="${esc(mergerPageUrl)}" class="btn btn-primary">
        View merger &rarr;
      </a>
    </div>
  </div>
  <div class="viewer">
    <object data="${esc(rawPdfUrl)}" type="application/pdf">
      <div class="fallback">
        <div class="fallback-icon">${DOCUMENT_ICON}</div>
        <p>PDF preview isn't available in your browser.</p>
        <a href="${esc(rawPdfUrl)}" class="btn btn-dl" download="${esc(fileName)}">Download PDF</a>
      </div>
    </object>
  </div>
</body>
</html>`;
}
