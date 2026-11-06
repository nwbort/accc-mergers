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

// The site's one shared Open Graph image, used wherever a page has no card of
// its own.
export const DEFAULT_OG_IMAGE = `${SITE_URL}/og-image.png`;

// A generated card name is a bare slug plus `.png`; anything else in the field
// is ignored rather than written into a URL.
const OG_CARD_RE = /^[a-z0-9-]+\.png$/;

/**
 * The Open Graph image for a merger page: the generic card for its latest
 * milestone (`og_card`, chosen by scripts/generate/og_cards.py and drawn into
 * public/og/), or the shared image. The Pages Function in
 * functions/mergers/[matter]/[[path]].js keeps an inline copy for the
 * link-preview bots, pinned to this one by pageMeta.test.js.
 */
export function mergerOgImage(merger) {
  const card = merger?.og_card;
  return typeof card === 'string' && OG_CARD_RE.test(card)
    ? `${SITE_URL}/og/${card}`
    : DEFAULT_OG_IMAGE;
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
 *   image: string, structuredData: Object[]}}
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
      logo: { '@type': 'ImageObject', url: DEFAULT_OG_IMAGE },
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
    image: mergerOgImage(merger),
    structuredData: [
      articleSchema,
      breadcrumbSchema([{ name: 'Mergers', path: '/mergers' }], merger.merger_name, path),
    ],
    acquirers,
    targets,
  };
}

// Roles in the order the party page lists them, with how prose names each.
const PARTY_ROLES = [
  ['acquirer', 'acquirer'],
  ['target', 'target'],
  ['other', 'another party'],
];

// Legal-form suffixes dropped from a party's name in the <title> only: nobody
// searches "Vets Central Holdings Pty Ltd", and the full legal name stays the
// h1. Deliberately the common English-language forms, not every form
// utils/partyMembers.js knows ("AG", "SA", "Co") — those read as part of the
// name to most searchers.
const TITLE_LEGAL_FORMS = new Set(['pty', 'ltd', 'limited', 'inc', 'llc', 'plc']);

/** "Vets Central Holdings Pty Ltd" -> "Vets Central Holdings". */
export function partyTitleName(name) {
  const tokens = (name || '').trim().split(/\s+/);
  while (
    tokens.length > 1 &&
    TITLE_LEGAL_FORMS.has(tokens[tokens.length - 1].toLowerCase().replace(/[.,()]/g, ''))
  ) {
    tokens.pop();
  }
  return tokens.join(' ').replace(/[,\s]+$/, '');
}

/** Each of a party's mergers once, with the role it played (first role wins). */
function partyMergers(party) {
  const seen = new Set();
  const out = [];
  for (const [role] of PARTY_ROLES) {
    for (const m of party.mergers?.[role] || []) {
      const key = m?.merger_id || m?.merger_name;
      if (!key || seen.has(key)) continue;
      seen.add(key);
      out.push({ ...m, role });
    }
  }
  return out;
}

/** "as acquirer in 10 and as target in 2", or "all as acquirer" when only one role applies. */
function rolePhrase(mergers) {
  const roles = PARTY_ROLES.map(([role, label]) => [label, mergers.filter((m) => m.role === role).length])
    .filter(([, count]) => count);
  if (roles.length === 1) return `all as ${roles[0][0]}`;
  return joinList(roles.map(([label, count]) => `as ${label} in ${count}`));
}

/**
 * "the acquirer in Vets Central – Vital Vet Animal Hospital, a merger
 * notification approved by the ACCC".
 */
function singleMergerPhrase(m) {
  const role = m.role === 'other' ? 'a party' : `the ${m.role}`;
  const kind = m.is_waiver ? 'waiver application' : 'merger notification';
  let outcome;
  if (m.determination === 'Approved') {
    outcome = `${m.has_conditions ? 'approved with conditions' : 'approved'} by the ACCC`;
  } else if (m.determination === 'Not approved') {
    outcome = 'not approved by the ACCC';
  } else if (m.status === 'Assessment ceased') {
    outcome = 'whose ACCC assessment ceased';
  } else {
    outcome = 'under ACCC assessment';
  }
  return `${role} in ${m.merger_name}, a ${kind} ${outcome}`;
}

