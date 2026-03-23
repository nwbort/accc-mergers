#!/usr/bin/env node
/**
 * Static site pre-rendering script.
 *
 * Runs after `vite build` to inject SEO-critical content into every route's
 * HTML file.  For each route it:
 *   1. Sets the correct <title>, <meta>, Open Graph, Twitter, and canonical tags
 *   2. Injects visible text content (headings, descriptions, links) into #root
 *   3. Adds JSON-LD structured data where applicable
 *
 * No browser required — reads data directly from the built JSON files.
 *
 * Usage:  node scripts/prerender.mjs
 */

import { readFileSync, writeFileSync, mkdirSync, readdirSync } from 'fs';
import { resolve, dirname, basename, extname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DIST_DIR = resolve(__dirname, '..', 'dist');
const DATA_DIR = resolve(DIST_DIR, 'data');
const SITE_URL = 'https://mergers.fyi';
const SITE_TITLE = 'Australian Merger Tracker';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function readJSON(path) {
  try {
    return JSON.parse(readFileSync(path, 'utf-8'));
  } catch {
    return null;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function escapeAttr(str) {
  if (!str) return '';
  return str.replace(/"/g, '&quot;').replace(/&/g, '&amp;');
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleDateString('en-AU', {
      day: 'numeric', month: 'short', year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

// ---------------------------------------------------------------------------
// HTML template manipulation
// ---------------------------------------------------------------------------

const templateHtml = readFileSync(resolve(DIST_DIR, 'index.html'), 'utf-8');

/**
 * Build a full HTML page by injecting SEO meta tags and content into the
 * built index.html template.
 */
function buildPage({ title, description, url, type = 'website', structuredData, content }) {
  const fullTitle = title ? `${title} | ${SITE_TITLE}` : `${SITE_TITLE} | ACCC Merger Reviews & M&A Data`;
  const canonicalUrl = `${SITE_URL}${url || '/'}`;
  const ogImage = `${SITE_URL}/og-image.png`;

  let html = templateHtml;

  // Replace <title>
  html = html.replace(
    /<title>[^<]*<\/title>/,
    `<title>${escapeHtml(fullTitle)}</title>`
  );

  // Replace meta description
  html = html.replace(
    /<meta name="description" content="[^"]*" \/>/,
    `<meta name="description" content="${escapeAttr(description)}" />`
  );

  // Replace Open Graph tags
  html = html.replace(
    /<meta property="og:type" content="[^"]*" \/>/,
    `<meta property="og:type" content="${escapeAttr(type)}" />`
  );
  html = html.replace(
    /<meta property="og:title" content="[^"]*" \/>/,
    `<meta property="og:title" content="${escapeAttr(fullTitle)}" />`
  );
  html = html.replace(
    /<meta property="og:description" content="[^"]*" \/>/,
    `<meta property="og:description" content="${escapeAttr(description)}" />`
  );
  html = html.replace(
    /<meta property="og:url" content="[^"]*" \/>/,
    `<meta property="og:url" content="${escapeAttr(canonicalUrl)}" />`
  );

  // Replace Twitter Card tags
  html = html.replace(
    /<meta name="twitter:title" content="[^"]*" \/>/,
    `<meta name="twitter:title" content="${escapeAttr(fullTitle)}" />`
  );
  html = html.replace(
    /<meta name="twitter:description" content="[^"]*" \/>/,
    `<meta name="twitter:description" content="${escapeAttr(description)}" />`
  );

  // Insert canonical link (before </head>)
  if (url) {
    html = html.replace(
      '</head>',
      `  <link rel="canonical" href="${escapeAttr(canonicalUrl)}" />\n  </head>`
    );
  }

  // Insert additional structured data (before </head>)
  if (structuredData) {
    html = html.replace(
      '</head>',
      `  <script type="application/ld+json">${JSON.stringify(structuredData)}</script>\n  </head>`
    );
  }

  // Inject pre-rendered content into #root (marked for hydration)
  if (content) {
    html = html.replace(
      '<div id="root"></div>',
      `<div id="root" data-prerendered="true">${content}</div>`
    );
  }

  return html;
}

