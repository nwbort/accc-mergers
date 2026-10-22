import { describe, expect, it } from 'vitest';
import {
  activeFilterTests,
  applyFilters,
  filterOptions,
  matchesNotified,
  mergerDivisions,
} from '../mergerFilters';
import { buildSearchIndex } from '../searchIndex';

const NOW = Date.parse('2026-10-22T00:00:00Z');

const MERGERS = [
  {
    merger_id: 'MN-1',
    merger_name: 'Ampol / Z Energy',
    status: 'Assessment completed',
    accc_determination: 'Approved',
    has_conditions: true,
    stage: 'Phase 1 - initial assessment',
    effective_notification_datetime: '2026-10-01T12:00:00Z',
    anzsic_codes: [{ code: '4000', name: 'Fuel Retailing' }, { code: '3321', name: 'Petroleum Product Wholesaling' }],
  },
  {
    merger_id: 'WA-2',
    merger_name: 'Woolworths / PFD',
    status: 'Assessment completed',
    accc_determination: 'Approved',
    is_waiver: true,
    stage: 'Waiver application',
    effective_notification_datetime: '2026-03-01T12:00:00Z',
    anzsic_codes: [{ code: '3600', name: 'Grocery Wholesaling' }],
  },
  {
    merger_id: 'MN-3',
    merger_name: 'BHP / Anglo',
    status: 'Under assessment',
    accc_determination: null,
    stage: 'Phase 2 - detailed assessment',
    effective_notification_datetime: '2025-11-01T12:00:00Z',
    anzsic_codes: [{ code: '0800', name: 'Metal Ore Mining' }],
  },
  {
    merger_id: 'MN-4',
    merger_name: 'Moved on to public benefit',
    status: 'Under assessment',
    accc_determination: null,
    reached_phase_2: true,
    stage: 'Public benefit phase',
    effective_notification_datetime: null,
    anzsic_codes: [{ code: '9999/1', name: 'Junk tag' }],
  },
];

const ids = (list) => list.map((m) => m.merger_id);

function filtered(values, ctx = {}) {
  const tests = activeFilterTests(values, {
    isTracked: () => false,
    searchIndex: buildSearchIndex(MERGERS),
    now: NOW,
    ...ctx,
  });
  return ids(applyFilters(MERGERS, tests));
}

describe('activeFilterTests + applyFilters', () => {
  it('returns the input array itself when nothing is set', () => {
    const tests = activeFilterTests({}, { isTracked: () => false, searchIndex: buildSearchIndex(MERGERS) });
    expect(tests).toEqual([]);
    expect(applyFilters(MERGERS, tests)).toBe(MERGERS);
  });

  it('filters by phase, keeping a matter that moved on from Phase 2 under Phase 2', () => {
    expect(filtered({ phase: 'phase1' })).toEqual(['MN-1']);
    expect(filtered({ phase: 'phase2' })).toEqual(['MN-3', 'MN-4']);
    expect(filtered({ phase: 'public-benefit' })).toEqual(['MN-4']);
    expect(filtered({ phase: 'waivers' })).toEqual(['WA-2']);
  });

  it('ignores an unrecognised phase rather than emptying the list', () => {
    expect(filtered({ phase: 'all' })).toEqual(ids(MERGERS));
  });

  it('filters by the outcome the badge shows', () => {
    expect(filtered({ status: 'Approved' })).toEqual(['MN-1', 'WA-2']);
    expect(filtered({ status: 'Under assessment' })).toEqual(['MN-3', 'MN-4']);
    expect(filtered({ status: 'all' })).toEqual(ids(MERGERS));
  });

  it('filters by notification window or year', () => {
    expect(filtered({ notified: '30d' })).toEqual(['MN-1']);
    expect(filtered({ notified: '12m' })).toEqual(['MN-1', 'WA-2', 'MN-3']);
    expect(filtered({ notified: '2025' })).toEqual(['MN-3']);
  });

  it('filters by ANZSIC division, through any of a matter\'s codes', () => {
    expect(filtered({ industry: 'F' })).toEqual(['MN-1', 'WA-2']);
    expect(filtered({ industry: 'G' })).toEqual(['MN-1']);
    expect(filtered({ industry: 'B' })).toEqual(['MN-3']);
  });

  it('filters to conditional approvals and to tracked matters', () => {
    expect(filtered({ conditions: 'true' })).toEqual(['MN-1']);
    expect(filtered({ tracked: 'true' }, { isTracked: (id) => id === 'MN-3' })).toEqual(['MN-3']);
  });

  it('combines the search box with the other filters', () => {
    expect(filtered({ q: 'wholesaling' })).toEqual(['MN-1', 'WA-2']);
    expect(filtered({ q: 'wholesaling', phase: 'waivers' })).toEqual(['WA-2']);
  });
});

describe('matchesNotified', () => {
  it('never puts a matter with no notification date in a window or year', () => {
    expect(matchesNotified(MERGERS[3], '12m', NOW)).toBe(false);
    expect(matchesNotified(MERGERS[3], '2026', NOW)).toBe(false);
  });
});

describe('mergerDivisions', () => {
  it('collects each division once and skips codes with none', () => {
    expect([...mergerDivisions(MERGERS[0])].sort()).toEqual(['F', 'G']);
    expect(mergerDivisions(MERGERS[3]).size).toBe(0);
  });
});

describe('filterOptions', () => {
  const ctx = { isTracked: () => false, searchIndex: buildSearchIndex(MERGERS), now: NOW };

  it('counts each option against every other filter, but not its own', () => {
    const tests = activeFilterTests({ phase: 'phase2', status: 'Approved' }, ctx);
    const options = filterOptions(MERGERS, tests, NOW);
    // Phase counts ignore the phase filter but honour status = Approved.
    expect(options.phase.find((o) => o.value === 'phase1').count).toBe(1);
    expect(options.phase.find((o) => o.value === 'phase2').count).toBe(0);
    // Status counts ignore status but honour phase = Phase 2.
    expect(options.status.find((o) => o.value === 'Under assessment').count).toBe(2);
    expect(options.status.find((o) => o.value === 'Approved').count).toBe(0);
  });

  it('lists every option from the whole data set, most common status first', () => {
    const options = filterOptions(MERGERS, [], NOW);
    expect(options.status.map((o) => o.value)).toEqual(['Approved', 'Under assessment']);
    expect(options.notified.map((o) => o.value)).toEqual(['30d', '90d', '12m', '2026', '2025']);
    expect(options.industry.map((o) => o.label)).toEqual(['Mining', 'Retail Trade', 'Wholesale Trade']);
    expect(options.industry.find((o) => o.value === 'F').count).toBe(2);
    expect(options.conditions).toBe(1);
  });
});
