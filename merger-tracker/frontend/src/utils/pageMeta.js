// Page metadata (title, description, canonical path, JSON-LD) shared by the
// React pages and the build-time prerenderer.
//
// Both consumers MUST produce identical <head> values: the pages render them
// through <SEO> once React mounts, while `prerender.js` stamps them into the
// static HTML that crawlers read *before* running any JavaScript. When the two
// disagree, search engines see one canonical/title in the raw markup and
// another after the render pass. Keeping the strings in one place is what stops
// that drift — see the header comment in prerender.js for the background.
//
// Every function here is pure and takes the raw JSON detail record straight
// from `public/data/`, so the prerenderer can call it with `JSON.parse` output
// and the pages can call it with fetched data.

import { industryPath, mergerPath, partyPath } from './slug.js';

export const SITE_URL = 'https://mergers.fyi';
export const SITE_TITLE = 'Australian Merger Tracker';
export const AUTHOR_NAME = 'Nick Twort';

// ANZSIC level → human label for the page subtitle, breadcrumb and description.
export const LEVEL_LABELS = {
  division: 'Division',
  subdivision: 'Subdivision',
  group: 'Group',
  class: 'Class',
};

/** The full <title>, matching how <SEO> composes it. */
export function fullTitle(title) {
  return title ? `${title} | ${SITE_TITLE}` : SITE_TITLE;
}

/**
 * Serialise JSON-LD for embedding in a `<script type="application/ld+json">`.
 *
 * HTML parsers end a script block at the first literal `</script>`, wherever it
 * appears — including inside a JSON string. Register text is third-party (it is
 * scraped from the ACCC), so a merger name or description containing `<` could
 * otherwise close the tag early and have the remainder parsed as markup.
 * Escaping every `<` to its unicode form keeps the JSON semantically identical
 * (parsers decode it back) while making that impossible.
 */
export function serialiseJsonLd(data) {
  return JSON.stringify(data).replace(/</g, '\\u003c');
}

function absolute(path) {
  return `${SITE_URL}${path}`;
}

function plural(n, word) {
  return `${n} ${word}${n !== 1 ? 's' : ''}`;
}

function names(parties) {
  return (parties ?? []).map((p) => p?.name).filter(Boolean);
}

/**
 * BreadcrumbList JSON-LD. `trail` is the list of intermediate crumbs between
 * Home and the current page, each `{name, path}`; the current page is passed
 * separately because it is not a link.
 */
export function breadcrumbSchema(trail, currentName, currentPath) {
  const items = [{ name: 'Home', item: SITE_URL }];
  for (const crumb of trail) {
    items.push({ name: crumb.name, item: absolute(crumb.path) });
  }
  items.push({ name: currentName, item: absolute(currentPath) });

  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((entry, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: entry.name,
      item: entry.item,
    })),
  };
}

/**
 * Meta for a merger detail page, from a `data/mergers/{id}.json` record.
 *
 * @returns {{title: string, description: string, path: string, type: string,
 *   publishedTime: string, modifiedTime: string, section: string|undefined,
 *   structuredData: Object[]}}
 */
export function mergerMeta(merger) {
  const acquirers = names(merger.acquirers);
  const targets = names(merger.targets);
  const path = mergerPath(merger.merger_id, merger.merger_name);
  const url = absolute(path);
  const modifiedTime =
    merger.determination_publication_date || merger.effective_notification_datetime;

  const description =
    merger.merger_description ||
    `ACCC merger review: ${acquirers.join(', ')} acquiring ${targets.join(', ')}. Status: ${merger.status}`;

  const articleSchema = {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: merger.merger_name,
    description:
      merger.merger_description ||
      `Merger between ${acquirers.join(', ')} and ${targets.join(', ')}`,
    datePublished: merger.effective_notification_datetime,
    dateModified: modifiedTime,
    mainEntityOfPage: { '@type': 'WebPage', '@id': url },
    author: { '@type': 'Person', name: AUTHOR_NAME, url: SITE_URL },
    publisher: {
      '@type': 'Organization',
      name: SITE_TITLE,
      url: SITE_URL,
      logo: { '@type': 'ImageObject', url: `${SITE_URL}/og-image.png` },
    },
    about: [
      ...acquirers.map((name) => ({ '@type': 'Organization', name })),
      ...targets.map((name) => ({ '@type': 'Organization', name })),
    ],
  };

  return {
    title: merger.merger_name,
    description,
    path,
    type: 'article',
    publishedTime: merger.effective_notification_datetime,
    modifiedTime,
    section: merger.anzsic_codes?.[0]?.name,
    structuredData: [
      articleSchema,
      breadcrumbSchema([{ name: 'Mergers', path: '/mergers' }], merger.merger_name, path),
    ],
    acquirers,
    targets,
  };
}

/**
 * Meta for a party detail page, from a `data/parties/{id}.json` record.
 * `id` is the route param, used as the display fallback when the record has
 * no canonical name (mirroring PartyDetail.jsx).
 */