// ---------------------------------------------------------------------------
// Page content generators — produce lightweight SEO HTML for each route
// ---------------------------------------------------------------------------

function generateDashboard() {
  const stats = readJSON(resolve(DATA_DIR, 'stats.json'));
  const upcoming = readJSON(resolve(DATA_DIR, 'upcoming-events.json'));

  let content = '<div>';
  content += `<h1>Australian Merger Tracker</h1>`;
  content += `<p>Live statistics and tracking for every merger reviewed by the Australian Competition and Consumer Commission (ACCC).</p>`;

  if (stats) {
    content += `<p>${stats.total_mergers ?? ''} mergers tracked across Australian industries.</p>`;

    if (stats.recent_determinations?.length) {
      content += `<h2>Recent Determinations</h2><ul>`;
      for (const d of stats.recent_determinations) {
        content += `<li><a href="/mergers/${escapeAttr(d.merger_id)}">${escapeHtml(d.merger_name)}</a> — ${escapeHtml(d.accc_determination)} (${formatDate(d.determination_publication_date)})</li>`;
      }
      content += '</ul>';
    }

    if (stats.recent_mergers?.length) {
      content += `<h2>Recently Notified Mergers</h2><ul>`;
      for (const m of stats.recent_mergers) {
        content += `<li><a href="/mergers/${escapeAttr(m.merger_id)}">${escapeHtml(m.merger_name)}</a> — notified ${formatDate(m.effective_notification_datetime)}</li>`;
      }
      content += '</ul>';
    }
  }

  if (upcoming?.events?.length) {
    content += `<h2>Upcoming Events</h2><ul>`;
    for (const e of upcoming.events.slice(0, 10)) {
      content += `<li><a href="/mergers/${escapeAttr(e.merger_id)}">${escapeHtml(e.merger_name)}</a> — ${escapeHtml(e.event_type_display || e.title)} (${formatDate(e.date)})</li>`;
    }
    content += '</ul>';
  }

  content += `<nav><h2>Explore</h2><ul>`;
  content += `<li><a href="/mergers">All Mergers</a></li>`;
  content += `<li><a href="/timeline">Timeline</a></li>`;
  content += `<li><a href="/industries">Industries</a></li>`;
  content += `<li><a href="/commentary">Commentary</a></li>`;
  content += `<li><a href="/digest">Weekly Digest</a></li>`;
  content += `<li><a href="/analysis">Analysis</a></li>`;
  content += `</ul></nav>`;
  content += '</div>';

  return buildPage({
    title: null, // use default site title
    description: 'Live stats on every ACCC merger review — recent clearances, upcoming deadlines, phase durations, and determination trends across Australian industries.',
    url: '/',
    content,
  });
}

function generateMergersList() {
  // Load all merger list pages
  const meta = readJSON(resolve(DATA_DIR, 'mergers', 'list-meta.json'));
  const allMergers = [];
  if (meta) {
    for (let i = 1; i <= meta.total_pages; i++) {
      const page = readJSON(resolve(DATA_DIR, 'mergers', `list-page-${i}.json`));
      if (page?.mergers) allMergers.push(...page.mergers);
    }
  }

  let content = '<div>';
  content += `<h1>All ACCC Mergers</h1>`;
  content += `<p>Search and filter every Australian merger notified to the ACCC. ${allMergers.length} mergers and counting.</p>`;

  if (allMergers.length) {
    content += '<ul>';
    for (const m of allMergers) {
      const status = m.accc_determination || m.status || '';
      const date = formatDate(m.effective_notification_datetime);
      content += `<li><a href="/mergers/${escapeAttr(m.merger_id)}">${escapeHtml(m.merger_name)}</a> — ${escapeHtml(status)}${date ? ` (${date})` : ''}</li>`;
    }
    content += '</ul>';
  }
  content += '</div>';

  return buildPage({
    title: 'All Mergers',
    description: 'Search every Australian merger notified to the ACCC. Filter by status, industry, acquirer, or outcome — cleared, declined, Phase 2, or under review.',
    url: '/mergers',
    content,
  });
}