function partyDescription(party, name, mergers) {
  const n = mergers.length;
  if (!n) return `${name} on the ACCC merger register. No merger reviews have been recorded yet.`;
  if (n === 1) return `${name} was ${singleMergerPhrase(mergers[0])}.`;

  const first = sortedDays(mergers)[0];
  const since = first ? ` since ${monthYear(first)}` : '';
  const phase2 = party.phase_2_count ?? 0;
  const t = outcomeTally(mergers);
  let outcome;
  if (t.approved === n) {
    outcome = 'All approved.';
  } else {
    const parts = [];
    if (t.approved) parts.push(`${t.approved} approved`);
    if (t.notApproved) parts.push(`${t.notApproved} not approved`);
    if (t.ceased) parts.push(`${t.ceased} ceased`);
    if (t.open) parts.push(`${t.open} under assessment`);
    outcome = `${joinList(parts)}.`;
  }
  return (
    `${name} has been involved in ${plural(n, 'ACCC merger review')}${since}, ${rolePhrase(mergers)}` +
    `${phase2 ? `, including ${plural(phase2, 'Phase 2 review')}` : ''}. ${outcome}`
  );
}

/**
 * The party page's crawlable paragraph. A one-merger party gets a single
 * sentence plus its filing date: anything longer would mostly repeat that
 * merger's own page. Related entities are left out: the Related parties
 * block directly below already lists them. Null for a party with no mergers.
 */
export function partySummary(party, name) {
  const mergers = partyMergers(party);
  const n = mergers.length;
  if (!n) return null;

  if (n === 1) {
    const day = isoDay(mergers[0].notification_date);
    return `${name} was ${singleMergerPhrase(mergers[0])}${day ? `, lodged on ${longDate(day)}` : ''}.`;
  }

  const first = sortedDays(mergers)[0];
  const kinds = kindsPhrase(mergers);
  return [
    `${first ? `Since ${monthYear(first)}, ` : ''}${name} has been a party to ` +
      `${plural(n, 'ACCC merger review')}, ${rolePhrase(mergers)}.`,
    kinds ? `They comprise ${kinds}.` : null,
    phase2Sentence(party.phase_2_count ?? 0),
    outcomeSentence(mergers),
    timingSentence(party),
    latestSentence(mergers),
  ]
    .filter(Boolean)
    .join(' ');
}

/**
 * Meta for a party detail page, from a record read out of its
 * `data/parties/shard-{nn}.json` bucket. `id` is the route param, used as the
 * display fallback when the record has no canonical name (mirroring
 * PartyDetail.jsx).
 */
export function partyMeta(party, id) {
  const name = party.canonical_name || id;
  const path = partyPath(id, name);
  const mergerCount = party.merger_count ?? 0;
  const mergers = partyMergers(party);

  const title = `${partyTitleName(name)} – ACCC Merger Reviews`;
  const description = partyDescription(party, name, mergers);

  const collection = {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: title,
    description,
    url: absolute(path),
    inLanguage: 'en-AU',
    isPartOf: { '@type': 'WebSite', name: SITE_TITLE, url: SITE_URL },
    about: { '@type': 'Organization', name },
    mainEntity: mergerItemList(mergers),
  };

  return {
    title,
    description,
    summary: partySummary(party, name),
    path,
    type: 'website',
    structuredData: [
      breadcrumbSchema([{ name: 'Parties', path: '/parties' }], name, path),
      collection,
    ],
    name,
    mergerCount,
  };
}

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

// Register dates are stored as midday UTC (`2026-09-14T12:00:00Z`), so the
// calendar day is read straight off the string rather than through Date, which
// would shift it by the reader's (or the build machine's) timezone.
function isoDay(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
  return m ? { y: m[1], m: Number(m[2]), d: Number(m[3]), key: m[0] } : null;
}

