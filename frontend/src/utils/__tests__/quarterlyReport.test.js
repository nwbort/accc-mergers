import { describe, expect, it } from 'vitest';
import {
  bucketShares,
  findQuarter,
  formatRate,
  percentChange,
  pickQuarter,
  previousQuarter,
} from '../quarterlyReport';

function quarter(key, overrides = {}) {
  const [year, q] = key.split('-');
  return {
    quarter: key,
    url_key: `${year.slice(2)}${q}`,
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
const QUARTERS = [Q2, Q3];

describe('pickQuarter', () => {
  it('honours a quarter named in the URL by its short key', () => {
    expect(pickQuarter(QUARTERS, '26Q2')).toBe(Q2);
    expect(pickQuarter(QUARTERS, '26q2')).toBe(Q2);
  });

  it('still reads the long form older links used', () => {
    expect(pickQuarter(QUARTERS, '2026-Q2')).toBe(Q2);
  });

  it('defaults to the latest quarter', () => {
    expect(pickQuarter(QUARTERS, null)).toBe(Q3);
    expect(pickQuarter(QUARTERS, '1999-Q1')).toBe(Q3);
  });

  it('is null with nothing published', () => {
    expect(pickQuarter([], null)).toBeNull();
  });
});

describe('findQuarter', () => {
  it('matches exactly, or not at all', () => {
    expect(findQuarter(QUARTERS, '26Q3')).toBe(Q3);
    expect(findQuarter(QUARTERS, '26q3')).toBe(Q3);
    expect(findQuarter(QUARTERS, '2026-Q3')).toBe(Q3);
    expect(findQuarter(QUARTERS, '26Q4')).toBeNull();
    expect(findQuarter(QUARTERS, null)).toBeNull();
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
