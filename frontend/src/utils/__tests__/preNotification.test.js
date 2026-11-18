/* global process */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  getPreNotificationConfidence,
  getPreNotificationEstimate,
  getPreNotificationWindowDays,
  HIGH_CONFIDENCE_WINDOW_DAYS,
  MEDIUM_CONFIDENCE_WINDOW_DAYS,
  PRE_NOTIFICATION_CONFIDENCE,
} from '../preNotification';

const repoRoot = resolve(process.cwd(), '..');

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

// fixtures/pre-notification-summary-cases.json pins this rule to its Python
// copy in scripts/generate/static_data/outputs/api.py, which publishes the
// same condensed estimate through the key-gated API (docs/api.md).
describe('getPreNotificationEstimate against the shared fixture', () => {
  const fixture = JSON.parse(
    readFileSync(resolve(repoRoot, 'fixtures', 'pre-notification-summary-cases.json'), 'utf8'),
  );

  it('has cases', () => {
    expect(fixture.cases.length).toBeGreaterThan(0);
  });

  it.each(fixture.cases.map((c) => [c.name, c]))('%s', (_name, { merger, expected }) => {
    const result = getPreNotificationEstimate(merger);
    expect(
      result && { kind: result.kind, start_date: result.startDate, confidence: result.confidence },
    ).toEqual(expected);
  });
});