function monthYear(day) {
  return `${MONTHS[day.m - 1]} ${day.y}`;
}

function longDate(day) {
  return `${day.d} ${MONTHS[day.m - 1]} ${day.y}`;
}

/** "a", "a and b", "a, b and c". */
function joinList(items) {
  if (items.length <= 1) return items.join('');
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;
}

// The register names a matter "Acquirer – Target" (en dash, em dash or a
// spaced hyphen). Summaries carry no party lists, so the acquirer is read off
// the name; an unspaced hyphen (Coca-Cola) is part of a name, not the split.
const MERGER_NAME_SPLIT_RE = /\s+[–—-]\s+/;

/**
 * Acquirers named on more than one of an industry's matters, most frequent
 * first (ties keep first-seen order, which is newest first). A matter filed
 * twice under the same name (a waiver then a notification, say) counts once,
 * so a single deal can't make its acquirer look "frequent".
 *
 * @returns {{name: string, count: number}[]}
 */
export function frequentAcquirers(mergers, limit = 3) {
  const seenDeals = new Set();
  const counts = new Map();
  for (const m of mergers || []) {
    const fullName = (m?.merger_name || '').trim();
    if (!fullName || seenDeals.has(fullName.toLowerCase())) continue;
    seenDeals.add(fullName.toLowerCase());
    const parts = fullName.split(MERGER_NAME_SPLIT_RE);
    if (parts.length < 2) continue;
    const acquirer = parts[0].trim();
    if (!acquirer) continue;
    counts.set(acquirer, (counts.get(acquirer) || 0) + 1);
  }
  return [...counts.entries()]
    .filter(([, count]) => count >= 2)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([name, count]) => ({ name, count }));
}

/** Outcome counts across an industry's merger summaries. */
function outcomeTally(mergers) {
  const tally = { approved: 0, conditions: 0, notApproved: 0, ceased: 0, open: 0 };
  for (const m of mergers) {
    if (m.determination === 'Approved') {
      tally.approved++;
      if (m.has_conditions) tally.conditions++;
    } else if (m.determination === 'Not approved') {
      tally.notApproved++;
    } else if (m.status === 'Assessment ceased') {
      tally.ceased++;
    } else {
      tally.open++;
    }
  }
  return tally;
}

function anzsicLabel(levelLabel, code) {
  return `ANZSIC ${levelLabel ? `${levelLabel.toLowerCase()} ` : ''}${code}`;
}

/** The notification days of a merger list, oldest first. */
function sortedDays(mergers) {
  const days = mergers.map((m) => isoDay(m.notification_date)).filter(Boolean);
  return days.sort((a, b) => a.key.localeCompare(b.key));
}

/** "3 notified mergers and 15 waiver applications". */
function kindsPhrase(mergers) {
  const waivers = mergers.filter((m) => m.is_waiver).length;
  const notified = mergers.length - waivers;
  const kinds = [];
  if (notified) kinds.push(plural(notified, 'notified merger'));
  if (waivers) kinds.push(plural(waivers, 'waiver application'));
  return joinList(kinds);
}

function phase2Sentence(phase2) {
  return phase2 ? `Of these, ${phase2} ${phase2 === 1 ? 'was' : 'were'} referred to Phase 2.` : null;
}

function outcomeSentence(mergers) {
  const n = mergers.length;
  const t = outcomeTally(mergers);
  const cond = t.conditions ? ` (${t.conditions} with conditions)` : '';
  if (t.approved === n) {
    return n === 1 ? `It was approved${cond}.` : `All ${n} were approved${cond}.`;
  }
  const parts = [];
  if (t.approved) parts.push(`${t.approved} approved${cond}`);
  if (t.notApproved) parts.push(`${t.notApproved} not approved`);
  if (t.ceased) parts.push(`${t.ceased} ceased`);
  if (t.open) parts.push(`${t.open} still under assessment`);
  return `Outcomes so far: ${joinList(parts)}.`;
}

