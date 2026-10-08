import { describe, expect, it } from 'vitest';
import {
  DEFAULT_SORT,
  SORT_FIELDS,
  SORT_FIELDS_BY_VALUE,
  normaliseSort,
  splitSort,
  sortMergers,
} from '../mergerSort';

const merger = (merger_name, overrides = {}) => ({
  merger_name,
  effective_notification_datetime: '2025-01-01T12:00:00Z',
  determination_publication_date: '2025-02-01T12:00:00Z',
  latest_event_date: '2025-01-01T12:00:00Z',
  ...overrides,
});

const names = (list) => list.map((m) => m.merger_name);

describe('sortMergers by name', () => {
  it('orders A to Z on name-asc', () => {
    const list = [merger('Zephyr – Alpha'), merger('Acme – Beta'), merger('Mango – Gamma')];
    expect(names(sortMergers(list, 'name-asc'))).toEqual([
      'Acme – Beta',
      'Mango – Gamma',
      'Zephyr – Alpha',
    ]);
  });

  it('orders Z to A on name-desc', () => {
    const list = [merger('Acme – Beta'), merger('Zephyr – Alpha'), merger('Mango – Gamma')];
    expect(names(sortMergers(list, 'name-desc'))).toEqual([
      'Zephyr – Alpha',
      'Mango – Gamma',
      'Acme – Beta',
    ]);
  });

  it('ignores case, so a lowercase name is not exiled to the end', () => {
    const list = [merger('Bravo Ltd'), merger('alpha Pty Ltd'), merger('Charlie Ltd')];
    expect(names(sortMergers(list, 'name-asc'))).toEqual([
      'alpha Pty Ltd',
      'Bravo Ltd',
      'Charlie Ltd',
    ]);
  });

  it('does not mutate the list it is given', () => {
    const list = [merger('Zephyr'), merger('Acme')];
    sortMergers(list, 'name-asc');
    expect(names(list)).toEqual(['Zephyr', 'Acme']);
  });

  it('tolerates a missing name', () => {
    const list = [merger('Bravo'), merger(undefined), merger('Acme')];
    expect(names(sortMergers(list, 'name-asc'))).toEqual([undefined, 'Acme', 'Bravo']);
  });
});

describe('sortMergers by date', () => {
  it('still defaults to most recently updated first', () => {
    const list = [
      merger('Older', { latest_event_date: '2024-03-01T12:00:00Z' }),
      merger('Newer', { latest_event_date: '2025-06-01T12:00:00Z' }),
    ];
    expect(names(sortMergers(list))).toEqual(['Newer', 'Older']);
  });

  it('sorts explicitly by notification date, independent of the default', () => {
    const list = [
      merger('Older', { effective_notification_datetime: '2024-03-01T12:00:00Z' }),
      merger('Newer', { effective_notification_datetime: '2025-06-01T12:00:00Z' }),
    ];
    expect(names(sortMergers(list, 'notification-desc'))).toEqual(['Newer', 'Older']);
  });

  it('keeps undetermined mergers last whichever way determination sorts', () => {
    const list = [
      merger('Undecided', { determination_publication_date: null }),
      merger('Decided', { determination_publication_date: '2025-02-01T12:00:00Z' }),
    ];
    expect(names(sortMergers(list, 'determination-asc'))).toEqual(['Decided', 'Undecided']);
    expect(names(sortMergers(list, 'determination-desc'))).toEqual(['Decided', 'Undecided']);
  });

  it('keeps mergers with no event history last whichever way "modified" sorts', () => {
    const list = [
      merger('NoHistory', { latest_event_date: null }),
      merger('HasHistory', { latest_event_date: '2025-02-01T12:00:00Z' }),
    ];
    expect(names(sortMergers(list, 'modified-asc'))).toEqual(['HasHistory', 'NoHistory']);
    expect(names(sortMergers(list, 'modified-desc'))).toEqual(['HasHistory', 'NoHistory']);
  });
});

