/* global process */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect } from 'vitest';

import {
  AUTHOR_ID,
  AUTHOR_REF,
  SITE_URL,
  STATIC_PAGE_META,
  fullTitle,
  frequentAcquirers,
  partyTitleName,
  DEFAULT_OG_IMAGE,
  industryMeta,
  mergerMeta,
  mergerOgImage,
  partyMeta,
  quarterlyMeta,
  serialiseJsonLd,
} from '../pageMeta.js';
import { mergerOgImage as fnMergerOgImage } from '../../../../functions/mergers/[matter]/[[path]].js';
import {
  DETAIL_SUMMARY,
  HOME_PAGE_PATH,
  componentBody,
  homeBody,
  industriesHubBody,
  industryBody,
  mergersHubBody,
  partiesHubBody,
  mergerBody,
  partyBody,
  renderPage,
  setStaticFooter,
  staticBody,
} from '../../../prerender.js';

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
    canonical_name: 'Vets Central Holdings Pty Ltd',
    merger_count: 3,
    phase_2_count: 1,
    phase_duration: { median_business_days: 27, completed_count: 2 },
    waiver_duration: null,
    members: [
      { name: 'VETS CENTRAL HOLDINGS PTY LTD', identifier: '11 111 111 111', identifier_type: 'ABN' },
      { name: 'Vets Central Holdings Pty Ltd' },
      { name: 'DROVERS VET HOSPITAL PTY LTD' },
      { name: 'FACEBARK PTY LTD' },
    ],
    mergers: {
      acquirer: [
        { merger_id: 'MN-3', merger_name: 'Vets Central – Vital Vet', determination: 'Approved', notification_date: '2026-09-25T12:00:00Z' },
        { merger_id: 'MN-2', merger_name: 'Vets Central – Drovers', phase: 'Phase 2', status: 'Under assessment', notification_date: '2026-04-01T12:00:00Z' },
      ],
      target: [
        { merger_id: 'WA-1', merger_name: 'Bigger Co – Vets Central', is_waiver: true, determination: 'Not approved', notification_date: '2026-01-15T12:00:00Z' },
      ],
      other: [],
    },
  };

  it('drops the legal form from the title but keeps it as the name', () => {
    const meta = partyMeta(party, 'vets-central-holdings-pty-ltd');
    expect(meta.title).toBe('Vets Central Holdings – ACCC Merger Reviews');
    expect(meta.name).toBe('Vets Central Holdings Pty Ltd');
    expect(partyTitleName('Bain Capital Investors, LLC.')).toBe('Bain Capital Investors');
    expect(partyTitleName('Siemens AG')).toBe('Siemens AG');
    expect(partyTitleName('Limited')).toBe('Limited');
  });

  it('describes roles, Phase 2 and outcomes', () => {
    expect(partyMeta(party, 'vc').description).toBe(
      'Vets Central Holdings Pty Ltd has been involved in 3 ACCC merger reviews since January 2026, ' +
        'as acquirer in 2 and as target in 1, including 1 Phase 2 review. ' +
        '1 approved, 1 not approved and 1 under assessment.',
    );
  });

  it('summarises the record without repeating the related parties block', () => {
    expect(partyMeta(party, 'vc').summary).toBe(
      'Since January 2026, Vets Central Holdings Pty Ltd has been a party to 3 ACCC merger reviews, ' +
        'as acquirer in 2 and as target in 1. They comprise 2 notified mergers and 1 waiver application. ' +
        'Of these, 1 was referred to Phase 2. ' +
        'Outcomes so far: 1 approved, 1 not approved and 1 still under assessment. ' +
        'Completed Phase 1 reviews took a median of 27 business days. ' +
        'The most recent, Vets Central – Vital Vet, was lodged on 25 September 2026.',
    );
  });

  it('keeps a one-merger party to a single sentence', () => {
    const single = {
      canonical_name: 'ZIM Integrated Shipping Services Ltd',
      merger_count: 1,
      mergers: {
        acquirer: [],
        target: [{ merger_id: 'MN-9', merger_name: 'Hapag-Lloyd - ZIM', determination: 'Approved', notification_date: '2026-06-29T12:00:00Z' }],
        other: [],
      },
    };
    const meta = partyMeta(single, 'zim');
    expect(meta.description).toBe(
      'ZIM Integrated Shipping Services Ltd was the target in Hapag-Lloyd - ZIM, a merger notification approved by the ACCC.',
    );
    expect(meta.summary).toBe(
      'ZIM Integrated Shipping Services Ltd was the target in Hapag-Lloyd - ZIM, ' +
        'a merger notification approved by the ACCC, lodged on 29 June 2026.',
    );
  });

  it('says "all as" when the party only ever played one role', () => {
    const acquirerOnly = { ...party, phase_2_count: 0, mergers: { ...party.mergers, target: [] } };
    expect(partyMeta(acquirerOnly, 'vc').description).toContain('since April 2026, all as acquirer.');
  });

  it('marks the page up as a collection about the organisation', () => {
    const [breadcrumb, collection] = partyMeta(party, 'vc').structuredData;
    expect(breadcrumb['@type']).toBe('BreadcrumbList');
    expect(collection['@type']).toBe('CollectionPage');
    expect(collection.about).toEqual({ '@type': 'Organization', name: 'Vets Central Holdings Pty Ltd' });
    expect(collection.mainEntity.numberOfItems).toBe(3);
    expect(collection.mainEntity.itemListElement.map((i) => i.url)).toEqual([
      'https://mergers.fyi/mergers/MN-3/vets-central-vital-vet',
      'https://mergers.fyi/mergers/MN-2/vets-central-drovers',
      'https://mergers.fyi/mergers/WA-1/bigger-co-vets-central',
    ]);
  });

  it('handles an empty record and falls back to the route id', () => {
    const meta = partyMeta({ merger_count: 0 }, 'some-party');
    expect(meta.name).toBe('some-party');
    expect(meta.path).toBe('/parties/some-party/some-party');
    expect(meta.summary).toBeNull();
    expect(meta.description).toBe('some-party on the ACCC merger register. No merger reviews have been recorded yet.');
  });
});

