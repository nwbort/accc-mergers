import { describe, expect, it } from 'vitest';
import { getDecidedOutcome, getDeterminationDocUrl } from '../mergerOutcome';

const approved = {
  status: 'Assessment completed',
  accc_determination: 'Approved',
  stage: 'Phase 1 - initial assessment',
  effective_notification_datetime: '2026-06-01T12:00:00Z',
  determination_publication_date: '2026-07-01T12:00:00Z',
};

describe('getDecidedOutcome', () => {
  it('reports the determination once the assessment is completed', () => {
    expect(getDecidedOutcome(approved)).toEqual({
      outcome: 'Approved',
      appealSuffix: null,
      ceased: false,
    });
  });

  it('reports nothing while the matter is still under assessment', () => {
    expect(
      getDecidedOutcome({ status: 'Under assessment', accc_determination: null })
    ).toBeNull();
  });

  it('reports nothing for a suspended assessment', () => {
    expect(
      getDecidedOutcome({ status: 'Assessment suspended', accc_determination: null })
    ).toBeNull();
  });

  it('treats a ceased assessment as an outcome even though it has no determination', () => {
    expect(
      getDecidedOutcome({ status: 'Assessment ceased', accc_determination: null })
    ).toEqual({ outcome: 'Assessment ceased', appealSuffix: null, ceased: true });
  });

  it('leaves the ACCC determination in place while an appeal is still current', () => {
    const outcome = getDecidedOutcome({
      ...approved,
      accc_determination: 'Not approved',
      appeal: { status: 'current', outcome: null, effective_determination: null },
    });
    expect(outcome).toEqual({
      outcome: 'Not approved',
      appealSuffix: null,
      ceased: false,
    });
  });

  it('takes the outcome the tribunal left standing once an appeal has concluded', () => {
    const outcome = getDecidedOutcome({
      ...approved,
      accc_determination: 'Not approved',
      appeal: {
        status: 'concluded',
        outcome: 'set_aside',
        effective_determination: 'Approved',
      },
    });
    expect(outcome).toEqual({
      outcome: 'Approved',
      appealSuffix: 'on appeal',
      ceased: false,
    });
  });

  it('handles a missing merger', () => {
    expect(getDecidedOutcome(null)).toBeNull();
  });
});

describe('getDeterminationDocUrl', () => {
  it('links the determination document for a Phase 1 matter', () => {
    expect(
      getDeterminationDocUrl({
        events: [
          { title: 'Questionnaire', url_gh: '/q.pdf' },
          { title: 'Determination', is_determination_event: true, url_gh: '/d.pdf' },
        ],
      })
    ).toBe('/d.pdf');
  });

  it('prefers the statement of reasons where a Phase 2 matter publishes one', () => {
    expect(
      getDeterminationDocUrl({
        phase_2_determination: 'Not approved',
        events: [
          { title: 'Determination', is_determination_event: true, url_gh: '/d.pdf' },
          { title: 'Statement of reasons', url_gh: '/sor.pdf' },
        ],
      })
    ).toBe('/sor.pdf');
  });

  it('falls back to the determination when a Phase 2 matter has no statement yet', () => {
    expect(
      getDeterminationDocUrl({
        phase_2_determination: 'Not approved',
        events: [{ title: 'Determination', is_determination_event: true, url_gh: '/d.pdf' }],
      })
    ).toBe('/d.pdf');
  });

  it('returns null when no document is attached', () => {
    expect(getDeterminationDocUrl({ events: [] })).toBeNull();
    expect(getDeterminationDocUrl({})).toBeNull();
  });
});
