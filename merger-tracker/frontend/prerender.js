// Build-time prerendering for every crawlable route.
//
// The frontend is a client-side React SPA: `vite build` emits a single
// `index.html` that every route shares, and the per-page <title>, description
// and <link rel="canonical"> are only injected once JavaScript runs (via
// react-helmet-async in src/components/SEO.jsx). Search engines do most of
// their duplicate-clustering and canonical selection on the *raw* HTML, before
// the deferred render pass — and because every URL returns byte-for-byte
// identical HTML, Google clusters unrelated pages together and picks an
// arbitrary URL as the cluster's canonical (e.g. WA-35022 -> MN-10007).
//
// This Vite plugin fixes that at the source. After the bundle is written it
// stamps a static, differentiated HTML file into `dist/` for every merger,
// party, industry and static route, carrying the correct title, description,
// canonical, Open Graph/Twitter tags, JSON-LD and a real body summary in the
// raw markup. Each file still boots the SPA (the module script is untouched),
// so `createRoot` replaces the prerendered #root on mount and users get the
// full interactive page. Crawlers and users receive the same HTML — no
// cloaking.
//
// Coverage is deliberately wider than the sitemap. `scripts/generate_sitemap.py`
// omits single-merger parties and empty industry nodes to focus crawl budget,
// but those pages are still reachable through in-app links (every party chip on
// a merger page links to one), so crawlers reach them regardless. Prerendering
// them too is what keeps them from re-forming the identical-HTML cluster that
// this plugin exists to break.

import { readFileSync, writeFileSync, readdirSync, mkdirSync } from 'node:fs';
import { join, dirname, basename } from 'node:path';
import {
  SITE_URL,
  STATIC_PAGE_META,
  fullTitle,
  industryMeta,
  mergerMeta,
  partyMeta,
  serialiseJsonLd,
} from './src/utils/pageMeta.js';
import { industryPath, mergerPath } from './src/utils/slug.js';

// Per-merger data files are named by matter id, e.g. MN-01016.json / WA-70017.json.
const MATTER_FILE_RE = /^(MN|WA)-\d+\.json$/i;
const JSON_FILE_RE = /\.json$/i;

// Cap on how many merger links a party/industry body lists. The busiest
// industry node carries ~66 mergers, so this only bites on pathological cases;
// it exists to stop one outlier node inflating the HTML payload.
const MAX_BODY_LINKS = 100;

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

function list(items) {
  return items.length ? `<ul>${items.map((i) => `<li>${i}</li>`).join('')}</ul>` : '';
}

function definitions(pairs) {
  const kept = pairs.filter(([, v]) => v);
  if (!kept.length) return '';
  return `<dl>${kept
    .map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd>`)
    .join('')}</dl>`;
}

// Merger rows appear on both party and industry pages with the same shape.
// Links use the slugged path so internal links point at the canonical URL
// rather than the bare `/mergers/{id}` form, which the SPA only rewrites once
// JavaScript runs and which has no prerendered file of its own.
function mergerLinks(mergers) {
  return list(
    mergers.slice(0, MAX_BODY_LINKS).map((m) => {
      const href = mergerPath(m.merger_id, m.merger_name);
      const outcome = m.determination || m.status;
      return (
        `<a href="${escapeHtml(href)}">${escapeHtml(m.merger_name)}</a>` +
        (outcome ? ` — ${escapeHtml(outcome)}` : '')
      );
    }),
  );
}

function breadcrumbHtml(trail, current) {
  const links = trail
    .map((c) => `<a href="${escapeHtml(c.path)}">${escapeHtml(c.name)}</a>`)
    .join(' / ');
  return `<nav aria-label="Breadcrumb">${links} / ${escapeHtml(current)}</nav>`;
}

// Bodies rendered into #root so the raw HTML carries unique, crawlable content
// and real internal links. React (createRoot) replaces them wholesale on mount,
// so they never have to match the live DOM — only to be accurate and unique.

export function mergerBody(merger, meta) {
  const facts = [
    ['Status', merger.status],
    ['ACCC determination', merger.accc_determination],
    ['Stage', merger.stage],
    ['Notified', formatDate(merger.effective_notification_datetime)],
    ['Determination published', formatDate(merger.determination_publication_date)],
  ];

  return `<main>
