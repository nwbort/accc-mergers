/* global process */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect } from 'vitest';

import {
  SITE_URL,
  STATIC_PAGE_META,
  fullTitle,
  industryMeta,
  mergerMeta,
  partyMeta,
} from '../pageMeta.js';
import { renderPage, staticBody } from '../../../prerender.js';

// Vitest runs with the frontend project dir as cwd.
const frontendRoot = process.cwd();
const readFixture = (p) => readFileSync(resolve(frontendRoot, p), 'utf8');

const MERGER = {
  merger_id: 'MN-01016',
  merger_name: 'Acme Corp - Widget Co',
  merger_description: 'Acme acquiring Widget.',
  status: 'Determination made',
  accc_determination: 'Not opposed',
  effective_notification_datetime: '2025-08-15T00:00:00Z',
  determination_publication_date: '2025-10-01T00:00:00Z',
  acquirers: [{ name: 'Acme Corp' }],
  targets: [{ name: 'Widget Co' }],
  anzsic_codes: [{ code: '6240', name: 'Financial Asset Investing' }],
};

describe('mergerMeta', () => {
  it('builds the canonical path, title and article metadata', () => {
    const meta = mergerMeta(MERGER);
    expect(meta.path).toBe('/mergers/MN-01016/acme-corp-widget-co');
    expect(meta.title).toBe('Acme Corp - Widget Co');
    expect(fullTitle(meta.title)).toBe('Acme Corp - Widget Co | Australian Merger Tracker');
    expect(meta.type).toBe('article');
    expect(meta.modifiedTime).toBe('2025-10-01T00:00:00Z');
    expect(meta.section).toBe('Financial Asset Investing');
  });

  it('falls back to a generated description when none is supplied', () => {
    const meta = mergerMeta({ ...MERGER, merger_description: '' });
    expect(meta.description).toBe(
      'ACCC merger review: Acme Corp acquiring Widget Co. Status: Determination made',
    );
  });

  it('emits Article and BreadcrumbList schemas pointing at the canonical URL', () => {
    const [article, breadcrumb] = mergerMeta(MERGER).structuredData;
    const url = `${SITE_URL}/mergers/MN-01016/acme-corp-widget-co`;
    expect(article['@type']).toBe('Article');
    expect(article.mainEntityOfPage['@id']).toBe(url);
    expect(breadcrumb['@type']).toBe('BreadcrumbList');
    expect(breadcrumb.itemListElement.map((i) => i.item)).toEqual([
      SITE_URL,
      `${SITE_URL}/mergers`,
      url,
    ]);
  });
});

describe('partyMeta', () => {
  const party = {
    canonical_name: 'Coles Group',
    merger_count: 11,
    phase_2_count: 1,
  };

  it('pluralises the review counts', () => {
    expect(partyMeta(party, 'coles').description).toBe(
      'Coles Group has been involved in 11 ACCC merger reviews, including 1 Phase 2 review.',
    );
    expect(partyMeta({ ...party, merger_count: 1, phase_2_count: 0 }, 'coles').description).toBe(
      'Coles Group has been involved in 1 ACCC merger review.',
    );
  });

  it('falls back to the route id when the record has no canonical name', () => {
    const meta = partyMeta({ merger_count: 0 }, 'some-party');
    expect(meta.name).toBe('some-party');
    expect(meta.path).toBe('/parties/some-party/some-party');
  });
});

describe('industryMeta', () => {
  const industry = {
    name: 'Financial Asset Investing',
    level: 'class',
    mergers: [{ merger_id: 'MN-1' }, { merger_id: 'MN-2' }],
    ancestors: [{ code: 'K', name: 'Financial and Insurance Services', level: 'division' }],
  };

  it('describes the node by ANZSIC level and count', () => {
    const meta = industryMeta(industry, '6240');
    expect(meta.description).toBe(
      '2 mergers in the Financial Asset Investing industry (ANZSIC class 6240) reviewed by the ACCC.',
    );
    expect(meta.path).toBe('/industries/6240/financial-asset-investing');
  });

  it('handles an empty node without pluralising wrongly', () => {
    const meta = industryMeta({ name: 'Empty', level: 'class', mergers: [] }, '9002');
    expect(meta.description).toBe(
      '0 mergers in the Empty industry (ANZSIC class 9002) reviewed by the ACCC.',
    );
  });

  it('falls back through detail name, index name, then code', () => {
    expect(industryMeta({}, '0114', 'Sheep Farming').name).toBe('Sheep Farming');
    expect(industryMeta({}, '0114').name).toBe('0114');
  });

  it('puts every ANZSIC ancestor in the breadcrumb trail', () => {
    const [breadcrumb] = industryMeta(industry, '6240').structuredData;
    expect(breadcrumb.itemListElement.map((i) => i.name)).toEqual([
      'Home',
      'Industries',
      'Financial and Insurance Services',
      'Financial Asset Investing',
    ]);
  });
});