function generateMergerDetail(mergerId) {
  const merger = readJSON(resolve(DATA_DIR, 'mergers', `${mergerId}.json`));
  if (!merger) return null;

  const acquirerNames = (merger.acquirers || []).map(a => a.name).join(', ');
  const targetNames = (merger.targets || []).map(t => t.name).join(', ');
  const description = merger.merger_description
    || `ACCC merger review: ${acquirerNames} acquiring ${targetNames}. Status: ${merger.status || 'Unknown'}.`;

  let content = '<article>';
  content += `<h1>${escapeHtml(merger.merger_name)}</h1>`;
  content += `<p>Merger ID: ${escapeHtml(merger.merger_id)}</p>`;

  // Key details
  content += '<dl>';
  content += `<dt>Status</dt><dd>${escapeHtml(merger.status || '')}</dd>`;
  content += `<dt>Stage</dt><dd>${escapeHtml(merger.stage || '')}</dd>`;
  if (merger.effective_notification_datetime) {
    content += `<dt>Notification Date</dt><dd>${formatDate(merger.effective_notification_datetime)}</dd>`;
  }
  if (merger.accc_determination) {
    content += `<dt>Determination</dt><dd>${escapeHtml(merger.accc_determination)}</dd>`;
  }
  if (merger.determination_publication_date) {
    content += `<dt>Determination Date</dt><dd>${formatDate(merger.determination_publication_date)}</dd>`;
  }
  if (merger.end_of_determination_period) {
    content += `<dt>End of Determination Period</dt><dd>${formatDate(merger.end_of_determination_period)}</dd>`;
  }
  content += '</dl>';

  // Parties
  if (merger.acquirers?.length) {
    content += `<h2>Acquirers</h2><ul>`;
    for (const a of merger.acquirers) content += `<li>${escapeHtml(a.name)}</li>`;
    content += '</ul>';
  }
  if (merger.targets?.length) {
    content += `<h2>Targets</h2><ul>`;
    for (const t of merger.targets) content += `<li>${escapeHtml(t.name)}</li>`;
    content += '</ul>';
  }

  // Description
  if (merger.merger_description) {
    content += `<h2>Description</h2><p>${escapeHtml(merger.merger_description)}</p>`;
  }

  // Commentary
  if (merger.comments?.length) {
    content += `<h2>Commentary</h2>`;
    for (const c of merger.comments) {
      content += `<p>${escapeHtml(c.commentary)}</p>`;
    }
  }

  // Industries
  if (merger.anzsic_codes?.length) {
    content += `<h2>Industries</h2><ul>`;
    for (const code of merger.anzsic_codes) {
      content += `<li><a href="/industries/${encodeURIComponent(code.code)}">${escapeHtml(code.name)} (${escapeHtml(code.code)})</a></li>`;
    }
    content += '</ul>';
  }

  // Events / Timeline
  if (merger.events?.length) {
    content += `<h2>Timeline</h2><ul>`;
    for (const e of merger.events) {
      content += `<li>${formatDate(e.date)} — ${escapeHtml(e.display_title || e.title)}</li>`;
    }
    content += '</ul>';
  }

  // Back link
  content += `<nav><a href="/mergers">← Back to all mergers</a></nav>`;
  content += '</article>';

  // Structured data
  const structuredData = {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: merger.merger_name,
    description: description.slice(0, 300),
    datePublished: merger.effective_notification_datetime,
    author: {
      '@type': 'Person',
      name: 'Nick Twort',
      url: SITE_URL,
    },
    about: {
      '@type': 'MergerAcquisition',
      name: merger.merger_name,
      acquirer: (merger.acquirers || []).map(a => ({
        '@type': 'Organization',
        name: a.name,
      })),
      target: (merger.targets || []).map(t => ({
        '@type': 'Organization',
        name: t.name,
      })),
    },
  };

  return buildPage({
    title: merger.merger_name,
    description: description.slice(0, 160),
    url: `/mergers/${merger.merger_id}`,
    structuredData,
    content,
  });
}

