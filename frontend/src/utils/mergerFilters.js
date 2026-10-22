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
import { dayOf, isIsoDate } from './dateTimeline';

/** Search params that hold a filter (the search box's `q` is handled apart). */
export const FILTER_PARAMS = ['phase', 'status', 'from', 'to', 'industry', 'conditions', 'tracked'];

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

/**
 * Was `m` notified (or, for a waiver, applied for) in [from, to], inclusive
 * YYYY-MM-DD strings? A matter with no notification date (a suspended
 * assessment) is outside every range.
 */
export function notifiedInRange(m, from, to) {
  const notified = dayOf(m.effective_notification_datetime);
  return Boolean(notified) && notified >= from && notified <= to;
}

/**
 * The range in the URL, or null when neither end is a usable date. Either end
 * may be left open; a range given backwards is turned round.
 */
export function dateRangeFrom(fromParam, toParam) {
  const from = isIsoDate(fromParam) ? fromParam : null;
  const to = isIsoDate(toParam) ? toParam : null;
  if (!from && !to) return null;
  const lo = from || '0000-01-01';
  const hi = to || '9999-12-31';
  return lo <= hi ? { from: lo, to: hi } : { from: hi, to: lo };
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
 * @param {Object} values - Raw param values: { q, phase, status, from, to, industry, conditions, tracked }
 * @param {Object} ctx - { isTracked, searchIndex }
 */
export function activeFilterTests(values, { isTracked, searchIndex }) {
  const tests = [];
  const { q, phase, status, from, to, industry, conditions, tracked } = values;
  const range = dateRangeFrom(from, to);
  if (phase && PHASE_TESTS[phase]) tests.push(['phase', PHASE_TESTS[phase]]);
  if (status && status !== 'all') tests.push(['status', (m) => displayedOutcome(m) === status]);
  if (range) tests.push(['date', (m) => notifiedInRange(m, range.from, range.to)]);
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
 *
 * The date filter's counts are per histogram bar and per quick range (see
 * utils/dateTimeline.js).
 *
 * @param {Object} dateAxis - { timeline, ranges }
 */
export function filterOptions(mergers, tests, { timeline, ranges = [] } = {}) {
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

  const dateBase = facet('date');
  const inRange = ({ from, to }) => countWhere(dateBase, (m) => notifiedInRange(m, from, to));
  const date = {
    bars: timeline ? timeline.bars.map(inRange) : [],
    ranges: ranges.map(inRange),
  };

  const present = new Set();
  for (const m of mergers) mergerDivisions(m).forEach((d) => present.add(d));
  const industryBase = facet('industry');
  const industry = [...present]
    .map((d) => ({ value: d, label: DIVISION_NAMES[d] || d }))
    .sort((a, b) => a.label.localeCompare(b.label))
    .map((o) => ({ ...o, count: countWhere(industryBase, (m) => mergerDivisions(m).has(o.value)) }));

  const conditions = countWhere(facet('conditions'), (m) => m.has_conditions);

  return { phase, status, date, industry, conditions };
}
