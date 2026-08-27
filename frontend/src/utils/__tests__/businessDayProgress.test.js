import { afterEach, describe, expect, it, vi } from 'vitest';
import { getBusinessDayProgress } from '../businessDayProgress';

describe('getBusinessDayProgress', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('counts today once it is a business day, regardless of the current clock time', () => {
    // Regression test: notified Friday 3 Jul 2026 (noon UTC); "now" is Monday
    // 6 Jul 2026 at 05:21 UTC — well before noon. Comparing the raw current
    // instant against day-by-day increments carried at the notification's
    // noon time-of-day used to undercount today (elapsed 0 instead of 1).
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-07-06T05:21:00Z'));

    const progress = getBusinessDayProgress({
      status: 'Under assessment',
      effective_notification_datetime: '2026-07-03T12:00:00Z',
      end_of_determination_period: '2026-08-14T12:00:00Z',
    });

    expect(progress.elapsed).toBe(1);
    expect(progress.total).toBe(30);
    expect(progress.overdue).toBe(false);
  });

  it('reports day 0 when notified today', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-01T09:00:00Z'));

    const progress = getBusinessDayProgress({
      status: 'Under assessment',
      effective_notification_datetime: '2026-06-01T12:00:00Z',
      end_of_determination_period: '2026-07-15T12:00:00Z',
    });

    expect(progress.elapsed).toBe(0);
  });

  it('clamps elapsed at the total and flags overdue once past the end date', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-01T00:00:00Z'));

    const progress = getBusinessDayProgress({
      status: 'Under assessment',
      effective_notification_datetime: '2026-03-01T12:00:00Z',
      end_of_determination_period: '2026-05-01T12:00:00Z',
    });

    expect(progress.elapsed).toBe(progress.total);
    expect(progress.overdue).toBe(true);
  });

  it('returns null for a waiver', () => {
    expect(
      getBusinessDayProgress({
        is_waiver: true,
        status: 'Under assessment',
        effective_notification_datetime: '2026-05-18T12:00:00Z',
        end_of_determination_period: '2026-07-01T12:00:00Z',
      })
    ).toBeNull();
  });

  it('returns null once the assessment is complete', () => {
    expect(
      getBusinessDayProgress({
        status: 'Assessment completed',
        effective_notification_datetime: '2026-05-18T12:00:00Z',
        end_of_determination_period: '2026-07-01T12:00:00Z',
        determination_publication_date: '2026-06-10T12:00:00Z',
      })
    ).toBeNull();
  });

  it('returns null when the end-of-determination period is missing', () => {
    expect(
      getBusinessDayProgress({
        status: 'Under assessment',
        effective_notification_datetime: '2026-05-18T12:00:00Z',
        end_of_determination_period: null,
      })
    ).toBeNull();
  });
});
