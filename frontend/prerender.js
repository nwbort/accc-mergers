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
// Coverage is deliberately wider than the sitemap. `scripts/generate/generate_sitemap.py`
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

// ---------------------------------------------------------------------------
// Styling
//
// The prerendered markup is what the user looks at between first paint and
// React mounting — measured at roughly 400ms on a fast connection and about a
// second when the bundles are slow. Unclassed markup spends that window as raw
// browser-default text, which is a visibly broken-looking page, so these
// helpers reuse the same Tailwind classes as the real components.
//
// The class strings are duplicated rather than imported because the components
// build them inside JSX; the goal is only that the static page reads as a
// plausible version of the real one, not that it matches pixel for pixel.
//
// IMPORTANT: Tailwind only emits classes it finds in the files listed under
// `content` in tailwind.config.js. This file is listed there for that reason —
// a class used only here is otherwise purged from the stylesheet and silently
// does nothing.
// ---------------------------------------------------------------------------

const CARD = 'bg-white rounded-2xl border border-gray-100 shadow-card';
const SECTION_HEADING = 'text-xs font-medium text-gray-500 uppercase tracking-wider';
const PAGE_WRAP = 'max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8';
const LINK = 'text-gray-900 hover:text-primary transition-colors';

function list(items, itemClass = 'text-sm text-gray-700') {
  if (!items.length) return '';
  return `<ul class="space-y-1">${items
    .map((i) => `<li class="${itemClass}">${i}</li>`)
    .join('')}</ul>`;
}

// The 2x4 stat grid the party and industry pages render through DetailStatGrid.
// A zero is a real value there — DetailStatGrid renders "0" rather than hiding
// the card — so only null/undefined/empty count as absent. Dropping zeros here
// would give the prerendered page fewer cards than the hydrated one and shove
// everything below the grid upwards when React mounts.
function statGrid(pairs) {
  const kept = pairs
    .filter(([, v]) => v != null && v !== '')
    .map(([k, v]) => [k, String(v)]);
  if (!kept.length) return '';
  const cards = kept
    .map(
      ([label, value]) =>
        `<div class="bg-white p-5 rounded-2xl border border-gray-100 shadow-card">` +
        `<p class="${SECTION_HEADING}">${escapeHtml(label)}</p>` +
        `<p class="text-2xl font-bold text-gray-900 mt-1.5 tracking-tight tabular-nums">${escapeHtml(value)}</p>` +
        `</div>`,
    )
    .join('');
  return `<div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">${cards}</div>`;
}

function section(heading, inner) {
  if (!inner) return '';
  return (
    `<div class="mb-8">` +
    `<h2 class="${SECTION_HEADING} mb-3">${escapeHtml(heading)}</h2>` +
    inner +
    `</div>`
  );
}

// Merger rows appear on both party and industry pages with the same shape.
// Links use the slugged path so internal links point at the canonical URL
// rather than the bare `/mergers/{id}` form, which the SPA only rewrites once
// JavaScript runs and which has no prerendered file of its own.
function mergerLinks(mergers) {
  const rows = mergers.slice(0, MAX_BODY_LINKS).map((m) => {
    const href = mergerPath(m.merger_id, m.merger_name);
    const outcome = m.determination || m.status;
    return (
      `<a href="${escapeHtml(href)}" class="text-base font-semibold ${LINK}">${escapeHtml(m.merger_name)}</a>` +
      (outcome ? `<span class="block text-sm text-gray-500 mt-0.5">${escapeHtml(outcome)}</span>` : '')
    );
  });
  if (!rows.length) return '';
  return (
    `<div class="${CARD} p-5"><ul class="space-y-3">` +
    rows.map((r) => `<li>${r}</li>`).join('') +
    `</ul></div>`
  );
}

function breadcrumbHtml(trail, current) {
  const crumbs = trail.map(
    (c) =>
      `<li><a href="${escapeHtml(c.path)}" class="hover:text-primary transition-colors">${escapeHtml(c.name)}</a></li>`,
  );
  crumbs.push(`<li aria-current="page"><span class="font-medium text-gray-700">${escapeHtml(current)}</span></li>`);
  return (
    `<nav aria-label="Breadcrumb" class="mb-5">` +
    `<ol class="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-sm text-gray-500">${crumbs.join(
      '<li aria-hidden="true" class="text-gray-300">/</li>',
    )}</ol>` +
    `</nav>`
  );
}

// The page header card, matching the `card-accent` treatment the detail pages
// use (a gradient hairline along the top edge).
function headerCard(title, subtitle, extra = '') {
  return (
    `<div class="${CARD} p-6 mb-6 card-accent">` +
    `<h1 class="text-2xl font-bold text-gray-900 tracking-tight">${escapeHtml(title)}</h1>` +
    (subtitle ? `<p class="text-sm text-gray-500 mt-1">${escapeHtml(subtitle)}</p>` : '') +
    extra +
    `</div>`
  );
}

// Mirrors App.jsx's shell: the gradient background, and a fixed bar matching
// the navbar's height so content sits at the same offset before and after
// React mounts. The bar carries the brand only — the real navbar's links are
// interactive and stateful, and a static copy of them would go stale.
function shell(inner) {
  return (
    `<div class="min-h-screen gradient-mesh flex flex-col">` +
    `<div class="fixed top-0 left-0 right-0 z-50 bg-white border-b border-gray-100">` +
    `<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">` +
    `<div class="flex items-center h-16">` +
    `<a href="/" class="text-lg font-bold tracking-tight text-gray-900">australian merger tracker</a>` +
    `</div></div></div>` +
    `<main id="main-content" class="flex-grow pt-16">` +
    `<div class="${PAGE_WRAP}">${inner}</div>` +
    `</main>` +
    `</div>`
  );
}