function generateTimeline() {
  // Load all timeline pages
  const meta = readJSON(resolve(DATA_DIR, 'timeline-meta.json'));
  const allEvents = [];
  if (meta) {
    for (let i = 1; i <= meta.total_pages; i++) {
      const page = readJSON(resolve(DATA_DIR, `timeline-page-${i}.json`));
      if (page?.events) allEvents.push(...page.events);
    }
  }

  let content = '<div>';
  content += `<h1>Merger Review Timeline</h1>`;
  content += `<p>Chronological feed of every ACCC merger event — notifications, Phase 2 launches, consultations, and determinations.</p>`;

  if (allEvents.length) {
    content += '<ul>';
    for (const e of allEvents.slice(0, 100)) { // first 100 for reasonable page size
      content += `<li>${formatDate(e.date)} — <a href="/mergers/${escapeAttr(e.merger_id)}">${escapeHtml(e.merger_name)}</a>: ${escapeHtml(e.display_title || e.title || e.event_type_display || '')}</li>`;
    }
    content += '</ul>';
  }
  content += '</div>';

  return buildPage({
    title: 'Timeline',
    description: 'Chronological feed of every ACCC merger event — notifications, Phase 2 launches, public consultation windows, and final determinations in date order.',
    url: '/timeline',
    content,
  });
}

function generateIndustries() {
  const industries = readJSON(resolve(DATA_DIR, 'industries.json'));

  let content = '<div>';
  content += `<h1>Industries</h1>`;
  content += `<p>Explore Australian merger activity by ANZSIC industry sector.</p>`;

  if (industries?.length) {
    content += '<ul>';
    for (const ind of industries) {
      content += `<li><a href="/industries/${encodeURIComponent(ind.code)}">${escapeHtml(ind.name)} (${escapeHtml(ind.code)})</a> — ${ind.count || 0} merger${(ind.count || 0) !== 1 ? 's' : ''}</li>`;
    }
    content += '</ul>';
  }
  content += '</div>';

  return buildPage({
    title: 'Industries',
    description: 'Explore Australian merger activity by industry sector. See which ANZSIC industries attract the most ACCC scrutiny and how deal outcomes compare across sectors.',
    url: '/industries',
    content,
  });
}

function generateIndustryDetail(code) {
  const data = readJSON(resolve(DATA_DIR, 'industries', `${code}.json`));
  if (!data) return null;

  const industryName = data.name || code;
  const mergers = data.mergers || [];

  let content = '<div>';
  content += `<h1>${escapeHtml(industryName)}</h1>`;
  content += `<p>ANZSIC code: ${escapeHtml(code)} — ${mergers.length} merger${mergers.length !== 1 ? 's' : ''} reviewed by the ACCC.</p>`;

  if (mergers.length) {
    content += '<ul>';
    for (const m of mergers) {
      content += `<li><a href="/mergers/${escapeAttr(m.merger_id)}">${escapeHtml(m.merger_name)}</a> — ${escapeHtml(m.accc_determination || m.status || '')}</li>`;
    }
    content += '</ul>';
  }

  content += `<nav><a href="/industries">← Back to all industries</a></nav>`;
  content += '</div>';

  return buildPage({
    title: industryName,
    description: `${mergers.length} merger${mergers.length !== 1 ? 's' : ''} in the ${industryName} industry reviewed by the ACCC.`,
    url: `/industries/${encodeURIComponent(code)}`,
    content,
  });
}

function generateCommentary() {
  const data = readJSON(resolve(DATA_DIR, 'commentary.json'));

  let content = '<div>';
  content += `<h1>Commentary</h1>`;
  content += `<p>In-depth analysis of Australian merger cases — examining ACCC decisions, competitive concerns, and M&amp;A policy implications.</p>`;

  if (data?.length) {
    content += `<p>${data.length} ${data.length === 1 ? 'entry' : 'entries'}</p>`;
    for (const item of data) {
      content += `<article>`;
      content += `<h2><a href="/mergers/${escapeAttr(item.merger_id)}">${escapeHtml(item.merger_name)}</a></h2>`;
      if (item.comments?.length) {
        for (const c of item.comments) {
          content += `<p>${escapeHtml(c.commentary)}</p>`;
        }
      }
      content += `</article>`;
    }
  }
  content += '</div>';

  return buildPage({
    title: 'Commentary',
    description: 'In-depth analysis of Australian merger cases — examining ACCC decisions, competitive concerns, economic reasoning, and M&A policy implications.',
    url: '/commentary',
    content,
  });
}