${breadcrumbHtml([{ name: 'Home', path: '/' }, { name: 'Mergers', path: '/mergers' }], merger.merger_name)}
<article>
<h1>${escapeHtml(merger.merger_name)}</h1>
<p>${escapeHtml(meta.description)}</p>
${definitions(facts)}
${meta.acquirers.length ? `<section><h2>Acquirers</h2>${list(meta.acquirers.map(escapeHtml))}</section>` : ''}
${meta.targets.length ? `<section><h2>Targets</h2>${list(meta.targets.map(escapeHtml))}</section>` : ''}
<p><a href="${escapeHtml(SITE_URL + meta.path)}">View full merger details on mergers.fyi</a></p>
</article>
</main>`;
}

export function partyBody(party, meta) {
  const roleSections = [
    ['acquirer', 'As acquirer'],
    ['target', 'As target'],
    ['other', 'As other party'],
  ]
    .map(([role, heading]) => {
      const mergers = party.mergers?.[role] || [];
      if (!mergers.length) return '';
      return `<section><h2>${heading}</h2>${mergerLinks(mergers)}</section>`;
    })
    .join('');

  const members = (party.members || []).map((m) => m?.name).filter(Boolean);

  const facts = [
    ['Total reviews', party.merger_count],
    ['Phase 1 reviews', party.phase_1_count],
    ['Phase 2 reviews', party.phase_2_count],
    ['Waivers', party.waiver_count],
    ['Under assessment', party.active_count],
  ].map(([k, v]) => [k, v ? String(v) : '']);

  return `<main>
${breadcrumbHtml([{ name: 'Home', path: '/' }, { name: 'Parties', path: '/parties' }], meta.name)}
<article>
<h1>${escapeHtml(meta.name)}</h1>
<p>${escapeHtml(meta.description)}</p>
${definitions(facts)}
${members.length > 1 ? `<section><h2>Related entities</h2>${list(members.map(escapeHtml))}</section>` : ''}
${roleSections}
</article>
</main>`;
}

export function industryBody(industry, code, meta) {
  const trail = [
    { name: 'Home', path: '/' },
    { name: 'Industries', path: '/industries' },
  ];

  const children = (industry.children || [])
    .filter((c) => c?.code)
    .map((c) => {
      const href = industryPath(c.code, c.name);
      return `<a href="${escapeHtml(href)}">${escapeHtml(c.name || c.code)}</a>`;
    });

  const facts = [
    ['ANZSIC code', code],
    ['Level', meta.levelLabel],
    ['Total reviews', industry.count],
    ['Phase 2 reviews', industry.phase_2_count],
    ['Waivers', industry.waiver_count],
    ['Under assessment', industry.active_count],
  ].map(([k, v]) => [k, v ? String(v) : '']);

  return `<main>
${breadcrumbHtml(trail, meta.name)}
<article>
<h1>${escapeHtml(meta.name)}</h1>
<p>${escapeHtml(meta.description)}</p>
${definitions(facts)}
${children.length ? `<section><h2>Sub-industries</h2>${list(children)}</section>` : ''}
${meta.mergers.length ? `<section><h2>Mergers in this industry</h2>${mergerLinks(meta.mergers)}</section>` : ''}
</article>
</main>`;
}

export function staticBody(meta) {
  return `<main>