export function partyMeta(party, id) {
  const name = party.canonical_name || id;
  const path = partyPath(id, name);
  const mergerCount = party.merger_count ?? 0;
  const phase2 = party.phase_2_count ?? 0;

  const description =
    `${name} has been involved in ${plural(mergerCount, 'ACCC merger review')}` +
    `${phase2 ? `, including ${plural(phase2, 'Phase 2 review')}` : ''}.`;

  return {
    title: name,
    description,
    path,
    type: 'website',
    structuredData: [
      breadcrumbSchema([{ name: 'Parties', path: '/parties' }], name, path),
    ],
    name,
    mergerCount,
  };
}

/**
 * Meta for an industry detail page, from a `data/industries/{code}.json`
 * record. `code` is the route param; `indexName` is the fallback name from
 * `industries.json` used when the detail record carries none (mirroring
 * IndustryDetail.jsx).
 */
export function industryMeta(industry, code, indexName) {
  const name = industry.name || indexName || code;
  const path = industryPath(code, name);
  const mergers = industry.mergers || [];
  const levelLabel = industry.level ? LEVEL_LABELS[industry.level] : null;

  const description =
    `${plural(mergers.length, 'merger')} in the ${name} industry` +
    `${levelLabel ? ` (ANZSIC ${levelLabel.toLowerCase()} ${code})` : ''} reviewed by the ACCC.`;

  // The ANZSIC ancestors already describe the crumb trail the page renders.
  const trail = [
    { name: 'Industries', path: '/industries' },
    ...(industry.ancestors || []).map((a) => ({
      name: a.name,
      path: industryPath(a.code, a.name),
    })),
  ];

  return {
    title: name,
    description,
    path,
    type: 'website',
    structuredData: [breadcrumbSchema(trail, name, path)],
    name,
    levelLabel,
    mergers,
  };
}

/**
 * Static (non-parameterised) routes worth prerendering, keyed by path.
 *
 * These mirror what each page passes to <SEO>; the pages import from here so
 * the two cannot drift. Routes deliberately absent: /feedback (a form, nothing
 * to crawl) and the /* NotFound catch-all.
 */
export const STATIC_PAGE_META = {
  '/': {
    // Note the bare title: <SEO> appends " | Australian Merger Tracker", so a
    // title that already carries the brand would render it twice.
    title: 'ACCC Merger Reviews & M&A Data',
    description:
      'Live stats on every ACCC merger review — recent clearances, upcoming deadlines, phase durations, and determination trends across Australian industries.',
  },
  '/mergers': {
    title: 'All Mergers',
    description:
      'Search every Australian merger notified to the ACCC. Filter by status, industry, acquirer, or outcome — cleared, declined, Phase 2, or under review.',
  },
  '/timeline': {
    title: 'Timeline',
    description:
      'Chronological feed of every ACCC merger event — notifications, Phase 2 launches, public consultation windows, and final determinations in date order.',
  },
  '/industries': {
    title: 'Industries',
    description:
      'Explore Australian merger activity by industry sector. See which ANZSIC industries attract the most ACCC scrutiny and how deal outcomes compare across sectors.',
  },
  '/parties': {
    title: 'Parties',
    description:
      'Explore the companies and investors behind Australian merger activity. See which acquirers and targets appear most often in ACCC merger reviews, and search for any party.',
  },
  '/analysis': {
    title: 'Analysis',
    description:
      'Data-driven analysis of ACCC merger reviews: Phase 1 and Phase 2 durations, waiver processing times, clearance rates, and year-on-year determination trends.',
  },
  '/phase-2': {
    title: 'Phase 2 tracker',
    description:
      'Track Australian mergers under ACCC Phase 2 (detailed) assessment, with referral dates, notice-of-competition-concerns milestones and determination deadlines.',
  },
  '/refiled-notifications': {
    title: 'Refiled notifications',
    description:
      'Mergers originally filed with the ACCC as a waiver application, declined, and then re-filed as a formal notification.',
  },
  '/extensions': {
    title: 'Phase 1 extensions',
    description:
      'How often, how long and why the ACCC extends its 30-business-day Phase 1 merger clock — and how strongly an extension foreshadows a Phase 2 escalation.',
  },
  '/commentary': {
    title: 'Commentary',
    description:
      'In-depth analysis of Australian merger cases — examining ACCC decisions, competitive concerns, economic reasoning, and M&A policy implications.',
  },
  '/digest': {
    title: 'Catch me up - ACCC Merger Tracker',
    description:
      'Weekly roundup of Australian merger activity: new ACCC notifications, Phase 1 clearances, Phase 2 launches, and upcoming consultation deadlines — all in one digest.',
  },
  '/nick-twort': {
    title: 'Nick Twort – Competition Economist | Australian Merger & Antitrust Expert',
    description:
      'Nick Twort is an Australian competition economist with eight years of experience advising on merger clearance, antitrust matters, and regulatory issues for the ACCC and New Zealand Commerce Commission. Expert in empirical analysis across airlines, digital platforms, supermarkets, telecoms and more.',
    type: 'profile',
  },
  '/privacy': {
    title: 'Privacy policy',
    description: 'How mergers.fyi collects, uses, and protects your personal information.',
  },
};
