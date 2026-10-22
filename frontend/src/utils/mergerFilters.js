/**
 * Filters for the merger list.
 *
 * Every filter lives in a search param, so a filtered list can be shared and
 * bookmarked. Each one is a predicate over a list entry (`mergers/list.json`);
 * the page ANDs together the ones that are set. Keeping them as separate
 * predicates is also what makes the option counts honest: each select's
 * counts are taken over the list filtered by everything *except* that select,
 * so a count says what picking the option would leave, given the rest.
 */
import { PHASES, isPublicBenefitStage } from '../constants/mergerStatus';
import { DIVISION_NAMES, divisionForCode } from './industryDivision';
import { searchPredicate } from './searchIndex';

/** Search params that hold a filter (the search box's `q` is handled apart). */
export const FILTER_PARAMS = ['phase', 'status', 'notified', 'industry', 'conditions', 'tracked'];

/** What the status badge shows, and so what the status filter matches on. */
export const displayedOutcome = (m) => m.accc_determination || m.status;

export const PHASE_OPTIONS = [
  { value: 'phase1', label: PHASES.PHASE_1, test: (m) => Boolean(m.stage?.includes(PHASES.PHASE_1)) },
  // reached_phase_2 keeps a matter that has since moved on to the public
  // benefit phase (see outputs/list.py).
  { value: 'phase2', label: PHASES.PHASE_2, test: (m) => Boolean(m.reached_phase_2 || m.stage?.includes(PHASES.PHASE_2)) },
  { value: 'public-benefit', label: PHASES.PUBLIC_BENEFITS, test: (m) => isPublicBenefitStage(m.stage) },
  { value: 'waivers', label: PHASES.WAIVER, test: (m) => Boolean(m.is_waiver) },
];

const PHASE_TESTS = Object.fromEntries(PHASE_OPTIONS.map((o) => [o.value, o.test]));

const DAY_MS = 24 * 60 * 60 * 1000;

// Rolling windows, ahead of the calendar years. Measured back from now, so a
// shared `?notified=30d` link always means "lately", not a fixed date range.
export const NOTIFIED_WINDOWS = [
  { value: '30d', label: 'Last 30 days', days: 30 },
  { value: '90d', label: 'Last 90 days', days: 90 },
  { value: '12m', label: 'Last 12 months', days: 365 },
];

const WINDOW_DAYS = Object.fromEntries(NOTIFIED_WINDOWS.map((w) => [w.value, w.days]));

const notificationMs = (m) => {
  const t = Date.parse(m.effective_notification_datetime);
  return Number.isNaN(t) ? null : t;
};

/** Calendar year a matter was notified (or applied, for a waiver), as a string. */
export const notifiedYear = (m) => m.effective_notification_datetime?.slice(0, 4) || null;

/** Does `m` fall in the `?notified=` value — a rolling window or a year? */
export function matchesNotified(m, value, now = Date.now()) {
  const days = WINDOW_DAYS[value];
  if (days) {
    const t = notificationMs(m);
    return t !== null && t >= now - days * DAY_MS;
  }
  return notifiedYear(m) === value;
}

// A matter can be tagged with several codes, so it can sit in several
// divisions. Worked out once per list entry: the entries are only ever
// replaced wholesale, never mutated.
const divisionCache = new WeakMap();

/** The ANZSIC division letters a matter's industry codes fall under. */
export function mergerDivisions(m) {
  let divisions = divisionCache.get(m);
  if (!divisions) {
    divisions = new Set();
    for (const c of m.anzsic_codes || []) {
      const d = divisionForCode(c?.code);
      if (d) divisions.add(d);
    }
    divisionCache.set(m, divisions);
  }
  return divisions;
}

/**
 * The filters that are set, as `[param, predicate]` pairs, the search box's
 * included (as `q`). Unset filters (and unrecognised values for the
 * fixed-choice ones) are left out rather than passed as always-true
 * predicates.
 *
 * @param {Object} values - Raw param values: { q, phase, status, notified, industry, conditions, tracked }
 * @param {Object} ctx - { isTracked, searchIndex, now }
 */
export function activeFilterTests(values, { isTracked, searchIndex, now = Date.now() }) {
  const tests = [];
  const { q, phase, status, notified, industry, conditions, tracked } = values;
  if (phase && PHASE_TESTS[phase]) tests.push(['phase', PHASE_TESTS[phase]]);
  if (status && status !== 'all') tests.push(['status', (m) => displayedOutcome(m) === status]);
  if (notified) tests.push(['notified', (m) => matchesNotified(m, notified, now)]);
  if (industry) tests.push(['industry', (m) => mergerDivisions(m).has(industry)]);
  if (conditions === 'true') tests.push(['conditions', (m) => Boolean(m.has_conditions)]);
  if (tracked === 'true') tests.push(['tracked', (m) => isTracked(m.merger_id)]);
  const matchesSearch = searchIndex ? searchPredicate(q, searchIndex) : null;
  if (matchesSearch) tests.push(['q', matchesSearch]);
  return tests;
}

/**
 * `mergers` with every test applied except `skip` (a param name), if given.
 * Returns the input array itself when nothing applies, so an unfiltered list
 * keeps its identity.
 */
export function applyFilters(mergers, tests, skip = null) {
  let result = mergers;
  for (const [key, test] of tests) {
    if (key !== skip) result = result.filter(test);
  }
  return result;
}

const countWhere = (list, test) => list.reduce((n, m) => (test(m) ? n + 1 : n), 0);

/**
 * Options for each filter, with counts.
 *
 * The option *lists* come from the whole data set, so an option doesn't
 * vanish just because another filter leaves it empty — it shows (0) instead.
 * The *counts* come from the list filtered by every other filter.
 */
export function filterOptions(mergers, tests, now = Date.now()) {
  const facet = (key) => applyFilters(mergers, tests, key);

  const phaseBase = facet('phase');
  const phase = PHASE_OPTIONS.map(({ value, label, test }) => ({
    value, label, count: countWhere(phaseBase, test),
  }));

  // Most common first: "Approved" is nine in ten matters, and the rarer
  // outcomes are the ones worth a glance down the list for.
  const statusTotals = new Map();
  for (const m of mergers) {
    const o = displayedOutcome(m);
    if (o) statusTotals.set(o, (statusTotals.get(o) || 0) + 1);
  }
  const statusBase = facet('status');
  const status = [...statusTotals.keys()]
    .sort((a, b) => statusTotals.get(b) - statusTotals.get(a) || a.localeCompare(b))
    .map((value) => ({ value, label: value, count: countWhere(statusBase, (m) => displayedOutcome(m) === value) }));

  const notifiedBase = facet('notified');
  const years = [...new Set(mergers.map(notifiedYear).filter(Boolean))].sort().reverse();
  const notified = [
    ...NOTIFIED_WINDOWS.map(({ value, label }) => ({ value, label })),
    ...years.map((y) => ({ value: y, label: y })),
  ].map((o) => ({ ...o, count: countWhere(notifiedBase, (m) => matchesNotified(m, o.value, now)) }));

  const present = new Set();
  for (const m of mergers) mergerDivisions(m).forEach((d) => present.add(d));
  const industryBase = facet('industry');
  const industry = [...present]
    .map((d) => ({ value: d, label: DIVISION_NAMES[d] || d }))
    .sort((a, b) => a.label.localeCompare(b.label))
    .map((o) => ({ ...o, count: countWhere(industryBase, (m) => mergerDivisions(m).has(o.value)) }));

  const conditions = countWhere(facet('conditions'), (m) => m.has_conditions);

  return { phase, status, notified, industry, conditions };
}