// The static table is the shared source of truth: the page components read it
// for <SEO> and the prerenderer reads it for the raw HTML. A route present in
// one but not the other is exactly the drift this suite exists to catch.
describe('STATIC_PAGE_META', () => {
  it('gives every route a title and description', () => {
    for (const [path, meta] of Object.entries(STATIC_PAGE_META)) {
      expect(path.startsWith('/'), `${path} should be a root-relative path`).toBe(true);
      expect(meta.title, `${path} title`).toBeTruthy();
      expect(meta.description, `${path} description`).toBeTruthy();
    }
  });

  it('never repeats the site name in a title', () => {
    // <SEO> appends " | Australian Merger Tracker"; a title carrying the brand
    // already would render it twice.
    for (const [path, meta] of Object.entries(STATIC_PAGE_META)) {
      expect(meta.title, `${path} title duplicates the site name`).not.toContain(
        'Australian Merger Tracker',
      );
    }
  });

  it('is consumed by every static page it names', () => {
    const routeToFile = {
      '/': 'Dashboard.jsx',
      '/mergers': 'Mergers.jsx',
      '/timeline': 'Timeline.jsx',
      '/industries': 'Industries.jsx',
      '/parties': 'Parties.jsx',
      '/analysis': 'Analysis.jsx',
      '/phase-2': 'Phase2.jsx',
      '/refiled-notifications': 'RefiledNotifications.jsx',
      '/extensions': 'Extensions.jsx',
      '/commentary': 'Commentary.jsx',
      '/digest': 'Digest.jsx',
      '/nick-twort': 'NickTwort.jsx',
      '/privacy': 'PrivacyPolicy.jsx',
    };
    expect(Object.keys(routeToFile).sort()).toEqual(Object.keys(STATIC_PAGE_META).sort());

    for (const [route, file] of Object.entries(routeToFile)) {
      const src = readFixture(`src/pages/${file}`);
      expect(src, `${file} should read STATIC_PAGE_META['${route}']`).toContain(
        `STATIC_PAGE_META['${route}']`,
      );
      expect(src, `${file} should pass the shared title to <SEO>`).toContain(
        'title={PAGE_META.title}',
      );
    }
  });
});

// If this block fails, index.html's tags have been renamed and renderPage's
// regexes are silently no longer matching — which means every prerendered page
// ships the generic site-wide head instead of its own. That is the exact bug
// the prerenderer exists to prevent, and it fails open, so it needs a test.
describe('renderPage stamping against the real index.html', () => {
  const template = readFixture('index.html');
  const meta = { ...STATIC_PAGE_META['/timeline'], path: '/timeline' };
  const html = renderPage(template, meta, staticBody(meta));

  it('replaces the title, description and canonical', () => {
    expect(html).toContain('<title>Timeline | Australian Merger Tracker</title>');
    expect(html).toContain(`<meta name="description" content="${meta.description}" />`);
    expect(html).toContain(`<link rel="canonical" href="${SITE_URL}/timeline" />`);
  });

  it('replaces every Open Graph and Twitter tag', () => {
    expect(html).toContain('<meta property="og:type" content="website" />');
    expect(html).toContain(
      '<meta property="og:title" content="Timeline | Australian Merger Tracker" />',
    );
    expect(html).toContain(`<meta property="og:url" content="${SITE_URL}/timeline" />`);
    expect(html).toContain(
      '<meta name="twitter:title" content="Timeline | Australian Merger Tracker" />',
    );
    // No generic copy left behind for a crawler to read instead.
    expect(html).not.toContain('<meta property="og:url" content="https://mergers.fyi" />');
  });

  it('keeps the SPA bootable and fills #root with real content', () => {
    expect(html).toContain('src="/src/main.jsx"');
    expect(html).not.toContain('<div id="root"></div>');
    expect(html).toContain('<h1>Timeline</h1>');
  });

  it('only emits article tags for article pages', () => {
    expect(html).not.toContain('article:published_time');
    const articleHtml = renderPage(template, mergerMeta(MERGER), '');
    expect(articleHtml).toContain('<meta property="og:type" content="article" />');
    expect(articleHtml).toContain(
      '<meta property="article:published_time" content="2025-08-15T00:00:00Z" />',
    );
    expect(articleHtml).toContain(
      '<meta property="article:section" content="Financial Asset Investing" />',
    );
  });

  // Register text is scraped from the ACCC, so it is third-party input landing
  // in both HTML attributes and a <script> block.
  it('escapes values that would otherwise break out of an attribute', () => {
    const hostile = mergerMeta({
      ...MERGER,
      merger_name: 'Evil" onload="alert(1)',
      merger_description: 'x',
    });
    const out = renderPage(template, hostile, '');
    expect(out).not.toContain('onload="alert(1)"');
    expect(out).toContain('&quot; onload=&quot;');
  });

  it('escapes values that would otherwise close the JSON-LD script tag', () => {
    const hostile = mergerMeta({
      ...MERGER,
      merger_description: '</script><img src=x onerror=alert(1)>',
    });
    const out = renderPage(template, hostile, '');
    const ldBlocks = out.match(/<script type="application\/ld\+json">[\s\S]*?<\/script>/g);
    // Two blocks: index.html's site-wide WebSite schema and this page's.
    expect(ldBlocks).toHaveLength(2);
    expect(out).not.toContain('<img src=x onerror=alert(1)>');
    expect(ldBlocks[1]).toContain('\\u003c/script>');
    // Still valid JSON, and the escape decodes back to the original text.
    const parsed = JSON.parse(ldBlocks[1].replace(/^<script[^>]*>|<\/script>$/g, ''));
    expect(parsed[0].description).toBe('</script><img src=x onerror=alert(1)>');
  });
});
