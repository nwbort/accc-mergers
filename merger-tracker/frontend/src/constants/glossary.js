/**
 * Single source of truth for merger-review terminology.
 *
 * Every definition here is reused in two places:
 *   1. The Glossary page (/glossary), which lists every term, grouped by
 *      category, with an anchor at #<id>.
 *   2. The <GlossaryTerm id="..."> component, which shows the *same*
 *      `definition` text in a hover/focus popover and links back to
 *      /glossary#<id>.
 *
 * Because the tooltip and the glossary entry share one `definition` field,
 * keep each definition concise (roughly one to three sentences) so it reads
 * well inside a small popover as well as on the page.
 *
 * Accuracy note: definitions describe Australia's mandatory and suspensory
 * merger control regime, administered by the ACCC, which applies from
 * 1 January 2026 (with voluntary notification available from 1 July 2025).
 * Statutory timeframes are expressed in business days, which for this regime
 * exclude weekends, ACT public holidays, and 23 December to 10 January.
 *
 * Sources: ACCC merger control guidance and the Competition and Consumer Act
 * 2010 (Cth). See https://www.accc.gov.au/business/mergers-and-acquisitions
 */

// Category metadata controls grouping and ordering on the Glossary page.
export const GLOSSARY_CATEGORIES = [
  { id: 'regime', label: 'The regime', blurb: 'How merger control works in Australia.' },
  { id: 'process', label: 'The review process', blurb: 'The stages a notified acquisition moves through.' },
  { id: 'documents', label: 'Key documents', blurb: 'The main documents the ACCC publishes.' },
  { id: 'outcomes', label: 'Statuses and outcomes', blurb: 'The labels you see on merger and determination badges.' },
  { id: 'mechanisms', label: 'Other mechanisms', blurb: 'Alternative paths, remedies and review rights.' },
  { id: 'site', label: 'On this site', blurb: 'Terms used to organise the data shown here.' },
];

/**
 * @typedef {Object} GlossaryEntry
 * @property {string}   id          Kebab-case slug; used as the anchor and lookup key.
 * @property {string}   term        Canonical display name.
 * @property {string}   [abbr]      Short form, if the term is commonly abbreviated.
 * @property {string}   category    One of GLOSSARY_CATEGORIES[].id.
 * @property {string}   definition  Concise definition reused in the tooltip and on the page.
 * @property {string[]} [aliases]   Alternate spellings/labels, used for search matching.
 * @property {string[]} [related]   ids of related entries to cross-link.
 * @property {string}   [acccUrl]   Authoritative ACCC link for further reading.
 */

