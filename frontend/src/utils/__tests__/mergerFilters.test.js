import { describe, expect, it } from 'vitest';
import {
  activeFilterTests,
  applyFilters,
  dateRangeFrom,
  filterOptions,
  matchesDateRange,
  mergerDivisions,
} from '../mergerFilters';
import { buildSearchIndex } from '../searchIndex';


const MERGERS = [
  {
    merger_id: 'MN-1',
    merger_name: 'Ampol / Z Energy',
    status: 'Assessment completed',
    accc_determination: 'Approved',
    has_conditions: true,
    stage: 'Phase 1 - initial assessment',
    effective_notification_datetime: '2026-10-01T12:00:00Z',
    determination_publication_date: '2026-10-15T12:00:00Z',
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
    determination_publication_date: '2026-03-20T12:00:00Z',
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

  it('filters by notification date range by default', () => {
    expect(filtered({ from: '2026-01-01', to: '2026-12-31' })).toEqual(['MN-1', 'WA-2']);
    expect(filtered({ from: '2026-10-01', to: '2026-10-01' })).toEqual(['MN-1']);
    // Either end may be left open.
    expect(filtered({ to: '2025-12-31' })).toEqual(['MN-3']);
    expect(filtered({ from: '2026-03-01' })).toEqual(['MN-1', 'WA-2']);
  });

  it('filters by determination date, leaving open matters out', () => {
    expect(filtered({ date: 'determined', from: '2026-03-01', to: '2026-03-31' })).toEqual(['WA-2']);
    expect(filtered({ date: 'determined', from: '2025-01-01', to: '2026-12-31' })).toEqual(['MN-1', 'WA-2']);
  });

  it('ignores dates that are not dates, and an unknown date field', () => {
    expect(filtered({ from: 'yesterday', to: '' })).toEqual(ids(MERGERS));
    // "open" was once a field; an old link falls back to notified.
    expect(filtered({ date: 'open', from: '2025-11-01', to: '2025-11-01' })).toEqual(['MN-3']);
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

describe('matchesDateRange', () => {
  it('never matches a matter with no notification date', () => {
    for (const field of ['notified', 'determined']) {
      expect(matchesDateRange(MERGERS[3], field, '2000-01-01', '2099-12-31')).toBe(false);
    }
  });
});

describe('dateRangeFrom', () => {
  it('turns a backwards range round and opens a missing end', () => {
    expect(dateRangeFrom('2026-05-01', '2026-04-01')).toEqual({ from: '2026-04-01', to: '2026-05-01' });
    expect(dateRangeFrom('2026-05-01', null)).toEqual({ from: '2026-05-01', to: '9999-12-31' });
    expect(dateRangeFrom(null, '')).toBeNull();
    expect(dateRangeFrom('2026-02-30', null)).toBeNull();
  });
});

describe('mergerDivisions', () => {
  it('collects each division once and skips codes with none', () => {
    expect([...mergerDivisions(MERGERS[0])].sort()).toEqual(['F', 'G']);
    expect(mergerDivisions(MERGERS[3]).size).toBe(0);
  });
});

describe('filterOptions', () => {
  const ctx = { isTracked: () => false, searchIndex: buildSearchIndex(MERGERS) };

  it('counts each option against every other filter, but not its own', () => {
    const tests = activeFilterTests({ phase: 'phase2', status: 'Approved' }, ctx);
    const options = filterOptions(MERGERS, tests);
    // Phase counts ignore the phase filter but honour status = Approved.
    expect(options.phase.find((o) => o.value === 'phase1').count).toBe(1);
    expect(options.phase.find((o) => o.value === 'phase2').count).toBe(0);
    // Status counts ignore status but honour phase = Phase 2.
    expect(options.status.find((o) => o.value === 'Under assessment').count).toBe(2);
    expect(options.status.find((o) => o.value === 'Approved').count).toBe(0);
  });

  it('lists every option from the whole data set, most common status first', () => {
    const options = filterOptions(MERGERS, []);
    expect(options.status.map((o) => o.value)).toEqual(['Approved', 'Under assessment']);
    expect(options.industry.map((o) => o.label)).toEqual(['Mining', 'Retail Trade', 'Wholesale Trade']);
    expect(options.industry.find((o) => o.value === 'F').count).toBe(2);
    expect(options.conditions).toBe(1);
  });
});

describe('filterOptions date counts', () => {
  const ctx = { isTracked: () => false, searchIndex: buildSearchIndex(MERGERS) };
  const timeline = {
    bars: [{ from: '2025-11-01', to: '2025-11-30' }, { from: '2026-03-01', to: '2026-03-31' }],
  };
  const ranges = [{ from: '2026-01-01', to: '2026-12-31' }];

  it('counts each bar and quick range on the chosen date field', () => {
    const notified = filterOptions(MERGERS, [], { field: 'notified', timeline, ranges }).date;
    expect(notified).toEqual({ bars: [1, 1], ranges: [2] });
    // MN-3 (notified in November) is still open, so it has no determination.
    const determined = filterOptions(MERGERS, [], { field: 'determined', timeline, ranges }).date;
    expect(determined).toEqual({ bars: [0, 1], ranges: [2] });
  });

  it('ignores the date range itself but honours the other filters', () => {
    const tests = activeFilterTests({ from: '2026-03-01', to: '2026-03-31', phase: 'waivers' }, ctx);
    const { date } = filterOptions(MERGERS, tests, { field: 'notified', timeline, ranges });
    expect(date.bars).toEqual([0, 1]);
    expect(date.ranges).toEqual([1]);
  });
});
