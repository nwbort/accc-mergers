import { describe, expect, it } from 'vitest';
import {
  extensionReason,
  getTimelineExtensions,
  isExtensionTitle,
} from '../timelineExtensions';

describe('isExtensionTitle', () => {
  it('matches both the standard and the earliest long-form notice', () => {
    expect(isExtensionTitle('Timeline extended by 6 business days – following request by parties')).toBe(true);
    expect(isExtensionTitle('ACCC decided to extend the Phase 1 determination period following receipt of extension request')).toBe(true);
    expect(isExtensionTitle('Merger notified to ACCC')).toBe(false);
    expect(isExtensionTitle(undefined)).toBe(false);
  });
});

describe('extensionReason', () => {
  it('returns the "following" clause, tidied', () => {
    expect(extensionReason('Timeline extended by 6 business days – following  request for further information.'))
      .toBe('request for further information');
    expect(extensionReason('Timeline extended by 6 business days')).toBe('');
  });
});

describe('getTimelineExtensions', () => {
  it('stacks phase 1 extensions after the 30-business-day window, matching the register deadline', () => {
    // MN-90008: three phase 1 extensions; the register's deadline is 17 Aug 2026.
    const result = getTimelineExtensions({
      effective_notification_datetime: '2026-05-21T12:00:00Z',
      end_of_determination_period: '2026-08-17T12:00:00Z',
      phase_1_determination_date: '2026-08-11T12:00:00Z',
      events: [
        { date: '2026-07-10T12:00:00Z', title: 'Timeline extended by 15 business days - following remedy offered by parties' },
        { date: '2026-06-19T12:00:00Z', title: 'Timeline extended by 10 business days - following request by parties' },
        { date: '2026-07-03T12:00:00Z', title: 'Timeline extended by 5 business days - following request by parties' },
        { date: '2026-05-21T12:00:00Z', title: 'Merger notified to ACCC' },
      ],
    });

    expect(result.map((e) => e.businessDays)).toEqual([10, 5, 15]);
    expect(result.every((e) => e.phase === 1)).toBe(true);
    expect(result[0].from).toBe('2026-07-06');
    expect(result[0].to).toBe(result[1].from);
    expect(result[1].to).toBe(result[2].from);
    expect(result[2].to).toBe('2026-08-17');
    expect(result[2].reason).toBe('remedy offered by parties');
  });

  it('anchors phase 2 extensions 90 business days on from the extended phase 1 deadline', () => {
    // MN-05013: one phase 1 extension, two phase 2 extensions the same day.
    const result = getTimelineExtensions({
      effective_notification_datetime: '2026-05-12T12:00:00Z',
      end_of_determination_period: '2026-12-17T12:00:00Z',
      phase_1_determination: 'Referred to phase 2',
      phase_1_determination_date: '2026-07-17T12:00:00Z',
      stage: 'Phase 2 - detailed assessment',
      events: [
        { date: '2026-06-15T12:00:00Z', title: 'Timeline extended by 20 business days – following request by notifying party' },
        { date: '2026-10-12T12:00:00Z', title: 'Timeline extended by 5 business days – following request by parties' },
        { date: '2026-10-12T12:00:00Z', title: 'Timeline extended by 9 business days – following request for further information' },
      ],
    });

    expect(result.map((e) => [e.phase, e.businessDays])).toEqual([[1, 20], [2, 5], [2, 9]]);
    expect(result[0].to).toBe('2026-07-23');
    expect(result[2].to).toBe('2026-12-17');
  });

  it('places nothing when a day count is missing', () => {
    expect(getTimelineExtensions({
      effective_notification_datetime: '2025-10-10T12:00:00Z',
      events: [{ date: '2025-11-06T12:00:00Z', title: 'ACCC decided to extend the Phase 1 determination period following receipt of extension request' }],
    })).toEqual([]);
  });

  it('skips extensions granted after the phase 2 determination', () => {
    expect(getTimelineExtensions({
      effective_notification_datetime: '2026-03-03T12:00:00Z',
      phase_1_determination: 'Referred to phase 2',
      phase_1_determination_date: '2026-04-16T12:00:00Z',
      phase_2_determination_date: '2026-09-23T12:00:00Z',
      events: [{ date: '2026-10-01T12:00:00Z', title: 'Timeline extended by 10 business days' }],
    })).toEqual([]);
  });

  it('returns nothing for waivers or matters without extensions', () => {
    expect(getTimelineExtensions({ effective_notification_datetime: '2026-05-21T12:00:00Z', events: [] })).toEqual([]);
    expect(getTimelineExtensions({ is_waiver: true, effective_notification_datetime: '2026-05-21T12:00:00Z' })).toEqual([]);
  });
});