<article>
<h1>${escapeHtml(meta.title)}</h1>
<p>${escapeHtml(meta.description)}</p>
<p><a href="${escapeHtml(SITE_URL + meta.path)}">Open on mergers.fyi</a></p>
</article>
</main>`;
}

// Produce the page HTML by stamping page-specific values into the shared built
// template. Tag-targeted regexes keep this resilient to unrelated changes in
// index.html (inlined CSS, hashed script names, etc.).
export function renderPage(template, meta, body) {
  const canonicalUrl = `${SITE_URL}${meta.path}`;
  const title = escapeHtml(fullTitle(meta.title));
  const description = escapeHtml(meta.description);
  const type = meta.type || 'website';

  const headExtras = [
    `<link rel="canonical" href="${escapeHtml(canonicalUrl)}" />`,
    '<meta property="og:locale" content="en_AU" />',
    type === 'article' && meta.publishedTime
      ? `<meta property="article:published_time" content="${escapeHtml(meta.publishedTime)}" />`
      : '',
    type === 'article' && meta.modifiedTime
      ? `<meta property="article:modified_time" content="${escapeHtml(meta.modifiedTime)}" />`
      : '',
    type === 'article' && meta.section
      ? `<meta property="article:section" content="${escapeHtml(meta.section)}" />`
      : '',
    meta.structuredData?.length
      ? `<script type="application/ld+json">${serialiseJsonLd(meta.structuredData)}</script>`
      : '',
  ]
    .filter(Boolean)
    .join('\n    ');

  return template
    .replace(/<title>[\s\S]*?<\/title>/, `<title>${title}</title>`)
    .replace(/<meta name="description"[^>]*>/, `<meta name="description" content="${description}" />`)
    .replace(/<meta property="og:type"[^>]*>/, `<meta property="og:type" content="${type}" />`)
    .replace(/<meta property="og:title"[^>]*>/, `<meta property="og:title" content="${title}" />`)
    .replace(/<meta property="og:description"[^>]*>/, `<meta property="og:description" content="${description}" />`)
    .replace(/<meta property="og:url"[^>]*>/, `<meta property="og:url" content="${escapeHtml(canonicalUrl)}" />`)
    .replace(/<meta name="twitter:title"[^>]*>/, `<meta name="twitter:title" content="${title}" />`)
    .replace(/<meta name="twitter:description"[^>]*>/, `<meta name="twitter:description" content="${description}" />`)
    .replace(/<\/head>/, `    ${headExtras}\n  </head>`)
    .replace(/<div id="root"><\/div>/, `<div id="root">${body}</div>`);
}

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

// `/mergers/MN-1/foo` -> `dist/mergers/MN-1/foo/index.html`; `/` -> `dist/index.html`.
// The root is skipped by the caller: overwriting dist/index.html would replace
// the template every other page is stamped from, and the SPA fallback already
// serves it.
function writePage(outDir, path, html) {
  const outFile = join(outDir, path.replace(/^\//, ''), 'index.html');
  mkdirSync(dirname(outFile), { recursive: true });
  writeFileSync(outFile, html);
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
      const dataDir = join(publicDir, 'data');
      const counts = { mergers: 0, parties: 0, industries: 0, static: 0 };

      // Reads every *.json in `dir`, maps it through `toPage`, and writes the
      // result. A malformed or unrecognised file is warned about and skipped so
      // one bad record can't fail the build.
      const renderDir = (dir, kind, toPage, fileFilter = JSON_FILE_RE) => {
        let files;
        try {
          files = readdirSync(dir).filter((f) => fileFilter.test(f));
        } catch {
          this.warn(`prerender: no ${kind} data at ${dir}, skipping`);
          return;
        }

        for (const file of files) {
          let page;
          try {
            page = toPage(readJson(join(dir, file)), basename(file, '.json'));
          } catch (err) {
            this.warn(`prerender: skipping ${kind}/${file}: ${err.message}`);
            continue;
          }
          if (!page) continue;
          writePage(outDir, page.meta.path, renderPage(template, page.meta, page.body));
          counts[kind]++;
        }
      };

      renderDir(
        join(dataDir, 'mergers'),
        'mergers',
        (merger) => {
          if (!merger.merger_id || !merger.merger_name) return null;
          const meta = mergerMeta(merger);
          return { meta, body: mergerBody(merger, meta) };
        },
        MATTER_FILE_RE,
      );

      // parties.json is the set of party pages the app actually links to. The
      // pipeline writes detail files without pruning, so ids that have since
      // been folded into a hand-declared canonical group leave a stale file
      // behind. Those pages are unreachable in-app; prerendering them would
      // hand crawlers a differentiated, indexable duplicate of a party that
      // now lives under its group page.
      let livePartyIds = null;
      try {
        const index = readJson(join(dataDir, 'parties.json'));
        livePartyIds = new Set((index.parties || index).map((p) => p.id));
      } catch {
        this.warn('prerender: parties.json unreadable, prerendering every party file');
      }

      renderDir(join(dataDir, 'parties'), 'parties', (party, id) => {
        const partyId = party.id || id;
        if (livePartyIds && !livePartyIds.has(partyId)) return null;
        const meta = partyMeta(party, partyId);
        return { meta, body: partyBody(party, meta) };
      });

      // industries.json supplies the display name for nodes whose detail file
      // carries none, mirroring IndustryDetail.jsx's fallback chain.
      let industryNames = {};
      try {
        const index = readJson(join(dataDir, 'industries.json'));
        const rows = index.industries || index;
        industryNames = Object.fromEntries(rows.map((r) => [r.code, r.name]));
      } catch {
        this.warn('prerender: industries.json unreadable, falling back to detail-file names');
      }

      renderDir(join(dataDir, 'industries'), 'industries', (industry, code) => {
        const meta = industryMeta(industry, industry.code || code, industryNames[code]);
        return { meta, body: industryBody(industry, industry.code || code, meta) };
      });

      for (const [path, base] of Object.entries(STATIC_PAGE_META)) {
        // The homepage is dist/index.html — the very template being stamped.
        if (path === '/') continue;
        const meta = { ...base, path };
        writePage(outDir, path, renderPage(template, meta, staticBody(meta)));
        counts.static++;
      }

      const total = Object.values(counts).reduce((a, b) => a + b, 0);
      this.info(
        `prerender: wrote ${total} page(s) — ${counts.mergers} merger, ` +
          `${counts.parties} party, ${counts.industries} industry, ${counts.static} static`,
      );
    },
  };
}