/** @type {GlossaryEntry[]} */
export const GLOSSARY = [
  // ---- The regime ----------------------------------------------------------
  {
    id: 'merger-control-regime',
    term: 'Mandatory and suspensory regime',
    category: 'regime',
    definition:
      'Australia’s merger control system from 1 January 2026. Acquisitions that meet the notification thresholds must be notified to the ACCC, and "suspensory" means the deal cannot complete until the ACCC approves it. Voluntary notification was available from 1 July 2025.',
    aliases: ['mandatory regime', 'suspensory', 'merger control'],
    related: ['notifiable-acquisition', 'notification', 'cca'],
    acccUrl: 'https://www.accc.gov.au/business/mergers-and-acquisitions/merger-control-regime',
  },
  {
    id: 'cca',
    term: 'Competition and Consumer Act',
    abbr: 'CCA',
    category: 'regime',
    definition:
      'The Competition and Consumer Act 2010 (Cth) — the legislation that contains Australia’s merger control rules and the substantial lessening of competition test, administered by the ACCC.',
    aliases: ['Competition and Consumer Act 2010', 'the Act'],
    related: ['accc', 'slc'],
  },
  {
    id: 'accc',
    term: 'ACCC',
    abbr: 'ACCC',
    category: 'regime',
    definition:
      'The Australian Competition and Consumer Commission — the national regulator that reviews and decides merger notifications under the Competition and Consumer Act.',
    aliases: ['Australian Competition and Consumer Commission'],
    related: ['cca', 'tribunal'],
    acccUrl: 'https://www.accc.gov.au/business/mergers-and-acquisitions',
  },
  {
    id: 'notifiable-acquisition',
    term: 'Notifiable acquisition',
    category: 'regime',
    definition:
      'An acquisition that meets the notification thresholds and so must be notified to, and approved by, the ACCC before it can complete.',
    aliases: ['notifiable'],
    related: ['notification-thresholds', 'notification', 'merger-control-regime'],
  },
  {
    id: 'notification-thresholds',
    term: 'Notification thresholds',
    category: 'regime',
    definition:
      'The size tests that decide whether an acquisition must be notified. They include a combined Australian turnover of the merger parties of at least $200 million, together with further target-based and market-concentration limbs set by the Treasurer.',
    aliases: ['thresholds', 'monetary threshold'],
    related: ['notifiable-acquisition', 'notification-waiver'],
    acccUrl: 'https://www.accc.gov.au/business/mergers-and-acquisitions/thresholds-for-notifying-acquisitions',
  },
  {
    id: 'slc',
    term: 'Substantial lessening of competition',
    abbr: 'SLC',
    category: 'regime',
    definition:
      'The legal test for clearance. The ACCC must approve an acquisition unless it is satisfied the acquisition would have the effect, or be likely to have the effect, of substantially lessening competition in any market.',
    aliases: ['substantially lessening competition', 'SLC test', 'competition test'],
    related: ['phase-2', 'public-benefit'],
  },
  {
    id: 'acquisitions-register',
    term: 'Acquisitions Register',
    category: 'regime',
    definition:
      'The public register on the ACCC website where notified acquisitions, waiver applications, key documents and determinations are published. This site mirrors and reorganises that data.',
    aliases: ['register', 'public register'],
    related: ['notification', 'determination'],
    acccUrl: 'https://www.accc.gov.au/public-registers/mergers-and-acquisitions-registers/acquisitions-register',
  },

  // ---- The review process --------------------------------------------------
  {
    id: 'pre-notification',
    term: 'Pre-notification engagement',
    category: 'process',
    definition:
      'Optional discussions with the ACCC before lodging, to settle the scope of the notification and the information required. The statutory review clock only starts once a valid notification is accepted.',
    aliases: ['pre-notification', 'pre-lodgement'],
    related: ['notification'],
  },
  {
    id: 'notification',
    term: 'Notification',
    category: 'process',
    definition:
      'The formal filing that starts an ACCC review. Once it is accepted the statutory clock begins, and the acquisition cannot complete until the ACCC approves it.',
    aliases: ['notify', 'merger notification'],
    related: ['phase-1', 'acquisitions-register', 'notifiable-acquisition'],
  },
  {
    id: 'phase-1',
    term: 'Phase 1 review',
    category: 'process',
    definition:
      'The initial review, lasting up to 30 business days. The ACCC can approve the acquisition (with or without commitments) from business day 15, or decide it needs an in-depth Phase 2 review.',
    aliases: ['phase 1', 'phase one'],
    related: ['phase-2', 'commitments', 'referred-to-phase-2'],
    acccUrl: 'https://www.accc.gov.au/business/mergers-and-acquisitions/assessment-process-and-review-timelines',
  },
  {
    id: 'phase-2',
    term: 'Phase 2 review',
    category: 'process',
    definition:
      'An in-depth review of up to 90 business days, used when the ACCC considers an acquisition could substantially lessen competition. It ends in an approval (with or without commitments) or a refusal.',
    aliases: ['phase 2', 'phase two', 'in-depth review'],
    related: ['phase-1', 'nocc', 'slc', 'commitments'],
    acccUrl: 'https://www.accc.gov.au/business/mergers-and-acquisitions/assessment-process-and-review-timelines',
  },
  {
    id: 'public-benefit',
    term: 'Public benefit application',
    category: 'process',
    definition:
      'An optional final stage where parties can ask the ACCC to approve an acquisition that lessens competition on the basis that it delivers a net public benefit. It is only available after the ACCC has decided the deal cannot otherwise proceed.',
    aliases: ['public benefits', 'net public benefit', 'public benefit phase'],
    related: ['slc', 'determination'],
  },
  {
    id: 'business-day',
    term: 'Business day',
    category: 'process',
    definition:
      'The unit the statutory clocks are measured in. For the merger regime a business day excludes weekends, ACT public holidays, and the period from 23 December to 10 January, so the clock pauses over the holidays.',
    aliases: ['business days'],
    related: ['phase-1', 'phase-2'],
  },

  // ---- Key documents -------------------------------------------------------
  {
    id: 'nocc',
    term: 'Notice of Competition Concerns',
    abbr: 'NOCC',
    category: 'documents',
    definition:
      'A document the ACCC issues by no later than business day 25 of a Phase 2 review, setting out its preliminary competition concerns. Merger parties then have 25 business days to respond.',
    aliases: ['notice of competition concerns'],
    related: ['phase-2', 'slc'],
  },
  {
    id: 'determination',
    term: 'Determination',
    category: 'documents',
    definition:
      'The ACCC’s formal, published decision on a notified acquisition or a waiver application, including its reasons.',
    aliases: ['determinations', 'decision'],
    related: ['approved', 'refused', 'acquisitions-register'],
  },

  // ---- Statuses and outcomes (match the badges shown across the site) ------
  {
    id: 'under-assessment',
    term: 'Under assessment',
    category: 'outcomes',
    definition:
      'A status meaning the ACCC is currently reviewing the notification and has not yet made a determination.',
    aliases: ['under assessment'],
    related: ['assessment-suspended', 'assessment-completed'],
  },
  {
    id: 'assessment-suspended',
    term: 'Assessment suspended',
    category: 'outcomes',
    definition:
      'A status meaning the statutory clock has been paused — for example while the ACCC waits for further information from the merger parties.',
    aliases: ['assessment suspended', 'suspended'],
    related: ['under-assessment', 'business-day'],
  },
  {
    id: 'assessment-completed',
    term: 'Assessment completed',
    category: 'outcomes',
    definition:
      'A status meaning the ACCC has finished its review and made a determination.',
    aliases: ['assessment completed', 'completed'],
    related: ['determination'],
  },
  {
    id: 'approved',
    term: 'Approved',
    category: 'outcomes',
    definition:
      'A determination that the ACCC has approved the acquisition, allowing it to proceed — sometimes subject to commitments offered by the parties.',
    aliases: ['approved', 'cleared', 'clearance'],
    related: ['commitments', 'refused', 'determination'],
  },
  {
    id: 'referred-to-phase-2',
    term: 'Referred to Phase 2',
    category: 'outcomes',
    definition:
      'The outcome at the end of Phase 1 where the ACCC decides the acquisition needs an in-depth Phase 2 review before it can be decided.',
    aliases: ['referred to phase 2', 'phase 2 referral'],
    related: ['phase-1', 'phase-2'],
  },
  {
    id: 'refused',
    term: 'Not approved',
    category: 'outcomes',
    definition:
      'A determination that the acquisition cannot proceed because the ACCC is satisfied it would substantially lessen competition and no net public benefit justifies it.',
    aliases: ['not approved', 'refused', 'blocked', 'opposed'],
    related: ['slc', 'public-benefit', 'tribunal'],
  },
  {
    id: 'declined',
    term: 'Declined',
    category: 'outcomes',
    definition:
      'A register label used where the ACCC has declined an application — for example declining to grant a notification waiver, or declining to approve an acquisition.',
    aliases: ['declined'],
    related: ['notification-waiver', 'refused'],
  },
  {
    id: 'not-opposed',
    term: 'Not opposed',
    category: 'outcomes',
    definition:
      'A legacy outcome from the former voluntary informal review, where the ACCC indicated it would not oppose an acquisition. It is retained here for historical matters reviewed before the 2026 regime.',
    aliases: ['not opposed', 'informal clearance'],
    related: ['approved'],
  },

  // ---- Other mechanisms ----------------------------------------------------
  {
    id: 'notification-waiver',
    term: 'Notification waiver',
    category: 'mechanisms',
    definition:
      'An ACCC decision that a specific acquisition does not need to be notified, even though it meets the thresholds. It offers a faster path for deals that clearly do not raise material competition concerns.',
    aliases: ['waiver', 'notification waivers'],
    related: ['notification-thresholds', 'notifiable-acquisition'],
    acccUrl: 'https://www.accc.gov.au/business/mergers-and-acquisitions/notification-waivers',
  },
  {
    id: 'commitments',
    term: 'Commitments',
    category: 'mechanisms',
    definition:
      'Court-enforceable undertakings parties offer to resolve the ACCC’s concerns — such as divesting a business (structural) or behavioural promises. They can be proposed in Phase 1 (by day 20), Phase 2 (by day 60) or the public benefit phase.',
    aliases: ['remedies', 'undertakings', 'commitment'],
    related: ['phase-1', 'phase-2', 'approved'],
  },
  {
    id: 'tribunal',
    term: 'Australian Competition Tribunal',
    category: 'mechanisms',
    definition:
      'The body to which a dissatisfied notifying party or third party can apply for a limited merits review of an ACCC merger determination.',
    aliases: ['tribunal', 'ACT'],
    related: ['determination', 'refused'],
  },

  // ---- On this site --------------------------------------------------------
  {
    id: 'anzsic',
    term: 'ANZSIC industry classification',
    abbr: 'ANZSIC',
    category: 'site',
    definition:
      'The Australian and New Zealand Standard Industrial Classification — the industry coding system this site uses to group mergers by sector.',
    aliases: ['ANZSIC', 'industry classification'],
    related: [],
  },
];

/** Fast lookup by id, e.g. GLOSSARY_BY_ID['phase-1']. */
export const GLOSSARY_BY_ID = Object.freeze(
  GLOSSARY.reduce((acc, entry) => {
    acc[entry.id] = entry;
    return acc;
  }, {})
);