/** The snippet's short outcome clause: ", all approved" or ": 9 approved and 1 not approved". */
function outcomeClause(mergers) {
  const n = mergers.length;
  const t = outcomeTally(mergers);
  if (t.approved === n) return n === 1 ? ', approved' : ', all approved';
  const parts = [];
  if (t.approved) parts.push(`${t.approved} approved`);
  if (t.notApproved) parts.push(`${t.notApproved} not approved`);
  if (t.open) parts.push(`${t.open} under assessment`);
  return parts.length ? `: ${joinList(parts)}` : '';
}

/** Median Phase 1 and waiver times, from a record's duration blocks. */
function timingSentence(record) {
  const p1 = record.phase_duration?.completed_count ? record.phase_duration.median_business_days : null;
  const wv = record.waiver_duration?.completed_count ? record.waiver_duration.median_business_days : null;
  if (p1 != null && wv != null) {
    return (
      `Completed Phase 1 reviews took a median of ${plural(p1, 'business day')}, ` +
      `and waivers a median of ${plural(wv, 'business day')}.`
    );
  }
  if (p1 != null) return `Completed Phase 1 reviews took a median of ${plural(p1, 'business day')}.`;
  if (wv != null) return `Waivers were decided in a median of ${plural(wv, 'business day')}.`;
  return null;
}

function latestSentence(mergers) {
  const days = sortedDays(mergers);
  const latestDay = days[days.length - 1];
  if (!latestDay || mergers.length < 2) return null;
  const latest = mergers.find((m) => isoDay(m.notification_date)?.key === latestDay.key);
  return latest?.merger_name
    ? `The most recent, ${latest.merger_name}, was lodged on ${longDate(latestDay)}.`
    : null;
}

/**
 * One crawlable paragraph describing an industry's merger activity, shown
 * under the heading on both the prerendered and the hydrated page. Built only
 * from the node's own summaries and stat blocks, so every industry page gets
 * text of its own rather than the same template around a different number.
 * Null for a node with no mergers.
 */
export function industrySummary(industry, code, name, levelLabel) {
  const mergers = industry.mergers || [];
  const n = mergers.length;
  if (!n) return null;

  const earliest = sortedDays(mergers)[0];
  const kinds = kindsPhrase(mergers);

  const acquirers = frequentAcquirers(mergers);
  let acquirerSentence = null;
  if (acquirers.length) {
    const listed = joinList(acquirers.map((a) => `${a.name} (${a.count})`));
    acquirerSentence =
      acquirers.length === 1
        ? `The most frequent acquirer is ${listed}.`
        : `The most frequent acquirers are ${listed}.`;
  }

  return [
    `${earliest ? `Since ${monthYear(earliest)}, the` : 'The'} ACCC has reviewed ` +
      `${plural(n, 'acquisition')} in the ${name} industry (${anzsicLabel(levelLabel, code)})` +
      `${kinds ? `: ${kinds}` : ''}.`,
    phase2Sentence(industry.phase_2_count ?? mergers.filter((m) => m.phase === 'Phase 2').length),
    outcomeSentence(mergers),
    acquirerSentence,
    timingSentence(industry),
    latestSentence(mergers),
  ]
    .filter(Boolean)
    .join(' ');
}

/** The search-result snippet: short enough not to be truncated, specific to the node. */
function industryDescription(industry, code, name, levelLabel) {
  const mergers = industry.mergers || [];
  const n = mergers.length;
  const label = anzsicLabel(levelLabel, code);
  if (!n) {
    return `ACCC merger reviews in the ${name} industry (${label}). None have been recorded yet.`;
  }

  const first = sortedDays(mergers)[0];
  const since = first ? ` since ${monthYear(first)}` : '';

  const acquirers = frequentAcquirers(mergers, 2);
  const acq = acquirers.length
    ? ` Frequent acquirers: ${acquirers.map((a) => a.name).join(', ')}.`
    : '';

  return `${plural(n, 'ACCC merger review')} in ${name} (${label})${since}${outcomeClause(mergers)}.${acq}`;
}