// Bodies rendered into #root so the raw HTML carries unique, crawlable content
// and real internal links. React (createRoot) replaces them wholesale on mount,
// so they never have to match the live DOM — only to be accurate and unique.

export function mergerBody(merger, meta) {
  const stats = [
    ['Status', merger.status],
    ['Determination', merger.accc_determination],
    ['Stage', merger.stage],
    ['Notified', formatDate(merger.effective_notification_datetime)],
  ];

  const parties = (heading, values) =>
    section(heading, values.length ? `<div class="${CARD} p-5">${list(values.map(escapeHtml))}</div>` : '');

  return shell(
    breadcrumbHtml(
      [{ name: 'Home', path: '/' }, { name: 'Mergers', path: '/mergers' }],
      merger.merger_name,
    ) +
      headerCard(
        merger.merger_name,
        merger.merger_id,
        `<p class="text-sm text-gray-600 mt-3">${escapeHtml(meta.description)}</p>`,
      ) +
      statGrid(stats) +
      parties('Acquirers', meta.acquirers) +
      parties('Targets', meta.targets),
  );
}

export function partyBody(party, meta) {
  const roleSections = [
    ['acquirer', 'As acquirer'],
    ['target', 'As target'],
    ['other', 'As other party'],
  ]
    .map(([role, heading]) => section(heading, mergerLinks(party.mergers?.[role] || [])))
    .join('');

  // PartyDetail shows the first MEMBERS_PREVIEW_COUNT members behind a "show
  // more" toggle. Matching that count (and the ABN suffix) keeps the card the
  // same height before and after React mounts, so hydration doesn't shove the
  // rest of the page down.
  const MEMBERS_PREVIEW_COUNT = 3;
  const allMembers = (party.members || []).filter((m) => m?.name);
  const memberRows = allMembers.slice(0, MEMBERS_PREVIEW_COUNT).map((m) => {
    const id = m.identifier
      ? `<span class="text-gray-500"> &middot; ${escapeHtml(
          m.identifier_type ? `${m.identifier_type}: ` : '',
        )}${escapeHtml(m.identifier)}</span>`
      : '';
    return `${escapeHtml(m.name)}${id}`;
  });
  const remaining = allMembers.length - MEMBERS_PREVIEW_COUNT;
  const relatedEntities =
    allMembers.length > 1
      ? `<div class="mt-4 pt-4 border-t border-gray-100">` +
        `<h2 class="${SECTION_HEADING} mb-2">Related parties</h2>` +
        list(memberRows) +
        (remaining > 0
          ? `<p class="text-sm text-primary font-medium mt-2">Show ${remaining} more</p>`
          : '') +
        `</div>`
      : '';

  const stats = [
    ['Total reviews', party.merger_count],
    ['Phase 2 reviews', party.phase_2_count],
    ['Waivers', party.waiver_count],
    ['Under assessment', party.active_count],
  ];

  return shell(
    breadcrumbHtml([{ name: 'Home', path: '/' }, { name: 'Parties', path: '/parties' }], meta.name) +
      headerCard(
        meta.name,
        `${meta.mergerCount} merger${meta.mergerCount !== 1 ? 's' : ''}`,
        relatedEntities,
      ) +
      statGrid(stats) +
      roleSections,
  );
}

export function industryBody(industry, code, meta) {
  const children = (industry.children || [])
    .filter((c) => c?.code)
    .map((c) => {
      const href = industryPath(c.code, c.name);
      return `<a href="${escapeHtml(href)}" class="text-sm font-medium ${LINK}">${escapeHtml(c.name || c.code)}</a>`;
    });

  const stats = [
    ['Total reviews', industry.count],
    ['Phase 2 reviews', industry.phase_2_count],
    ['Waivers', industry.waiver_count],
    ['Under assessment', industry.active_count],
  ];

  const subtitle =
    `ANZSIC ${meta.levelLabel ? `${meta.levelLabel.toLowerCase()} ` : 'code: '}${code}` +
    ` · ${meta.mergers.length} merger${meta.mergers.length !== 1 ? 's' : ''}`;

  // The ANZSIC ancestors are the crumb trail the real page renders.
  const trail = [
    { name: 'Home', path: '/' },
    { name: 'Industries', path: '/industries' },
    ...(industry.ancestors || []).map((a) => ({
      name: a.name,
      path: industryPath(a.code, a.name),
    })),
  ];

  return shell(
    breadcrumbHtml(trail, meta.name) +
      headerCard(meta.name, subtitle) +
      statGrid(stats) +
      section('Sub-industries', children.length ? `<div class="${CARD} p-5">${list(children)}</div>` : '') +
      section('Mergers in this industry', mergerLinks(meta.mergers)),
  );
}

export function staticBody(meta) {
  return shell(
    headerCard(
      meta.title,
      '',
      `<p class="text-sm text-gray-600 mt-3">${escapeHtml(meta.description)}</p>`,
    ),
  );
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
