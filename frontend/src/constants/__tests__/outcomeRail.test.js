import { describe, expect, it } from 'vitest';
import { DEFAULT_OUTCOME_RAIL, getOutcomeRail } from '../outcomeRail';

describe('getOutcomeRail', () => {
  it('colours a cleared matter emerald', () => {
    expect(
      getOutcomeRail({ status: 'Assessment completed', determination: 'Approved' })
    ).toMatch(/emerald/);
  });

  it('colours a refused matter red', () => {
    expect(
      getOutcomeRail({ status: 'Assessment completed', determination: 'Not approved' })
    ).toMatch(/red/);
  });

  it('colours a ceased assessment purple, where there is no determination to read', () => {
    expect(getOutcomeRail({ status: 'Assessment ceased', determination: null })).toMatch(
      /purple/
    );
  });

  it('gives a live matter a rail of its own, so a rail is never the signal', () => {
    const rail = getOutcomeRail({ status: 'Under assessment', determination: null });
    expect(rail).toBe('bg-primary');
    expect(rail).not.toBe(DEFAULT_OUTCOME_RAIL);
  });

  it('prefers the determination over the status', () => {
    // Both are styled; the determination is the one that describes the result.
    expect(
      getOutcomeRail({ status: 'Assessment ceased', determination: 'Approved' })
    ).toMatch(/emerald/);
  });

  it('follows a concluded appeal, so the rail and the badge cannot disagree', () => {
    expect(
      getOutcomeRail({
        status: 'Assessment completed',
        determination: 'Not approved',
        appeal: { status: 'concluded', outcome: 'set_aside', effective_determination: 'Approved' },
      })
    ).toMatch(/emerald/);
  });

  it('leaves the rail on the ACCC determination while an appeal is still current', () => {
    expect(
      getOutcomeRail({
        status: 'Assessment completed',
        determination: 'Not approved',
        appeal: { status: 'current', outcome: null, effective_determination: null },
      })
    ).toMatch(/red/);
  });

  it('falls back rather than borrowing another outcome\'s colour', () => {
    expect(getOutcomeRail({ status: 'Assessment completed', determination: null })).toBe(
      DEFAULT_OUTCOME_RAIL
    );
    expect(getOutcomeRail()).toBe(DEFAULT_OUTCOME_RAIL);
  });
});