function generateDigest() {
  const data = readJSON(resolve(DATA_DIR, 'digest.json'));

  let content = '<div>';
  content += `<h1>Catch Me Up</h1>`;
  content += `<p>Weekly roundup of Australian merger activity — new notifications, clearances, Phase 2 launches, and upcoming deadlines.</p>`;

  if (data) {
    const sections = [
      { key: 'new_mergers', label: 'New Mergers' },
      { key: 'approved', label: 'Mergers Approved' },
      { key: 'declined', label: 'Mergers Declined' },
      { key: 'phase1', label: 'Ongoing — Phase 1' },
      { key: 'phase2', label: 'Ongoing — Phase 2' },
    ];

    for (const { key, label } of sections) {
      const items = data[key];
      if (items?.length) {
        content += `<h2>${label}</h2><ul>`;
        for (const m of items) {
          content += `<li><a href="/mergers/${escapeAttr(m.merger_id)}">${escapeHtml(m.merger_name)}</a></li>`;
        }
        content += '</ul>';
      }
    }
  }
  content += '</div>';

  return buildPage({
    title: 'Catch me up - ACCC Merger Tracker',
    description: 'Weekly roundup of Australian merger activity: new ACCC notifications, Phase 1 clearances, Phase 2 launches, and upcoming consultation deadlines — all in one digest.',
    url: '/digest',
    content,
  });
}

function generateAnalysis() {
  const data = readJSON(resolve(DATA_DIR, 'analysis.json'));

  let content = '<div>';
  content += `<h1>Analysis</h1>`;
  content += `<p>Data-driven analysis of ACCC merger reviews: Phase 1 and Phase 2 durations, waiver processing times, clearance rates, and year-on-year trends.</p>`;

  if (data) {
    if (data.phase1_avg != null) content += `<p>Average Phase 1 duration: ${data.phase1_avg} days</p>`;
    if (data.phase1_median != null) content += `<p>Median Phase 1 duration: ${data.phase1_median} days</p>`;
    if (data.waiver_avg != null) content += `<p>Average waiver duration: ${data.waiver_avg} days</p>`;
  }

  content += `<p>Interactive charts showing Phase 1 duration over time, waiver duration trends, and monthly notification volume are available with JavaScript enabled.</p>`;
  content += '</div>';

  return buildPage({
    title: 'Analysis',
    description: 'Data-driven analysis of ACCC merger reviews: Phase 1 and Phase 2 durations, waiver processing times, clearance rates, and year-on-year determination trends.',
    url: '/analysis',
    content,
  });
}

