import { describe, expect, it } from 'vitest';
import { phase2Outcome, summarisePhase2 } from '../phase2Summary';

const completedMatter = (overrides) => ({
  merger_id: 'MN-0001',
  merger_name: 'Alpha acquires Beta',
  determination: 'Approved',
  referral_date: '2026-01-01T12:00:00Z',
  determination_date: '2026-05-01T12:00:00Z',
  has_conditions: false,
  ...overrides,
});

describe('phase2Outcome', () => {
  it('counts a conditional clearance as its own outcome', () => {
    expect(phase2Outcome(completedMatter({ has_conditions: true })))
      .toBe('Approved with conditions');
  });

  it('ignores a conditions flag left on a non-approval', () => {
    expect(phase2Outcome(completedMatter({ determination: 'Not approved', has_conditions: true })))
      .toBe('Not approved');
  });
});

describe('summarisePhase2', () => {
  it('counts running and completed matters', () => {
    const summary = summarisePhase2(
      [{ merger_id: 'MN-1' }, { merger_id: 'MN-2' }],
      [completedMatter()]
    );
    expect(summary.total).toBe(3);
    expect(summary.currentCount).toBe(2);
    expect(summary.completedCount).toBe(1);
  });

  it('splits completed reviews by outcome, cleared first and ceased last', () => {
    const summary = summarisePhase2([], [
      completedMatter({ merger_id: 'MN-1', determination: 'Assessment ceased' }),
      completedMatter({ merger_id: 'MN-2', determination: 'Not approved' }),
      completedMatter({ merger_id: 'MN-3', has_conditions: true }),
      completedMatter({ merger_id: 'MN-4' }),
    ]);
    expect(summary.outcomes).toEqual([
      { label: 'Approved', count: 1, share: 25 },
      { label: 'Approved with conditions', count: 1, share: 25 },
      { label: 'Not approved', count: 1, share: 25 },
      { label: 'Assessment ceased', count: 1, share: 25 },
    ]);
  });

  it('appends an outcome the fixed order does not know about rather than dropping it', () => {
    const summary = summarisePhase2([], [
      completedMatter({ merger_id: 'MN-1', determination: 'Something new' }),
      completedMatter({ merger_id: 'MN-2' }),
    ]);
    expect(summary.outcomes.map((o) => o.label)).toEqual(['Approved', 'Something new']);
  });

  it('averages the referral-to-determination span in calendar days', () => {
    const summary = summarisePhase2([], [
      completedMatter({ merger_id: 'MN-1', determination_date: '2026-01-11T12:00:00Z' }), // 10
      completedMatter({ merger_id: 'MN-2', determination_date: '2026-01-21T12:00:00Z' }), // 20
    ]);
    expect(summary.averageDays).toBe(15);
    expect(summary.averageBasis).toBe(2);
  });

  it('leaves ceased assessments out of the average', () => {
    const summary = summarisePhase2([], [
      completedMatter({ merger_id: 'MN-1', determination_date: '2026-01-11T12:00:00Z' }), // 10
      completedMatter({
        merger_id: 'MN-2',
        determination: 'Assessment ceased',
        determination_date: '2026-01-03T12:00:00Z', // 2 days — would halve the mean
      }),
    ]);
    expect(summary.averageDays).toBe(10);
    expect(summary.averageBasis).toBe(1);
    expect(summary.ceasedCount).toBe(1);
    // ...but the ceased matter still counts toward the outcome split.
    expect(summary.outcomes).toContainEqual({ label: 'Assessment ceased', count: 1, share: 50 });
  });

  it('skips a matter whose dates cannot produce a duration', () => {
    const summary = summarisePhase2([], [
      completedMatter({ merger_id: 'MN-1', determination_date: '2026-01-11T12:00:00Z' }),
      completedMatter({ merger_id: 'MN-2', referral_date: null }),
    ]);
    expect(summary.averageDays).toBe(10);
    expect(summary.averageBasis).toBe(1);
  });

  it('reports no average when nothing has been determined', () => {
    const summary = summarisePhase2([{ merger_id: 'MN-1' }], []);
    expect(summary.averageDays).toBeNull();
    expect(summary.averageBasis).toBe(0);
    expect(summary.outcomes).toEqual([]);
  });
});
