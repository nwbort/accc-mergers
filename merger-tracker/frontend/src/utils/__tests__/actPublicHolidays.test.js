import { describe, expect, it } from 'vitest';
import actPublicHolidays from '../../data/act-public-holidays.json';

// Tripwire for spec 4 (issue #578): `isBusinessDay` silently treats any date
// beyond the calendar's covered years as a workday. This test fails loudly
// once the calendar's horizon shrinks to less than a year ahead of "today",
// so a maintainer refreshes act-public-holidays.json before the gap causes
// silently wrong business-day durations. A failure on a January CI run
// (i.e. the file covers less than a year further out) is deliberate and
// expected — it means it's time to add the next year's holidays.
describe('act-public-holidays.json horizon', () => {
  it('covers at least one year beyond the current year', () => {
    const latestYear = Math.max(
      ...actPublicHolidays.holidays.map((yearData) => yearData.year)
    );
    const currentYear = new Date().getFullYear();

    expect(latestYear).toBeGreaterThanOrEqual(currentYear + 1);
  });
});
