import { describe, expect, it } from 'vitest';
import {
  getPreNotificationConfidence,
  getPreNotificationEstimate,
  getPreNotificationWindowDays,
  HIGH_CONFIDENCE_WINDOW_DAYS,
  MEDIUM_CONFIDENCE_WINDOW_DAYS,
  PRE_NOTIFICATION_CONFIDENCE,
} from '../preNotification';

const bracketed = (minDays, maxDays) => ({
  estimated_days: minDays,
  min_days: minDays,
  max_days: maxDays,
  id_issued_estimated: '2026-05-07',
  basis: 'bracketed',
});

describe('getPreNotificationWindowDays', () => {
  it('measures the gap between the proven floor and the generous ceiling', () => {
    expect(getPreNotificationWindowDays(bracketed(12, 34))).toBe(22);
  });

  it('has no width to give when only one side is dated', () => {
    expect(getPreNotificationWindowDays({ min_days: 7, max_days: null })).toBeNull();
    expect(getPreNotificationWindowDays({ min_days: null, max_days: 40 })).toBeNull();
    expect(getPreNotificationWindowDays(undefined)).toBeNull();
  });
});

describe('getPreNotificationConfidence', () => {
  it('rates a bracket by its width, inclusive of each threshold', () => {
    const { LOW, MEDIUM, HIGH } = PRE_NOTIFICATION_CONFIDENCE;
    expect(getPreNotificationConfidence(bracketed(0, HIGH_CONFIDENCE_WINDOW_DAYS))).toBe(HIGH);
    expect(getPreNotificationConfidence(bracketed(0, HIGH_CONFIDENCE_WINDOW_DAYS + 1))).toBe(MEDIUM);
    expect(getPreNotificationConfidence(bracketed(0, MEDIUM_CONFIDENCE_WINDOW_DAYS))).toBe(MEDIUM);
    expect(getPreNotificationConfidence(bracketed(0, MEDIUM_CONFIDENCE_WINDOW_DAYS + 1))).toBe(LOW);
  });

  it('never rates a single-bound estimate above low, however narrow it looks', () => {
    expect(getPreNotificationConfidence({
      min_days: 2,
      max_days: null,
      basis: 'lower-bound-only',
    })).toBe(PRE_NOTIFICATION_CONFIDENCE.LOW);
    expect(getPreNotificationConfidence({
      min_days: null,
      max_days: 2,
      basis: 'upper-bound-only',
    })).toBe(PRE_NOTIFICATION_CONFIDENCE.LOW);
  });
});

describe('getPreNotificationEstimate', () => {
  const merger = (estimate) => ({
    merger_id: 'MN-01050',
    original_notification_datetime: '2026-05-27T12:00:00Z',
    effective_notification_datetime: '2026-05-27T12:00:00Z',
    pre_notification: estimate,
  });

  it('carries the rating and the window through with the dated estimate', () => {
    expect(getPreNotificationEstimate(merger(bracketed(12, 34)))).toMatchObject({
      confidence: PRE_NOTIFICATION_CONFIDENCE.MEDIUM,
      windowDays: 22,
    });
  });

  it('rates a nought-day estimate too, where there is no date to rate', () => {
    expect(getPreNotificationEstimate(merger({ ...bracketed(0, 4), estimated_days: 0 })))
      .toMatchObject({
        startDate: null,
        confidence: PRE_NOTIFICATION_CONFIDENCE.HIGH,
        windowDays: 4,
      });
  });
});