// How many matters the ItemList JSON-LD names. Matches prerender.js's cap on
// body links: the list describes the links the page actually carries.
const MAX_ITEM_LIST = 100;

/** schema.org ItemList of merger pages, for a CollectionPage's mainEntity. */
function mergerItemList(mergers) {
  return {
    '@type': 'ItemList',
    numberOfItems: mergers.length,
    itemListElement: mergers
      .filter((m) => m?.merger_id)
      .slice(0, MAX_ITEM_LIST)
      .map((m, i) => ({
        '@type': 'ListItem',
        position: i + 1,
        name: m.merger_name || m.merger_id,
        url: absolute(mergerPath(m.merger_id, m.merger_name)),
      })),
  };
}

/**
 * Meta for an industry detail page, from a node read out of
 * `data/industries/{division}.json` (utils/industryNode.js). `code` is the
 * route param; `indexName` is the fallback name from `industries.json` used
 * when the node carries none (mirroring IndustryDetail.jsx).
 */
export function industryMeta(industry, code, indexName) {
  const name = industry.name || indexName || code;
  const path = industryPath(code, name);
  const mergers = industry.mergers || [];
  const levelLabel = industry.level ? LEVEL_LABELS[industry.level] : null;

  // Keyword-first: what people search is "<industry> mergers" / "ACCC", and
  // the bare industry name said neither. The h1 stays the plain name.
  const title = `${name} Mergers – ACCC Reviews`;
  const description = industryDescription(industry, code, name, levelLabel);
  const summary = industrySummary(industry, code, name, levelLabel);

  // The ANZSIC ancestors already describe the crumb trail the page renders.
  const trail = [
    { name: 'Industries', path: '/industries' },
    ...(industry.ancestors || []).map((a) => ({
      name: a.name,
      path: industryPath(a.code, a.name),
    })),
  ];

  const collection = {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: title,
    description,
    url: absolute(path),
    inLanguage: 'en-AU',
    isPartOf: { '@type': 'WebSite', name: SITE_TITLE, url: SITE_URL },
    about: {
      '@type': 'DefinedTerm',
      name,
      termCode: code,
      inDefinedTermSet: 'ANZSIC 2006',
    },
    mainEntity: mergerItemList(mergers),
  };

  return {
    title,
    description,
    summary,
    path,
    type: 'website',
    structuredData: [breadcrumbSchema(trail, name, path), collection],
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
/** The page for one quarter of quarterly.json: `/quarterly/26Q3`. */
export function quarterlyPath(quarter) {
  return `/quarterly/${quarter.url_key}`;
}

/**
 * Meta for one quarter's report, from its quarterly.json block. The
 * description leads with the generated findings, so a search result says what
 * happened that quarter rather than what the page is.
 */
export function quarterlyMeta(quarter) {
  const title = `Quarterly merger report \u2013 ${quarter.label}`;
  const lead = (quarter.findings || []).slice(0, 2).join(' ');
  const path = quarterlyPath(quarter);
  return {
    title,
    description:
      `Australia's merger regime in ${quarter.label}: notifications, waivers, ACCC decision times, ` +
      `Phase 2 and Tribunal reviews.${lead ? ` ${lead}` : ''}`,
    path,
    type: 'website',
    structuredData: [
      breadcrumbSchema([{ name: 'Quarterly report', path: '/quarterly' }], quarter.label, path),
    ],
  };
}

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
  '/current-status': {
    title: 'Current status',
    description:
      'How fast the ACCC is deciding Australian merger notifications and waivers right now — recent decision times against the all-time baseline, and how they track the open caseload.',
  },
  '/quarterly': {
    title: 'Quarterly report',
    description:
      'A quarter-by-quarter report on Australia\'s merger regime: notifications and waivers, clearance rates, ACCC decision times, the industries deals came from, and every Phase 2, public benefit and Tribunal milestone.',
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
  '/copyright': {
    title: 'Copyright and licensing',
    description: 'How the data and documents on mergers.fyi are licensed, and how to credit them.',
  },
};
