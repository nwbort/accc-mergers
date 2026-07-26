// Build-time prerendering for merger detail pages.
//
// The frontend is a client-side React SPA: `vite build` emits a single
// `index.html` that every route shares, and the per-page <title>, description
// and <link rel="canonical"> are only injected once JavaScript runs (via
// react-helmet-async in src/components/SEO.jsx). Search engines do most of
// their duplicate-clustering and canonical selection on the *raw* HTML, before
// the deferred render pass — and because every merger URL returns byte-for-byte
// identical HTML, Google clusters unrelated mergers together and picks an
// arbitrary URL as the cluster's canonical (e.g. WA-35022 -> MN-10007).
//
// This Vite plugin fixes that at the source. After the bundle is written it
// stamps a static, differentiated HTML file into `dist/mergers/{id}/{slug}/`
// for every merger, carrying the correct title, description, canonical, Open
// Graph/Twitter tags, JSON-LD and a real body summary in the raw markup. The
// file still boots the SPA (the module script is untouched), so `createRoot`
// replaces the prerendered #root on mount and users get the full interactive
// page. Crawlers and users receive the same HTML — no cloaking.

import { readFileSync, writeFileSync, readdirSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { mergerPath } from './src/utils/slug.js';

const SITE_URL = 'https://mergers.fyi';
// Per-merger data files are named by matter id, e.g. MN-01016.json / WA-70017.json.
const MATTER_FILE_RE = /^(MN|WA)-\d+\.json$/i;

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// A human-readable date for the body summary, e.g. "15 August 2025". Falls back
// to an empty string when the value is missing or unparseable.
function formatDate(value) {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

function partyNames(parties) {
  return (parties ?? []).map((p) => p.name).filter(Boolean);
}

// The <title> and description here MUST mirror what src/pages/MergerDetail.jsx
// passes to <SEO> so the prerendered head matches the client-rendered head.
function pageMeta(merger) {
  const acquirers = partyNames(merger.acquirers);
  const targets = partyNames(merger.targets);
  const title = `${merger.merger_name} | Australian Merger Tracker`;
  const description =
    merger.merger_description ||
    `ACCC merger review: ${acquirers.join(', ')} acquiring ${targets.join(', ')}. Status: ${merger.status}`;
  return { title, description, acquirers, targets };
}

function buildStructuredData(merger, canonicalUrl) {
  const acquirers = partyNames(merger.acquirers);
  const targets = partyNames(merger.targets);
  const modifiedTime =
    merger.determination_publication_date || merger.effective_notification_datetime;

  const articleSchema = {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: merger.merger_name,
    description:
      merger.merger_description ||
      `Merger between ${acquirers.join(', ')} and ${targets.join(', ')}`,
    datePublished: merger.effective_notification_datetime,
    dateModified: modifiedTime,
    mainEntityOfPage: { '@type': 'WebPage', '@id': canonicalUrl },
    author: { '@type': 'Person', name: 'Nick Twort', url: SITE_URL },
    publisher: {
      '@type': 'Organization',
      name: 'Australian Merger Tracker',
      url: SITE_URL,
      logo: { '@type': 'ImageObject', url: `${SITE_URL}/og-image.png` },
    },
    about: [
      ...acquirers.map((name) => ({ '@type': 'Organization', name })),
      ...targets.map((name) => ({ '@type': 'Organization', name })),
    ],
  };

  const breadcrumbSchema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: SITE_URL },
      { '@type': 'ListItem', position: 2, name: 'Mergers', item: `${SITE_URL}/mergers` },
      { '@type': 'ListItem', position: 3, name: merger.merger_name, item: canonicalUrl },
    ],
  };

  return [articleSchema, breadcrumbSchema];
}