describe('normaliseSort', () => {
  it('keeps every field the select offers, in both directions', () => {
    SORT_FIELDS.forEach(({ value }) => {
      expect(normaliseSort(`${value}-asc`)).toBe(`${value}-asc`);
      expect(normaliseSort(`${value}-desc`)).toBe(`${value}-desc`);
    });
  });

  it('folds an unknown or empty ?sort= back to the default', () => {
    expect(normaliseSort('bogus-asc')).toBe(DEFAULT_SORT);
    expect(normaliseSort('name-sideways')).toBe(DEFAULT_SORT);
    expect(normaliseSort('')).toBe(DEFAULT_SORT);
    expect(normaliseSort(null)).toBe(DEFAULT_SORT);
  });
});

describe('splitSort', () => {
  it('splits a sort value into field and direction', () => {
    expect(splitSort('name-asc')).toEqual({ field: 'name', dir: 'asc' });
    expect(splitSort(DEFAULT_SORT)).toEqual({ field: 'modified', dir: 'desc' });
  });
});

describe('SORT_FIELDS', () => {
  it('gives the name sort a natural A to Z starting direction', () => {
    expect(SORT_FIELDS_BY_VALUE.name).toMatchObject({
      defaultDir: 'asc',
      asc: 'A to Z',
      desc: 'Z to A',
    });
  });

  it('gives every offered field a direction sortMergers implements', () => {
    // A field with no case of its own falls through to the notification-desc
    // default in both directions, so the select would offer an order it never
    // applies. Two records that differ on every field must therefore come back
    // in opposite orders for each field the select lists.
    const list = [
      merger('Bravo', {
        effective_notification_datetime: '2024-01-01T12:00:00Z',
        determination_publication_date: '2024-02-01T12:00:00Z',
        latest_event_date: '2024-03-01T12:00:00Z',
      }),
      merger('Alpha', {
        effective_notification_datetime: '2025-01-01T12:00:00Z',
        determination_publication_date: '2025-02-01T12:00:00Z',
        latest_event_date: '2025-03-01T12:00:00Z',
      }),
    ];
    SORT_FIELDS.forEach(({ value, defaultDir }) => {
      expect(['asc', 'desc']).toContain(defaultDir);
      const asc = names(sortMergers(list, `${value}-asc`));
      expect(names(sortMergers(list, `${value}-desc`))).toEqual([...asc].reverse());
    });
  });
  describe('same-day ties on "modified"', () => {
    // Every event is stamped midday, so these all tie on latest_event_date.
    const day = '2026-10-01T12:00:00Z';
    const list = [
      merger('Morning', { latest_event_date: day, page_modified_datetime: '2026-10-01T09:25:06+10:00' }),
      merger('Evening', { latest_event_date: day, page_modified_datetime: '2026-10-01T17:43:53+10:00' }),
      merger('Midday', { latest_event_date: day, page_modified_datetime: '2026-10-01T13:45:06+10:00' }),
    ];

    it('orders by the register page modified time, newest first', () => {
      expect(names(sortMergers(list, 'modified-desc'))).toEqual(['Evening', 'Midday', 'Morning']);
    });

    it('reverses the whole order, ties included, for oldest first', () => {
      expect(names(sortMergers(list, 'modified-asc'))).toEqual(['Morning', 'Midday', 'Evening']);
    });

    it('compares instants, not strings, across a daylight-saving offset change', () => {
      // 23:30+10:00 on 4 Oct is 13:30Z; 00:00+11:00 on 5 Oct is 13:00Z. The
      // second string sorts higher, but the first is the later instant.
      const dst = [
        merger('Earlier', { latest_event_date: day, page_modified_datetime: '2026-10-05T00:00:00+11:00' }),
        merger('Later', { latest_event_date: day, page_modified_datetime: '2026-10-04T23:30:00+10:00' }),
      ];
      expect(names(sortMergers(dst, 'modified-desc'))).toEqual(['Later', 'Earlier']);
    });

    it('never lets page modified time outrank a later event date', () => {
      const old = merger('OldEventEditedLate', {
        latest_event_date: '2026-09-01T12:00:00Z',
        page_modified_datetime: '2026-10-02T09:00:00+10:00',
      });
      expect(names(sortMergers([old, ...list], 'modified-desc'))[3]).toBe('OldEventEditedLate');
    });
  });
});
