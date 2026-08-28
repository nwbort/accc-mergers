import { describe, expect, it } from 'vitest';
import {
  acccDecisionSentence,
  durationSentence,
  getDecidedOutcome,
  getDeterminationDocUrl,
} from '../mergerOutcome';

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

describe('acccDecisionSentence', () => {
  it('names the phase a notification was cleared in', () => {
    expect(acccDecisionSentence(approved, approved.determination_publication_date)).toBe(
      'The ACCC cleared this acquisition in Phase 1 on 1 July 2026.'
    );
  });

  it('spells out a conditional clearance', () => {
    expect(
      acccDecisionSentence(
        { ...approved, has_conditions: true, stage: 'Phase 2 - detailed assessment' },
        approved.determination_publication_date
      )
    ).toBe('The ACCC cleared this acquisition subject to conditions in Phase 2 on 1 July 2026.');
  });

  it('describes a refusal rather than repeating the register label', () => {
    expect(
      acccDecisionSentence(
        { ...approved, accc_determination: 'Not approved', stage: 'Phase 2 - detailed assessment' },
        approved.determination_publication_date
      )
    ).toBe('The ACCC refused to approve this acquisition in Phase 2 on 1 July 2026.');
  });

  it('uses waiver wording for a waiver application', () => {
    const waiver = { ...approved, is_waiver: true, stage: 'Waiver application' };
    expect(acccDecisionSentence(waiver, waiver.determination_publication_date)).toBe(
      'The ACCC granted a notification waiver on 1 July 2026.'
    );
    expect(
      acccDecisionSentence(
        { ...waiver, accc_determination: 'Not approved' },
        waiver.determination_publication_date
      )
    ).toBe('The ACCC did not grant a notification waiver on 1 July 2026.');
  });

  it('describes a ceased assessment, which has no determination to report', () => {
    expect(
      acccDecisionSentence(
        { status: 'Assessment ceased', accc_determination: null },
        '2026-07-16T12:00:00Z'
      )
    ).toBe('The ACCC ceased its assessment of this acquisition on 16 July 2026.');
  });

  it('drops the date when the register never published one', () => {
    expect(acccDecisionSentence(approved, null)).toBe(
      'The ACCC cleared this acquisition in Phase 1.'
    );
  });
});

describe('durationSentence', () => {
  it('counts calendar and business days from notification', () => {
    expect(
      durationSentence(approved, '2026-06-01T12:00:00Z', '2026-07-01T12:00:00Z')
    ).toBe('30 calendar days (21 business days) from notification.');
  });

  it('says the clock started at the waiver application for a waiver', () => {
    expect(
      durationSentence({ is_waiver: true }, '2026-06-01T12:00:00Z', '2026-07-01T12:00:00Z')
    ).toContain('from the waiver application.');
  });

  it('says nothing when either end of the range is missing', () => {
    expect(durationSentence(approved, null, '2026-07-01T12:00:00Z')).toBeNull();
    expect(durationSentence(approved, '2026-06-01T12:00:00Z', null)).toBeNull();
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