// A small, real body rendered into #root so the raw HTML carries unique,
// crawlable content. React (createRoot) replaces it wholesale on mount, so it
// never has to match the live DOM — it only has to be accurate and unique.
function buildBody(merger, canonicalUrl, meta) {
  const list = (names) =>
    names.length
      ? `<ul>${names.map((n) => `<li>${escapeHtml(n)}</li>`).join('')}</ul>`
      : '';

  const facts = [
    ['Status', merger.status],
    ['ACCC determination', merger.accc_determination],
    ['Stage', merger.stage],
    ['Notified', formatDate(merger.effective_notification_datetime)],
    ['Determination published', formatDate(merger.determination_publication_date)],
  ].filter(([, v]) => v);

  return `<div id="root"><main>
<nav aria-label="Breadcrumb"><a href="/">Home</a> / <a href="/mergers">Mergers</a> / ${escapeHtml(merger.merger_name)}</nav>
<article>
<h1>${escapeHtml(merger.merger_name)}</h1>
<p>${escapeHtml(meta.description)}</p>
<dl>${facts.map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd>`).join('')}</dl>
${meta.acquirers.length ? `<section><h2>Acquirers</h2>${list(meta.acquirers)}</section>` : ''}
${meta.targets.length ? `<section><h2>Targets</h2>${list(meta.targets)}</section>` : ''}
<p><a href="${escapeHtml(canonicalUrl)}">View full merger details on mergers.fyi</a></p>
</article>
</main></div>`;
}

// Produce the per-merger HTML by stamping page-specific values into the shared
// built template. Tag-targeted regexes keep this resilient to unrelated changes
// in index.html (inlined CSS, hashed script names, etc.).
function renderPage(template, merger) {
  const path = mergerPath(merger.merger_id, merger.merger_name);
  const canonicalUrl = `${SITE_URL}${path}`;
  const meta = pageMeta(merger);
  const title = escapeHtml(meta.title);
  const description = escapeHtml(meta.description);
  const structuredData = buildStructuredData(merger, canonicalUrl);
  const publishedTime = merger.effective_notification_datetime;
  const modifiedTime =
    merger.determination_publication_date || merger.effective_notification_datetime;

  const headExtras = [
    `<link rel="canonical" href="${escapeHtml(canonicalUrl)}" />`,
    '<meta property="og:locale" content="en_AU" />',
    publishedTime
      ? `<meta property="article:published_time" content="${escapeHtml(publishedTime)}" />`
      : '',
    modifiedTime
      ? `<meta property="article:modified_time" content="${escapeHtml(modifiedTime)}" />`
      : '',
    `<script type="application/ld+json">${JSON.stringify(structuredData)}</script>`,
  ]
    .filter(Boolean)
    .join('\n    ');

  return template
    .replace(/<title>[\s\S]*?<\/title>/, `<title>${title}</title>`)
    .replace(/<meta name="description"[^>]*>/, `<meta name="description" content="${description}" />`)
    .replace(/<meta property="og:type"[^>]*>/, '<meta property="og:type" content="article" />')
    .replace(/<meta property="og:title"[^>]*>/, `<meta property="og:title" content="${title}" />`)
    .replace(/<meta property="og:description"[^>]*>/, `<meta property="og:description" content="${description}" />`)
    .replace(/<meta property="og:url"[^>]*>/, `<meta property="og:url" content="${escapeHtml(canonicalUrl)}" />`)
    .replace(/<meta name="twitter:title"[^>]*>/, `<meta name="twitter:title" content="${title}" />`)
    .replace(/<meta name="twitter:description"[^>]*>/, `<meta name="twitter:description" content="${description}" />`)
    .replace(/<\/head>/, `    ${headExtras}\n  </head>`)
    .replace(/<div id="root"><\/div>/, buildBody(merger, canonicalUrl, meta));
}

export default function prerenderMergers() {
  let outDir;
  let publicDir;

  return {
    name: 'prerender-mergers',
    apply: 'build',
    enforce: 'post',
    configResolved(config) {
      outDir = config.build.outDir;
      publicDir = config.publicDir;
    },
    closeBundle() {
      const template = readFileSync(join(outDir, 'index.html'), 'utf8');
      const dataDir = join(publicDir, 'data', 'mergers');

      let files;
      try {
        files = readdirSync(dataDir).filter((f) => MATTER_FILE_RE.test(f));
      } catch {
        this.warn(`prerender-mergers: no merger data at ${dataDir}, skipping`);
        return;
      }

      let count = 0;
      for (const file of files) {
        let merger;
        try {
          merger = JSON.parse(readFileSync(join(dataDir, file), 'utf8'));
        } catch (err) {
          this.warn(`prerender-mergers: skipping ${file}: ${err.message}`);
          continue;
        }
        if (!merger.merger_id || !merger.merger_name) continue;

        // Emit at the slugged path (which matches the sitemap and canonical);
        // fall back to the bare-id directory when no slug can be derived.
        const path = mergerPath(merger.merger_id, merger.merger_name);
        const outFile = join(outDir, path.replace(/^\//, ''), 'index.html');
        mkdirSync(dirname(outFile), { recursive: true });
        writeFileSync(outFile, renderPage(template, merger));
        count++;
      }

      this.info(`prerender-mergers: wrote ${count} merger page(s)`);
    },
  };
}
