import { describe, expect, it } from 'vitest';
import { formatClock, hearingPromoTitle } from '../hearingPromo';
import { COLES_KALGOORLIE_HEARING } from '../../constants/promo';

// Sydney is on AEDT (UTC+11) throughout November 2026.
function sydney(isoLocal) {
  return new Date(`${isoLocal}+11:00`);
}

const title = (isoLocal) => hearingPromoTitle(COLES_KALGOORLIE_HEARING, sydney(isoLocal));
const S = 'Coles Kalgoorlie tribunal appeal hearing';

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
    expect(hearingPromoTitle(COLES_KALGOORLIE_HEARING, new Date('2026-11-08T23:30:00Z'))).toBe(
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
