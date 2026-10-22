/**
 * Geometry for the merger list's date filter: the bars of its histogram and
 * the quick ranges above it.
 *
 * Everything here is a plain YYYY-MM-DD string, compared as strings. Register
 * dates are Australian calendar days stored at a nominal midday UTC, so the
 * first ten characters are the day itself; arithmetic happens in UTC, where no
 * daylight-saving shift can move a date across midnight.
 */

const DAY_MS = 24 * 60 * 60 * 1000;

// Weekly bars until the span would make them too thin to read or hit, then
// monthly. 78 weeks is a year and a half.
const MAX_WEEKLY_BARS = 78;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

const toMs = (iso) => Date.parse(`${iso}T00:00:00Z`);
const toIso = (ms) => new Date(ms).toISOString().slice(0, 10);
const addDays = (iso, days) => toIso(toMs(iso) + days * DAY_MS);
const lastDayOfMonth = (y, m) => new Date(Date.UTC(y, m, 0)).getUTCDate();
const pad = (n) => String(n).padStart(2, '0');

/** Whether `value` is a usable YYYY-MM-DD string. */
// A round trip rather than a parse check: Date.parse rolls 30 February over
// to 2 March instead of rejecting it.
export const isIsoDate = (value) => (
  typeof value === 'string' && ISO_DATE.test(value) && !Number.isNaN(toMs(value)) && toIso(toMs(value)) === value
);

/** The day part of a stored register datetime, or null. */
export const dayOf = (datetime) => (datetime ? datetime.slice(0, 10) : null);

/** The calendar months from `first` to `last` inclusive, each with its first and last day. */
export function monthsBetween(first, last) {
  const months = [];
  let [y, m] = first.split('-').map(Number);
  const [y1, m1] = last.split('-').map(Number);
  while (y < y1 || (y === y1 && m <= m1)) {
    months.push({ from: `${y}-${pad(m)}-01`, to: `${y}-${pad(m)}-${pad(lastDayOfMonth(y, m))}` });
    if (m === 12) { y += 1; m = 1; } else { m += 1; }
  }
  return months;
}

/**
 * The histogram's bars, from `first` to `today`: weeks starting on Mondays,
 * or calendar months once the span is too long for weekly bars to read.
 */
export function buildTimeline(first, today) {
  const mondayOffset = (new Date(toMs(first)).getUTCDay() + 6) % 7;
  const start = addDays(first, -mondayOffset);
  const weekCount = Math.floor((toMs(today) - toMs(start)) / (7 * DAY_MS)) + 1;
  if (weekCount <= MAX_WEEKLY_BARS) {
    const bars = Array.from({ length: weekCount }, (_, i) => {
      const from = addDays(start, i * 7);
      return { from, to: addDays(from, 6) };
    });
    return { unit: 'week', bars };
  }
  return { unit: 'month', bars: monthsBetween(first, today) };
}

/**
 * The quick ranges, all ending today: the last 30 and 90 days, this calendar
 * year so far, and last year whole when the data reaches back that far.
 */
export function quickRanges(first, today) {
  const year = Number(today.slice(0, 4));
  const ranges = [
    { key: '30d', label: 'Last 30 days', from: addDays(today, -29), to: today },
    { key: '90d', label: 'Last 90 days', from: addDays(today, -89), to: today },
    { key: 'this-year', label: 'This year', from: `${year}-01-01`, to: today },
  ];
  if (first <= `${year - 1}-12-31`) {
    ranges.push({ key: 'last-year', label: String(year - 1), from: `${year - 1}-01-01`, to: `${year - 1}-12-31` });
  }
  return ranges;
}

/** Whether the inclusive ranges [aFrom, aTo] and [bFrom, bTo] share a day. */
export const overlaps = (aFrom, aTo, bFrom, bTo) => aFrom <= bTo && bFrom <= aTo;
