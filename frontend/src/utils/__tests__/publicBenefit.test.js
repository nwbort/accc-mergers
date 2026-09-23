import { describe, expect, it } from 'vitest';
import { isPublicBenefitStage } from '../../constants/mergerStatus';
import {
  determinationForEvent,
  getDeterminationDocUrl,
  getPublicBenefitQualifier,
} from '../mergerOutcome';

// MN-65005 once its parties applied for a public benefit determination: the
// pipeline clears the headline (the matter is live again) and keeps the
// Phase 2 outcome in phase_2_determination.
const applied = {
  status: 'Under assessment',
  stage: 'Public benefit phase',
  accc_determination: null,
  phase_2_determination: 'Not approved',
  phase_2_determination_date: '2026-09-22T12:00:00Z',
  public_benefit_in_progress: true,
};

const decided = {
  ...applied,
  status: 'Assessment completed',
  accc_determination: 'Approved',
  public_benefit_in_progress: undefined,
  public_benefits_determination: 'Approved',
  public_benefits_determination_date: '2026-12-14T12:00:00Z',
};

describe('isPublicBenefitStage', () => {
  it('matches the register label, whatever its case', () => {
    expect(isPublicBenefitStage('Public benefit phase')).toBe(true);
    expect(isPublicBenefitStage('Public Benefits Test')).toBe(true);
    expect(isPublicBenefitStage('Phase 2 - detailed assessment')).toBe(false);
    expect(isPublicBenefitStage(null)).toBe(false);
  });
});

describe('getPublicBenefitQualifier', () => {
  it('adds nothing while the application runs', () => {
    expect(getPublicBenefitQualifier(applied)).toBeNull();
  });

  it('says how a decided one was decided', () => {
    expect(getPublicBenefitQualifier(decided)).toBe('after public benefit review');
  });

  it('says nothing for any other matter', () => {
    expect(getPublicBenefitQualifier({ status: 'Under assessment' })).toBeNull();
  });
});

describe('determinationForEvent', () => {
  it('matches each determination event to its own phase by date', () => {
    expect(determinationForEvent(decided, { date: '2026-09-22T12:00:00Z' })).toBe('Not approved');
    expect(determinationForEvent(decided, { date: '2026-12-14T12:00:00Z' })).toBe('Approved');
  });

  it('keeps the Phase 2 outcome while the application runs', () => {
    expect(determinationForEvent(applied, { date: '2026-09-22T12:00:00Z' })).toBe('Not approved');
  });

  it('falls back to the headline determination', () => {
    expect(determinationForEvent({ accc_determination: 'Approved' }, { date: '2026-01-01' })).toBe('Approved');
  });
});

describe('getDeterminationDocUrl after a public benefit determination', () => {
  it('links the latest statement of reasons, not the Phase 2 one', () => {
    const merger = {
      ...decided,
      events: [
        { date: '2026-09-22T12:00:00Z', title: 'Phase 2 - Statement of reasons', url_gh: '/p2.pdf' },
        { date: '2026-12-14T12:00:00Z', title: 'Public benefit - Statement of reasons', url_gh: '/pb.pdf' },
      ],
    };
    expect(getDeterminationDocUrl(merger)).toBe('/pb.pdf');
  });
});