describe('industryMeta', () => {
  const industry = {
    name: 'Financial Asset Investing',
    level: 'class',
    mergers: [{ merger_id: 'MN-1' }, { merger_id: 'MN-2' }],
    ancestors: [{ code: 'K', name: 'Financial and Insurance Services', level: 'division' }],
  };

  // A realistic node: newest first, as the division file orders them.
  const DENTAL = {
    name: 'Dental Services',
    level: 'class',
    phase_2_count: 0,
    phase_duration: { median_business_days: 16, completed_count: 3 },
    waiver_duration: { median_business_days: 15, completed_count: 2 },
    ancestors: [],
    mergers: [
      { merger_id: 'WA-3', merger_name: 'National Dental Care – Sunshine Dental, VIC', is_waiver: true, determination: 'Approved', notification_date: '2026-09-11T12:00:00Z' },
      { merger_id: 'WA-2', merger_name: 'Impression Dental Group - Blackburn Dental Centre', is_waiver: true, determination: 'Approved', notification_date: '2026-08-14T12:00:00Z' },
      { merger_id: 'MN-3', merger_name: 'Impression Dental Group - Coastal Dental Care', determination: 'Approved', notification_date: '2026-05-28T12:00:00Z' },
      { merger_id: 'MN-2', merger_name: 'National Dental Care – Comfy Dental clinic', determination: 'Approved', notification_date: '2026-03-13T12:00:00Z' },
      { merger_id: 'MN-1', merger_name: 'National Dental Care – DDTA Dental', determination: 'Approved', has_conditions: true, notification_date: '2026-02-27T12:00:00Z' },
    ],
  };

  it('leads the title with the industry and what people search for', () => {
    const meta = industryMeta(DENTAL, '8531');
    expect(meta.title).toBe('Dental Services Mergers – ACCC Reviews');
    expect(fullTitle(meta.title)).toBe('Dental Services Mergers – ACCC Reviews | Australian Merger Tracker');
    // The h1 keeps the plain name.
    expect(meta.name).toBe('Dental Services');
  });

  it('writes a description specific to the node', () => {
    expect(industryMeta(DENTAL, '8531').description).toBe(
      '5 ACCC merger reviews in Dental Services (ANZSIC class 8531) since February 2026, all approved. ' +
        'Frequent acquirers: National Dental Care, Impression Dental Group.',
    );
    expect(industryMeta(industry, '6240').path).toBe('/industries/6240/financial-asset-investing');
  });

  it('breaks down mixed outcomes in the description', () => {
    const mixed = {
      name: 'Retail',
      level: 'division',
      mergers: [
        { merger_name: 'A - B', determination: 'Approved' },
        { merger_name: 'C - D', determination: 'Not approved' },
        { merger_name: 'E - F', status: 'Under assessment' },
      ],
    };
    expect(industryMeta(mixed, 'G').description).toBe(
      '3 ACCC merger reviews in Retail (ANZSIC division G): 1 approved, 1 not approved and 1 under assessment.',
    );
  });

  it('describes an empty node without a count of zero', () => {
    const meta = industryMeta({ name: 'Empty', level: 'class', mergers: [] }, '9002');
    expect(meta.description).toBe(
      'ACCC merger reviews in the Empty industry (ANZSIC class 9002). None have been recorded yet.',
    );
    expect(meta.summary).toBeNull();
  });

  it('summarises volume, outcomes, acquirers, timing and the latest matter', () => {
    expect(industryMeta(DENTAL, '8531').summary).toBe(
      'Since February 2026, the ACCC has reviewed 5 acquisitions in the Dental Services industry ' +
        '(ANZSIC class 8531): 3 notified mergers and 2 waiver applications. ' +
        'All 5 were approved (1 with conditions). ' +
        'The most frequent acquirers are National Dental Care (3) and Impression Dental Group (2). ' +
        'Completed Phase 1 reviews took a median of 16 business days, and waivers a median of 15 business days. ' +
        'The most recent, National Dental Care – Sunshine Dental, VIC, was lodged on 11 September 2026.',
    );
  });

  it('mentions Phase 2 referrals and open matters', () => {
    const summary = industryMeta(
      {
        name: 'Supermarkets',
        level: 'class',
        phase_2_count: 1,
        mergers: [
          { merger_name: 'X - Y', phase: 'Phase 2', status: 'Under assessment', notification_date: '2026-04-01T12:00:00Z' },
          { merger_name: 'Z - W', determination: 'Approved', notification_date: '2026-03-01T12:00:00Z' },
        ],
      },
      '4110',
    ).summary;
    expect(summary).toContain('Of these, 1 was referred to Phase 2.');
    expect(summary).toContain('Outcomes so far: 1 approved and 1 still under assessment.');
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

  it('marks the page up as a collection of its mergers', () => {
    const [, collection] = industryMeta(DENTAL, '8531').structuredData;
    expect(collection['@type']).toBe('CollectionPage');
    expect(collection.url).toBe('https://mergers.fyi/industries/8531/dental-services');
    expect(collection.about).toMatchObject({ termCode: '8531', name: 'Dental Services' });
    expect(collection.mainEntity.numberOfItems).toBe(5);
    expect(collection.mainEntity.itemListElement[0]).toEqual({
      '@type': 'ListItem',
      position: 1,
      name: 'National Dental Care – Sunshine Dental, VIC',
      url: 'https://mergers.fyi/mergers/WA-3/national-dental-care-sunshine-dental-vic',
    });
  });
});

describe('frequentAcquirers', () => {
  it('reads the acquirer off the name and needs two distinct deals', () => {
    expect(
      frequentAcquirers([
        { merger_name: 'Airtree – HotDoc' },
        { merger_name: 'Airtree – HotDoc' }, // same deal filed twice
        { merger_name: 'Coca-Cola Europacific - Bottler A' },
        { merger_name: 'Coca-Cola Europacific - Bottler B' },
        { merger_name: 'No separator here' },
      ]),
    ).toEqual([{ name: 'Coca-Cola Europacific', count: 2 }]);
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

  it('points every page card at a committed file under public/og/', () => {
    // Drawn by scripts/generate/og_cards.py (PAGE_CARDS); a renamed or
    // undrawn card would unfurl as a broken image.
    for (const path of ['/digest', '/current-status', '/phase-2', '/analysis', '/nick-twort']) {
      expect(STATIC_PAGE_META[path].image, `${path} image`).toBeTruthy();
      expect(STATIC_PAGE_META[path].imageAlt, `${path} imageAlt`).toBeTruthy();
    }
    for (const [path, meta] of Object.entries(STATIC_PAGE_META)) {
      if (!meta.image) continue;
      const prefix = `${SITE_URL}/og/`;
      expect(meta.image.startsWith(prefix), `${path} image`).toBe(true);
      expect(() => readFixture(`public/og/${meta.image.slice(prefix.length)}`), `${path} card`).not.toThrow();
    }
  });

  it("gives each committed quarter's page its own committed card", () => {
    const { quarters } = JSON.parse(readFixture('public/data/quarterly.json'));
    expect(quarters.length).toBeGreaterThan(0);
    for (const quarter of quarters) {
      const { image } = quarterlyMeta(quarter);
      expect(image).toBe(`${SITE_URL}/og/quarterly/${quarter.url_key.toLowerCase()}.png`);
      expect(() => readFixture(`public/og/quarterly/${quarter.url_key.toLowerCase()}.png`)).not.toThrow();
    }
    expect(quarterlyMeta({ url_key: '../x', label: 'Q1 2026' }).image).toBeUndefined();
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
      '/industries': 'Industries.jsx',
      '/parties': 'Parties.jsx',
      '/analysis': 'Analysis.jsx',
      '/phase-2': 'Phase2.jsx',
      '/refiled-notifications': 'RefiledNotifications.jsx',
      '/current-status': 'CurrentStatus.jsx',
      '/quarterly': 'Quarterly.jsx',
      '/commentary': 'Commentary.jsx',
      '/digest': 'Digest.jsx',
      '/nick-twort': 'NickTwort.jsx',
      '/privacy': 'PrivacyPolicy.jsx',
      '/copyright': 'Copyright.jsx',
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
describe('mergerOgImage', () => {
  const cases = [
    { og_card: 'cleared-by-the-accc.png' },
    { og_card: null },
    {},
    { og_card: '../og-image.png' },
    { og_card: 'x.png" onload="' },
    { og_card: 42 },
  ];

  it('points at the generated card, falling back to the shared image', () => {
    expect(mergerOgImage({ og_card: 'cleared-by-the-accc.png' })).toBe(
      `${SITE_URL}/og/cleared-by-the-accc.png`,
    );
    expect(mergerOgImage({})).toBe(DEFAULT_OG_IMAGE);
    expect(mergerOgImage({ og_card: '../og-image.png' })).toBe(DEFAULT_OG_IMAGE);
    expect(mergerMeta({ ...MERGER, og_card: 'assessment-ceased.png' }).image).toBe(
      `${SITE_URL}/og/assessment-ceased.png`,
    );
  });

  it('agrees with the Pages Function copy the preview bots see', () => {
    for (const merger of cases) {
      expect(fnMergerOgImage(merger)).toBe(mergerOgImage(merger));
    }
  });
});

describe('renderPage stamping against the real index.html', () => {
  const template = readFixture('index.html');
  const meta = { ...STATIC_PAGE_META['/industries'], path: '/industries' };
  const html = renderPage(template, meta, staticBody(meta));

  it('replaces the title, description and canonical', () => {
    expect(html).toContain('<title>Industries | Australian Merger Tracker</title>');
    expect(html).toContain(`<meta data-rh="true" name="description" content="${meta.description}" />`);
    expect(html).toContain(`<link data-rh="true" rel="canonical" href="${SITE_URL}/industries" />`);
  });

  it('replaces every Open Graph and Twitter tag', () => {
    expect(html).toContain('<meta data-rh="true" property="og:type" content="website" />');
    expect(html).toContain(
      '<meta data-rh="true" property="og:title" content="Industries | Australian Merger Tracker" />',
    );
    expect(html).toContain(`<meta data-rh="true" property="og:url" content="${SITE_URL}/industries" />`);
    expect(html).toContain(
      '<meta data-rh="true" name="twitter:title" content="Industries | Australian Merger Tracker" />',
    );
    // No generic copy left behind for a crawler to read instead.
    expect(html).not.toContain('<meta data-rh="true" property="og:url" content="https://mergers.fyi" />');
  });

  it('keeps the shared image unless the page names its own', () => {
    expect(html).toContain(`<meta data-rh="true" property="og:image" content="${DEFAULT_OG_IMAGE}" />`);
    const card = renderPage(template, { ...meta, image: `${SITE_URL}/og/assessment-ceased.png` }, '');
    expect(card).toContain(`<meta data-rh="true" property="og:image" content="${SITE_URL}/og/assessment-ceased.png" />`);
    expect(card).toContain(`<meta data-rh="true" name="twitter:image" content="${SITE_URL}/og/assessment-ceased.png" />`);
    expect(card).not.toContain(DEFAULT_OG_IMAGE);
    // The width/height tags are siblings, not replaced.
    expect(card).toContain('<meta data-rh="true" property="og:image:width" content="1200" />');
  });

  it('keeps the SPA bootable and fills #root with real content', () => {
    expect(html).toContain('src="/src/main.jsx"');
    expect(html).not.toContain('<div id="root"></div>');
    expect(html).toContain('>Industries</h1>');
  });

  it('only emits article tags for article pages', () => {
    expect(html).not.toContain('article:published_time');
    const articleHtml = renderPage(template, mergerMeta(MERGER), '');
    expect(articleHtml).toContain('<meta data-rh="true" property="og:type" content="article" />');
    expect(articleHtml).toContain(
      '<meta data-rh="true" property="article:published_time" content="2025-08-15T00:00:00Z" />',
    );
    expect(articleHtml).toContain(
      '<meta data-rh="true" property="article:section" content="Financial Asset Investing" />',
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
    const ldBlocks = out.match(/<script [^>]*type="application\/ld\+json">[\s\S]*?<\/script>/g);
    // One block: this page's (the WebSite schema is the homepage's alone).
    expect(ldBlocks).toHaveLength(1);
    expect(out).not.toContain('<img src=x onerror=alert(1)>');
    expect(ldBlocks[0]).toContain('\\u003c/script>');
    // Still valid JSON, and the escape decodes back to the original text.
    const parsed = JSON.parse(ldBlocks[0].replace(/^<script[^>]*>|<\/script>$/g, ''));
    expect(parsed[0].description).toBe('</script><img src=x onerror=alert(1)>');
  });
});

// The prerendered markup is what a user looks at until React mounts. Unclassed
// markup renders as raw browser-default text for that whole window, which is
// what these tests exist to stop regressing.
describe('prerendered bodies are styled', () => {
  const PARTY = {
    canonical_name: 'Coles Group',
    merger_count: 11,
    phase_2_count: 1,
    waiver_count: 4,
    active_count: 2,
    members: [
      { name: 'COLES GROUP LIMITED', identifier: '11 004 089 936', identifier_type: 'ABN' },
      { name: 'COLES SUPERMARKETS AUSTRALIA PTY LTD' },
      { name: 'Coles Group Limited' },
      { name: 'Retail Payment Solutions Pty Ltd' },
    ],
    mergers: {
      acquirer: [{ merger_id: 'MN-1', merger_name: 'Coles - Paydock', status: 'Under assessment' }],
      target: [],
      other: [],
    },
  };

  const INDUSTRY = {
    name: 'Financial Asset Investing',
    level: 'class',
    count: 66,
    phase_2_count: 0,
    waiver_count: 54,
    active_count: 3,
    ancestors: [{ code: 'K', name: 'Financial and Insurance Services', level: 'division' }],
    children: [],
    mergers: [{ merger_id: 'MN-2', merger_name: 'Some deal', determination: 'Approved' }],
  };

  const bodies = {
    merger: mergerBody(MERGER, mergerMeta(MERGER)),
    party: partyBody(PARTY, partyMeta(PARTY, 'coles')),
    industry: industryBody(INDUSTRY, '6240', industryMeta(INDUSTRY, '6240')),
    static: staticBody({ ...STATIC_PAGE_META['/industries'], path: '/industries' }),
  };

  it.each(Object.entries(bodies))('%s body wraps content in the app shell', (_name, body) => {
    // Same background, same fixed-header offset as App.jsx, so nothing jumps
    // vertically when React replaces the markup.
    expect(body).toContain('min-h-screen gradient-mesh');
    expect(body).toContain('class="flex-grow pt-16"');
    expect(body).toContain('max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8');
  });

  it.each(Object.entries(bodies))('%s body styles its heading', (_name, body) => {
    expect(body).toContain('<h1 class="text-2xl font-bold text-gray-900 tracking-tight">');
  });

  it('keeps a zero-valued stat card rather than dropping it', () => {
    // DetailStatGrid renders "0"; hiding the card here would leave the
    // prerendered grid one card short and shift the page on hydration.
    expect(bodies.industry).toContain('Phase 2 reviews');
    expect(bodies.industry).toMatch(/Phase 2 reviews<\/p><p[^>]*>0</);
  });

  it('shows the same member preview count as PartyDetail', () => {
    // PartyDetail previews 3 behind a "show more" toggle.
    expect(bodies.party).toContain('COLES GROUP LIMITED');
    expect(bodies.party).toContain('ABN: 11 004 089 936');
    expect(bodies.party).not.toContain('Retail Payment Solutions Pty Ltd');
    expect(bodies.party).toContain('Show 1 more');
  });

  it('carries the industry summary paragraph in the header card', () => {
    const meta = industryMeta(INDUSTRY, '6240');
    expect(meta.summary).toBeTruthy();
    expect(bodies.industry).toContain(`<p class="${DETAIL_SUMMARY}">${meta.summary}</p></div>`);
  });

  it('carries the party summary paragraph before the related parties', () => {
    const meta = partyMeta(PARTY, 'coles');
    expect(bodies.party).toContain(`<p class="${DETAIL_SUMMARY}">${meta.summary}</p><div class="mt-4 pt-4`);
  });

  it('links mergers by their canonical slugged path', () => {
    expect(bodies.party).toContain('href="/mergers/MN-1/coles-paydock"');
    expect(bodies.industry).toContain('href="/mergers/MN-2/some-deal"');
  });
});

// Tailwind only emits classes it finds in the files listed under `content`.
// Drop prerender.js from that list and every class above is purged from the
// stylesheet — the build still succeeds and the pages silently render as
// unstyled text.
describe('tailwind config', () => {
  it('scans prerender.js for classes', () => {
    const config = readFixture('tailwind.config.js');
    expect(config).toContain('./prerender.js');
  });
});

describe('quarterlyMeta', () => {
  const quarter = {
    quarter: '2026-Q3',
    url_key: '26Q3',
    label: 'Q3 2026',
    findings: ['113 notifications filed.', 'Phase 1 took 18 days.', 'Third point.'],
  };

  it('addresses the quarter by its dated path', () => {
    const meta = quarterlyMeta(quarter);
    expect(meta.path).toBe('/quarterly/26Q3');
    expect(meta.title).toBe('Quarterly merger report – Q3 2026');
    expect(meta.title).not.toContain('Australian Merger Tracker');
  });

  it('leads the description with the first two findings', () => {
    const { description } = quarterlyMeta(quarter);
    expect(description).toContain('113 notifications filed. Phase 1 took 18 days.');
    expect(description).not.toContain('Third point.');
  });
});

describe('hub page bodies', () => {
  const meta = (path) => ({ ...STATIC_PAGE_META[path], path });

  it('links every merger on /mergers, newest first', () => {
    const body = mergersHubBody(
      [
        { merger_id: 'MN-1', merger_name: 'Old - Deal', accc_determination: 'Approved', effective_notification_datetime: '2025-01-01T12:00:00Z' },
        { merger_id: 'WA-2', merger_name: 'New - Deal', status: 'Under assessment', effective_notification_datetime: '2026-01-01T12:00:00Z' },
      ],
      meta('/mergers'),
    );
    expect(body).toContain('All 2 mergers, newest first');
    expect(body.indexOf('/mergers/WA-2/new-deal')).toBeLessThan(body.indexOf('/mergers/MN-1/old-deal'));
    expect(body).toContain('Under assessment');
  });

  it('groups /industries under their division, with the unplaceable last', () => {
    const body = industriesHubBody(
      [
        { code: '8531', name: 'Dental Services', merger_count: 18 },
        { code: '4110', name: 'Supermarket and Grocery Stores', merger_count: 26 },
        { code: '99/1', name: 'Mystery', merger_count: 1 },
      ],
      { G: 'Retail Trade', Q: 'Health Care and Social Assistance' },
      (code) => ({ 8531: 'Q', 4110: 'G' })[code] || '_orphans',
      meta('/industries'),
    );
    expect(body).toContain('href="/industries/G/retail-trade"');
    expect(body).toContain('href="/industries/8531/dental-services"');
    const order = ['Retail Trade', 'Health Care and Social Assistance', 'Other industries'].map((t) => body.indexOf(t));
    expect(order).toEqual([...order].sort((a, b) => a - b));
    expect(order[0]).toBeGreaterThan(-1);
  });

  it('links only parties on more than one merger from /parties', () => {
    const body = partiesHubBody(
      [
        { id: 'coles', name: 'Coles Group', merger_count: 19 },
        { id: 'solo', name: 'Solo Pty Ltd', merger_count: 1 },
      ],
      meta('/parties'),
    );
    expect(body).toContain('href="/parties/coles/coles-group"');
    expect(body).not.toContain('Solo Pty Ltd');
    expect(body).toContain('(1 of 2)');
  });

  it('wraps a component-rendered page in the chrome only', () => {
    const body = componentBody('<div class="max-w-4xl">page</div>');
    expect(body).toContain('class="flex-grow pt-16"><div class="max-w-4xl">page</div></main>');
  });

  it('serves the stamped homepage at / through the rewrite in _redirects', () => {
    // prerender.js writes the copy to HOME_PAGE_PATH; Pages only serves it at /
    // because _redirects rewrites to the same path.
    const rules = readFixture('public/_redirects')
      .split('\n')
      .map((line) => line.trim().split(/\s+/))
      .filter(([from]) => from === '/');
    expect(rules).toEqual([['/', HOME_PAGE_PATH, '200']]);
    const meta = { ...STATIC_PAGE_META['/'], path: '/' };
    const html = renderPage(readFixture('index.html'), meta, '');
    expect(html).toContain('<link data-rh="true" rel="canonical" href="https://mergers.fyi/" />');
    // ...and no _headers rule that matches either URL marks it noindex, which
    // would fight that canonical. Rules are a path line, then indented headers.
    const headerRules = {};
    let current = null;
    for (const line of readFixture('public/_headers').split('\n')) {
      if (!line.trim() || line.startsWith('#')) continue;
      if (/^\S/.test(line)) headerRules[(current = line.trim())] = [];
      else if (current) headerRules[current].push(line.trim());
    }
    const matching = Object.keys(headerRules).filter((rule) =>
      ['/', `${HOME_PAGE_PATH}`].some((url) =>
        new RegExp(`^${rule.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*')}$`).test(url),
      ),
    );
    expect(matching).toContain('/*');
    for (const rule of matching) {
      expect(headerRules[rule].join('\n'), rule).not.toMatch(/x-robots-tag/i);
    }
  });

  it('opens the homepage with the dashboard top it is handed, then links every section', () => {
    const meta = { ...STATIC_PAGE_META['/'], path: '/' };
    const top = '<div class="max-w-7xl"><h1 class="sr-only">dashboard</h1></div>';
    const body = homeBody(meta, top, STATIC_PAGE_META);
    expect(body).toContain(`<main id="main-content" class="flex-grow pt-16">${top}`);
    for (const path of ['/mergers', '/phase-2', '/analysis', '/current-status', '/quarterly']) {
      expect(body).toContain(`href="${path}"`);
    }
    // Without the dashboard (no stats.json, or no renderer) a plain header
    // stands in, and the section links still do.
    const plain = homeBody(meta, '', STATIC_PAGE_META);
    expect(plain).toMatch(/<h1[^>]*>Australian Merger Tracker<\/h1>/);
    expect(plain).toContain('href="/mergers"');
  });

  it('hands every head tag <SEO> also writes to Helmet, and only those', () => {
    // react-helmet-async replaces tags carrying data-rh on mount; an unmarked
    // copy would sit beside Helmet's for good. The real built template, so a
    // new unmarked tag in index.html is caught too.
    const template = readFixture('index.html');
    const html = renderPage(template, mergerMeta(MERGER), '');
    const head = html.slice(0, html.indexOf('</head>'));
    const managed = [
      /<link [^>]*rel="canonical"/,
      /<script [^>]*type="application\/ld\+json"/,
      ...['description', 'twitter:card', 'twitter:title', 'twitter:description', 'twitter:image'].map(
        (n) => new RegExp(`<meta [^>]*name="${n}"`),
      ),
      ...['og:type', 'og:title', 'og:description', 'og:url', 'og:site_name', 'og:image', 'og:image:width',
        'og:image:height', 'og:locale', 'article:published_time'].map((p) => new RegExp(`<meta [^>]*property="${p}"`)),
    ];
    for (const re of managed) {
      const tags = head.match(new RegExp(re.source, 'g')) || [];
      expect(tags.length, re.source).toBe(1);
      expect(tags[0], re.source).toContain('data-rh="true"');
    }
    // The tags <SEO> never writes stay put, unmarked.
    for (const n of ['author', 'keywords', 'theme-color']) {
      expect(head).toMatch(new RegExp(`<meta name="${n}"`));
    }
  });

  it('closes every page with the footer once one is set', () => {
    setStaticFooter('<footer>foot</footer>');
    try {
      expect(staticBody({ title: 'T', description: 'D' })).toContain('</main><footer>foot</footer></div>');
      expect(componentBody('page')).toContain('</main><footer>foot</footer></div>');
    } finally {
      setStaticFooter('');
    }
  });
});

describe('the author page', () => {
  it('carries its ProfilePage JSON-LD in the shared meta, so the prerender emits it', () => {
    const [profile] = STATIC_PAGE_META['/nick-twort'].structuredData;
    expect(profile['@type']).toBe('ProfilePage');
    expect(profile.url).toBe('https://mergers.fyi/nick-twort');
    const person = profile.mainEntity;
    expect(person['@type']).toBe('Person');
    expect(person['@id']).toBe(AUTHOR_ID);
    expect(person.name).toBe('Nick Twort');
    expect(person.url).toBe(profile.url);
    expect(person.worksFor).toMatchObject({ '@type': 'Organization', name: 'Econic Partners' });
    expect(person.sameAs).toContain('https://www.linkedin.com/in/nick-twort');
    // Round-trips as JSON (no functions, cycles or undefined values).
    expect(JSON.parse(serialiseJsonLd(profile))).toEqual(profile);
  });

  it('is who the homepage WebSite JSON-LD names as author', () => {
    const [site] = STATIC_PAGE_META['/'].structuredData;
    expect(site['@type']).toBe('WebSite');
    expect(site.author).toEqual(AUTHOR_REF);
    expect(site).not.toHaveProperty('creator');
    // The profile says it belongs to that same WebSite.
    const [profile] = STATIC_PAGE_META['/nick-twort'].structuredData;
    expect(profile.isPartOf['@id']).toBe(site['@id']);
  });

  it("gives the fallback shell the homepage's own title and description", () => {
    // index.html is what Pages serves for any URL without a file, and what
    // bots that run no JavaScript see there, so it reads as the homepage.
    const html = readFixture('index.html');
    const home = STATIC_PAGE_META['/'];
    const attr = (s) => s.replace(/&/g, '&amp;');
    expect(html).toContain(`<title>${home.documentTitle}</title>`);
    for (const tag of ['name="description"', 'property="og:description"', 'name="twitter:description"']) {
      expect(html, tag).toContain(`${tag} content="${home.description}"`);
    }
    for (const tag of ['property="og:title"', 'name="twitter:title"']) {
      expect(html, tag).toContain(`${tag} content="${home.documentTitle}"`);
    }
    // ...and the prerendered homepage says the same, escaped for HTML.
    const page = renderPage(html, { ...home, path: '/' }, '');
    expect(page).toContain(`<title>${attr(home.documentTitle)}</title>`);
  });

  it('keeps the WebSite JSON-LD to the homepage', () => {
    // index.html is the template every page is stamped from (and the fallback
    // shell), so a block there would be on every page.
    expect(readFixture('index.html')).not.toContain('application/ld+json');
    for (const [path, meta] of Object.entries(STATIC_PAGE_META)) {
      if (path === '/') continue;
      const types = (meta.structuredData || []).map((d) => d['@type']);
      expect(types, path).not.toContain('WebSite');
    }
  });

  it('is the author of every merger article', () => {
    const [article] = mergerMeta({ merger_id: 'MN-1', merger_name: 'A - B' }).structuredData;
    expect(article.author).toEqual(AUTHOR_REF);
  });
});
