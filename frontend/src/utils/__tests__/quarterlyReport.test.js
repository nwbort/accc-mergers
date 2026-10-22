import { describe, expect, it } from 'vitest';
import {
  bucketShares,
  formatRate,
  keyFindings,
  percentChange,
  pickQuarter,
  previousQuarter,
} from '../quarterlyReport';

function quarter(key, overrides = {}) {
  const [year, q] = key.split('-');
  return {
    quarter: key,
    label: `${q} ${year}`,
    notifications: {
      filed: 100,
      phase_1_decided: 90,
      cleared: 88,
      referred_to_phase_2: 2,
      refused: 0,
      ceased: 0,
      clearance_rate: 88 / 90,
      timing: { median: 17, buckets: [] },
      ...overrides.notifications,
    },
    waivers: {
      decided: 150,
      granted: 144,
      refused: 6,
      clearance_rate: 0.96,
      timing: { median: 12, buckets: [] },
      ...overrides.waivers,
    },
    milestones: overrides.milestones ?? [],
    complete: overrides.complete ?? true,
  };
}

const Q2 = quarter('2026-Q2');
const Q3 = quarter('2026-Q3', {
  notifications: { filed: 113, timing: { median: 18, buckets: [] } },
  waivers: { decided: 183, timing: { median: 17, buckets: [] } },
  milestones: [
    { kind: 'phase_2_outcome', detail: 'Not approved' },
    { kind: 'phase_2_outcome', detail: 'Not approved' },
    { kind: 'phase_2_outcome', detail: 'Assessment ceased' },
    { kind: 'tribunal_application', detail: 'Coles' },
  ],
});
const Q4 = quarter('2026-Q4', { complete: false, notifications: { filed: 29 } });
const QUARTERS = [Q2, Q3, Q4];

describe('pickQuarter', () => {
  it('honours a quarter named in the URL', () => {
    expect(pickQuarter(QUARTERS, '2026-Q2')).toBe(Q2);
    expect(pickQuarter(QUARTERS, '2026-Q4')).toBe(Q4);
  });

  it('defaults to the latest complete quarter, not the one in progress', () => {
    expect(pickQuarter(QUARTERS, null)).toBe(Q3);
    expect(pickQuarter(QUARTERS, '1999-Q1')).toBe(Q3);
  });

  it('falls back to the latest quarter when none is complete, and null when empty', () => {
    expect(pickQuarter([Q4], null)).toBe(Q4);
    expect(pickQuarter([], null)).toBeNull();
  });
});

describe('previousQuarter', () => {
  it('is the quarter before in the list', () => {
    expect(previousQuarter(QUARTERS, Q3)).toBe(Q2);
    expect(previousQuarter(QUARTERS, Q2)).toBeNull();
  });
});

describe('figures', () => {
  it('rounds percentage change and refuses a zero base', () => {
    expect(percentChange(113, 95)).toBe(19);
    expect(percentChange(5, 0)).toBeNull();
    expect(percentChange(null, 10)).toBeNull();
  });

  it('formats rates as whole percentages', () => {
    expect(formatRate(0.9617)).toBe('96%');
    expect(formatRate(null)).toBe('–');
  });

  it('turns bucket counts into shares', () => {
    expect(bucketShares([1, 1, 2])).toEqual([25, 25, 50]);
    expect(bucketShares([0, 0])).toEqual([0, 0]);
  });
});

describe('keyFindings', () => {
  it('compares volume and timing with the previous quarter', () => {
    const [volume, timing, rates, phase2] = keyFindings(Q3, Q2);
    expect(volume).toBe(
      '113 notifications filed, up 13% on Q2 2026, and 183 waiver applications decided, up 22% on Q2 2026.'
    );
    expect(timing).toBe(
      'Phase 1 reviews concluded in a median 18 business days, 1 day slower than Q2 2026; waivers in 17, 5 days slower than Q2 2026.'
    );
    expect(rates).toBe('96% of waivers were granted and 98% of phase 1 reviews ended in approval.');
    expect(phase2).toBe(
      '2 matters referred to phase 2; 3 phase 2 reviews concluded (2 not approved, 1 assessment ceased).'
    );
  });

  it('leaves volume uncompared for a quarter still in progress', () => {
    const [volume] = keyFindings(Q4, Q3);
    expect(volume).toBe('29 notifications filed, and 150 waiver applications decided.');
  });

  it('has no comparisons for the first quarter', () => {
    const [volume, timing] = keyFindings(Q2, null);
    expect(volume).not.toContain(' on ');
    expect(timing).toBe('Phase 1 reviews concluded in a median 17 business days; waivers in 12.');
  });
});
