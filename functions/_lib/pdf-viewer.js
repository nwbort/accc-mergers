const DOCUMENT_ICON = '<svg width="28" height="28" fill="none" stroke="#9ca3af" stroke-width="1.5" viewBox="0 0 24 24"><path d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"/></svg>';

// FaExclamationCircle, the icon the SPA's ErrorCard shows, in its gray-500.
const ERROR_ICON = '<svg width="32" height="32" fill="#6b7280" viewBox="0 0 512 512" aria-hidden="true"><path d="M504 256c0 136.997-111.043 248-248 248S8 392.997 8 256C8 119.083 119.043 8 256 8s248 111.083 248 248zm-248 50c-25.405 0-46 20.595-46 46s20.595 46 46 46 46-20.595 46-46-20.595-46-46-46zm-43.673-165.346l7.418 136c.347 6.364 5.609 11.346 11.982 11.346h48.546c6.373 0 11.635-4.982 11.982-11.346l7.418-136c.375-6.874-5.098-12.654-11.982-12.654h-63.383c-6.884 0-12.356 5.78-11.981 12.654z"/></svg>';

const CSS = `
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f8f9fa}
.banner{display:flex;align-items:center;justify-content:space-between;height:52px;padding:0 20px;background:#335145;color:#fff;font-size:14px;gap:16px}
.banner a{color:#a7f3d0;text-decoration:none}
.banner a:hover{color:#fff;text-decoration:underline}
.left{display:flex;align-items:center;gap:10px;min-width:0}
.banner a.site{color:#fff;font-size:15px;font-weight:800;white-space:nowrap}
.site .dot{color:#6ee7b7}
.sep{color:rgba(255,255,255,.3)}
.doc{color:rgba(255,255,255,.75);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.right{display:flex;align-items:center;gap:10px;flex-shrink:0}
.btn{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border-radius:8px;font-size:13px;font-weight:500;text-decoration:none!important;white-space:nowrap;transition:background .15s,border-color .15s}
.btn-primary{background:#10b981;color:#fff}
.btn-primary:hover{background:#059669;color:#fff}
.viewer{height:calc(100vh - 52px)}
.viewer object{width:100%;height:100%;border:none}
.fallback{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:16px;padding:32px;text-align:center;color:#4b5563}
.fallback-icon{width:64px;height:64px;border-radius:16px;background:#f3f4f6;display:flex;align-items:center;justify-content:center}
.fallback p{max-width:360px;line-height:1.5}
.fallback .btn-dl{background:#335145;color:#fff;padding:10px 20px;font-size:14px;border-radius:10px;text-decoration:none!important}
.fallback .btn-dl:hover{background:#223a30;color:#fff}
@font-face{font-family:'Inter';font-style:normal;font-display:swap;font-weight:100 900;src:url('/fonts/inter-latin.woff2') format('woff2-variations')}
body.not-found{background:#f8fafc}
.not-found .content{padding:64px 16px}
.error-card{max-width:512px;margin:0 auto;padding:40px;text-align:center;background:#fff;border:1px solid #f3f4f6;border-radius:16px;box-shadow:0 1px 3px 0 rgba(0,0,0,.04),0 1px 2px -1px rgba(0,0,0,.04);font-family:'Inter',-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.error-icon{width:64px;height:64px;margin:0 auto 20px;border-radius:16px;background:#f3f4f6;display:flex;align-items:center;justify-content:center}
.error-card h1{font-size:24px;line-height:32px;font-weight:700;letter-spacing:-.025em;color:#111827;margin-bottom:12px}
.error-card p{color:#6b7280;line-height:1.5;margin-bottom:24px}
.error-card .btn-back{display:inline-flex;align-items:center;padding:10px 20px;font-size:14px;font-weight:500;border-radius:12px;color:#fff;background:#335145;box-shadow:0 1px 2px 0 rgba(0,0,0,.05);text-decoration:none;transition:background .15s}
.error-card .btn-back:hover{background:#223a30}
@media(max-width:640px){.banner{padding:0 12px;gap:8px}.doc,.sep{display:none}}
`.trim();

function esc(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function banner({ displayName, mergerPageUrl, mergerLinkLabel }) {
  return `<div class="banner">
    <div class="left">
      <a href="/" class="site">mergers<span class="dot">.</span>fyi</a>
      <span class="sep">|</span>
      <span class="doc">${esc(displayName)}</span>
    </div>
    <div class="right">
      <a href="${esc(mergerPageUrl)}" class="btn btn-primary">
        ${esc(mergerLinkLabel)} &rarr;
      </a>
    </div>
  </div>`;
}

export function renderViewer({ matterId, displayName, rawPdfUrl, mergerPageUrl }) {
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
  ${banner({ displayName, mergerPageUrl, mergerLinkLabel: 'View merger' })}
  <div class="viewer">
    <object data="${esc(rawPdfUrl)}" type="application/pdf">
      <div class="fallback">
        <div class="fallback-icon">${DOCUMENT_ICON}</div>
        <p>PDF preview isn't available in your browser.</p>
        <a href="${esc(rawPdfUrl)}" class="btn btn-dl">Download PDF</a>
      </div>
    </object>
  </div>
</body>
</html>`;
}

// The same chrome around a "document not found" message, for a PDF path that
// matches no deployed file and no known source URL. Without it the miss falls
// through to the SPA shell, which reads the filename as a slug and quietly
// lands the reader on the matter page. `mergerPageUrl` is the matter page when
// the matter exists, else the merger list — `backLabel` says which. The card
// copies the SPA's ErrorCard (frontend/src/components/ErrorCard.jsx), so this
// reads as the same kind of message as "Merger not found".
export function renderNotFound({ matterId, displayName, mergerPageUrl, backLabel }) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Document not found – ${esc(matterId)} | Australian Merger Tracker</title>
  <meta name="robots" content="noindex">
  <style>${CSS}</style>
</head>
<body class="not-found">
  ${banner({ displayName, mergerPageUrl, mergerLinkLabel: backLabel })}
  <div class="content">
    <div class="error-card">
      <div class="error-icon">${ERROR_ICON}</div>
      <h1>Document not found</h1>
      <p>We couldn't find a document called "${esc(displayName)}.pdf" for ${esc(matterId)}. It may have been renamed or the link might be incorrect.</p>
      <a href="${esc(mergerPageUrl)}" class="btn-back">${esc(backLabel)}</a>
    </div>
  </div>
</body>
</html>`;
}