function generateNickTwort() {
  const structuredData = {
    '@context': 'https://schema.org',
    '@type': 'Person',
    name: 'Nick Twort',
    jobTitle: 'Competition Economist',
    description: 'Australian competition economist with eight years of experience specialising in merger clearance, antitrust analysis, and regulatory economics across Australia and New Zealand.',
    url: `${SITE_URL}/nick-twort`,
    sameAs: [SITE_URL],
    knowsAbout: [
      'Merger clearance', 'Antitrust economics', 'Competition policy',
      'ACCC merger review', 'Market power analysis', 'Regulatory economics',
      'Empirical industrial organisation',
    ],
    hasOccupation: {
      '@type': 'Occupation',
      name: 'Competition Economist',
      occupationLocation: { '@type': 'Country', name: 'Australia' },
      skills: 'Merger clearance analysis, competitive effects modelling, empirical industrial organisation, regulatory economics, antitrust advice',
    },
  };

  let content = '<article>';
  content += `<h1>Nick Twort</h1>`;
  content += `<p>Competition Economist — Australia &amp; New Zealand</p>`;
  content += `<h2>Overview</h2>`;
  content += `<p>Nick Twort is an Australian competition economist with eight years of experience advising on merger clearance, antitrust matters, and regulatory issues for the ACCC and New Zealand Commerce Commission.</p>`;
  content += `<h2>Merger Clearance &amp; the Australian Merger Regime</h2>`;
  content += `<p>Expert in empirical analysis across airlines, digital platforms, supermarkets, telecoms and more.</p>`;
  content += `<h2>Antitrust Practice Areas</h2>`;
  content += `<ul><li>Misuse of Market Power</li><li>Cartels &amp; Exclusionary Conduct</li><li>Access &amp; Regulation</li><li>Public Inquiries</li></ul>`;
  content += `<h2>About This Site</h2>`;
  content += `<p>The <a href="/">Australian Merger Tracker</a> provides real-time tracking of every ACCC merger review.</p>`;
  content += '</article>';

  return buildPage({
    title: 'Nick Twort – Competition Economist | Australian Merger & Antitrust Expert',
    description: 'Nick Twort is an Australian competition economist with eight years of experience advising on merger clearance, antitrust matters, and regulatory issues for the ACCC and New Zealand Commerce Commission. Expert in empirical analysis across airlines, digital platforms, supermarkets, telecoms and more.',
    url: '/nick-twort',
    type: 'profile',
    structuredData,
    content,
  });
}

// ---------------------------------------------------------------------------
// Write page to dist
// ---------------------------------------------------------------------------

function writePage(route, html) {
  if (route === '/') {
    writeFileSync(resolve(DIST_DIR, 'index.html'), html);
  } else {
    const dir = resolve(DIST_DIR, route.replace(/^\//, ''));
    mkdirSync(dir, { recursive: true });
    writeFileSync(resolve(dir, 'index.html'), html);
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
  console.log('Pre-rendering static pages...\n');
  let count = 0;
  const failed = [];

  // Static pages
  const staticPages = [
    { route: '/', gen: generateDashboard },
    { route: '/mergers', gen: generateMergersList },
    { route: '/timeline', gen: generateTimeline },
    { route: '/industries', gen: generateIndustries },
    { route: '/commentary', gen: generateCommentary },
    { route: '/digest', gen: generateDigest },
    { route: '/analysis', gen: generateAnalysis },
    { route: '/nick-twort', gen: generateNickTwort },
  ];

  for (const { route, gen } of staticPages) {
    try {
      const html = gen();
      writePage(route, html);
      count++;
    } catch (err) {
      failed.push({ route, error: err.message });
    }
  }
  console.log(`  Static pages: ${count}`);

  // Merger detail pages
  let mergerCount = 0;
  const mergersDir = resolve(DATA_DIR, 'mergers');
  for (const file of readdirSync(mergersDir)) {
    if (file === 'list-meta.json' || file.startsWith('list-page-')) continue;
    if (extname(file) !== '.json') continue;
    const mergerId = basename(file, '.json');
    try {
      const html = generateMergerDetail(mergerId);
      if (html) {
        writePage(`/mergers/${mergerId}`, html);
        mergerCount++;
      }
    } catch (err) {
      failed.push({ route: `/mergers/${mergerId}`, error: err.message });
    }
  }
  console.log(`  Merger detail pages: ${mergerCount}`);

  // Industry detail pages
  let industryCount = 0;
  const industriesDir = resolve(DATA_DIR, 'industries');
  for (const file of readdirSync(industriesDir)) {
    if (extname(file) !== '.json') continue;
    const code = basename(file, '.json');
    try {
      const html = generateIndustryDetail(code);
      if (html) {
        writePage(`/industries/${code}`, html);
        industryCount++;
      }
    } catch (err) {
      failed.push({ route: `/industries/${code}`, error: err.message });
    }
  }
  console.log(`  Industry detail pages: ${industryCount}`);

  const total = count + mergerCount + industryCount;
  console.log(`\nDone! Pre-rendered ${total} pages.`);

  if (failed.length > 0) {
    console.warn(`\nWarning: ${failed.length} pages failed:`);
    for (const { route, error } of failed) {
      console.warn(`  ${route}: ${error}`);
    }
  }
}

main();
