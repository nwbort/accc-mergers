import { describe, expect, it } from 'vitest';
import { sortEventsNewestFirst } from '../eventOrder';

const NOTIFIED = { date: '2026-10-02T12:00:00Z', title: 'Merger notified to ACCC' };
const QUESTIONNAIRE = { date: '2026-10-02T12:00:00Z', title: 'Phase 1 Questionnaire' };
const LATER = { date: '2026-10-09T12:00:00Z', title: 'Consultation closes' };

describe('sortEventsNewestFirst', () => {
  it('sorts by date, newest first', () => {
    const titles = sortEventsNewestFirst([NOTIFIED, LATER]).map((e) => e.title);
    expect(titles).toEqual([LATER.title, NOTIFIED.title]);
  });

  it('puts the notification below a same-day event whichever order they were stored in', () => {
    // MN-10032: the new consultation format stores the questionnaire after
    // the notification, where the old format stored it before.
    for (const events of [[NOTIFIED, QUESTIONNAIRE], [QUESTIONNAIRE, NOTIFIED]]) {
      expect(sortEventsNewestFirst(events).map((e) => e.title))
        .toEqual([QUESTIONNAIRE.title, NOTIFIED.title]);
    }
  });

  it('keeps the stored order for other same-day events', () => {
    const a = { ...QUESTIONNAIRE, title: 'A' };
    const b = { ...QUESTIONNAIRE, title: 'B' };
    expect(sortEventsNewestFirst([a, b])).toEqual([a, b]);
    expect(sortEventsNewestFirst([b, a])).toEqual([b, a]);
  });

  it('returns an empty list for a merger with no events', () => {
    expect(sortEventsNewestFirst(undefined)).toEqual([]);
  });
});
