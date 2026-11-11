import { describe, expect, it } from 'vitest';
import { formatClock, hearingPromoTitle } from '../hearingPromo';
import {
  COLES_KALGOORLIE_HEARING_PROMO,
  FEDERAL_COURT_YOUTUBE_CHANNEL,
  livestreamLink,
} from '../../constants/promo';

// Sydney is on AEDT (UTC+11) throughout November 2026.
function sydney(isoLocal) {
  return new Date(`${isoLocal}+11:00`);
}

// A fixture of its own, so these pin the function rather than whatever the
// live campaign's schedule currently is.
const S = 'Coles Kalgoorlie tribunal appeal hearing';
const HEARING = {
  subject: S,
  sittingDays: [
    '2026-11-09', '2026-11-10', '2026-11-11', '2026-11-12',
    '2026-11-16', '2026-11-17', '2026-11-18', '2026-11-19',
  ],
  startTime: '10:15',
  endTime: '16:15',
  timeZone: 'Australia/Sydney',
};

const title = (isoLocal) => hearingPromoTitle(HEARING, sydney(isoLocal));

describe('hearingPromoTitle', () => {
  it.each([
    ['2026-11-01T12:00', `${S} begins on Monday 9 November at 10:15am`],
    ['2026-11-06T09:00', `${S} begins on Monday at 10:15am`],
    ['2026-11-08T20:00', `${S} begins tomorrow at 10:15am`],
    ['2026-11-09T08:00', `${S} begins today at 10:15am`],
    ['2026-11-09T10:14', `${S} begins today at 10:15am`],
    ['2026-11-09T10:15', `${S} has commenced`],
    ['2026-11-09T16:14', `${S} has commenced`],
    ['2026-11-09T16:15', `${S} continues tomorrow at 10:15am`],
    ['2026-11-09T23:59', `${S} continues tomorrow at 10:15am`],
    ['2026-11-10T00:00', `${S} continues today at 10:15am`],
    ['2026-11-10T11:00', `${S} has resumed`],
    ['2026-11-11T17:00', `${S} continues tomorrow at 10:15am`],
    ['2026-11-12T16:30', `${S} continues on Monday at 10:15am`],
    ['2026-11-13T12:00', `${S} continues on Monday at 10:15am`],
    ['2026-11-15T12:00', `${S} continues tomorrow at 10:15am`],
    ['2026-11-16T09:00', `${S} continues today at 10:15am`],
    ['2026-11-19T09:00', `${S} continues today at 10:15am`],
    ['2026-11-19T15:00', `${S} has resumed`],
  ])('at %s Sydney time', (when, expected) => {
    expect(title(when)).toBe(expected);
  });

  it('is gone once the last scheduled day rises', () => {
    expect(title('2026-11-19T16:15')).toBeNull();
    expect(title('2026-11-20T09:00')).toBeNull();
  });

  it('reads the clock in Sydney, whatever the instant is in UTC', () => {
    // 2026-11-08T23:30Z is 10:30am Monday in Sydney.
    expect(hearingPromoTitle(HEARING, new Date('2026-11-08T23:30:00Z'))).toBe(
      `${S} has commenced`,
    );
  });
});

describe('formatClock', () => {
  it.each([
    ['10:15', '10:15am'],
    ['09:05', '9:05am'],
    ['12:00', '12pm'],
    ['00:30', '12:30am'],
    ['16:15', '4:15pm'],
  ])('%s reads %s', (hhmm, expected) => {
    expect(formatClock(hhmm)).toBe(expected);
  });
});

describe('COLES_KALGOORLIE_HEARING_PROMO', () => {
  const at = (isoLocal) => COLES_KALGOORLIE_HEARING_PROMO.resolve(sydney(isoLocal));
  const L = 'The public livestream';

  it('keeps one headline while its subline follows the livestream', () => {
    expect(COLES_KALGOORLIE_HEARING_PROMO.title).toBe(
      'Coles Kalgoorlie Tribunal appeal hearing continues this week',
    );
  });

  it.each([
    // Tuesday 10 November sat in closed court: no livestream that day.
    ['2026-11-10T09:00', `${L} continues tomorrow at 10:15am.`],
    ['2026-11-10T11:00', `${L} continues tomorrow at 10:15am.`],
    ['2026-11-11T09:00', `${L} continues today at 10:15am.`],
    ['2026-11-11T11:00', `${L} has resumed.`],
    ['2026-11-12T17:00', `${L} continues on Monday at 10:15am.`],
    ['2026-11-19T15:00', `${L} has resumed.`],
  ])('at %s Sydney time', (when, expected) => {
    expect(at(when).description).toBe(expected);
  });

  it('links to the court channel when no link exists for the day', () => {
    expect(COLES_KALGOORLIE_HEARING_PROMO.href).toBe(FEDERAL_COURT_YOUTUBE_CHANNEL);
    expect(at('2026-11-10T09:00').href).toBe(FEDERAL_COURT_YOUTUBE_CHANNEL);
  });

  it('is gone once the last scheduled day rises', () => {
    expect(at('2026-11-19T16:15')).toBeNull();
  });
});

describe('livestreamLink', () => {
  const LINKS = { '2026-11-12': 'https://www.youtube.com/watch?v=day' };
  const tz = 'Australia/Sydney';

  it("uses the day's link, keyed by the Sydney date", () => {
    expect(livestreamLink(LINKS, sydney('2026-11-12T00:30'), tz)).toBe(LINKS['2026-11-12']);
    // 23:30 UTC on the 11th is already the 12th in Sydney.
    expect(livestreamLink(LINKS, new Date('2026-11-11T23:30Z'), tz)).toBe(LINKS['2026-11-12']);
  });

  it('falls back to the court channel on a day without one', () => {
    expect(livestreamLink(LINKS, sydney('2026-11-13T09:00'), tz)).toBe(FEDERAL_COURT_YOUTUBE_CHANNEL);
  });
});
