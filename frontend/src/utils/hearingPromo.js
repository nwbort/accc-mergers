/**
 * The wording of a promo banner for a hearing that sits over several days,
 * as it stands at a given moment.
 *
 * A hearing is a list of sitting days (YYYY-MM-DD, in `timeZone`) that each
 * start at `startTime` and rise at `endTime` (HH:MM, 24-hour). The banner
 * walks through the run:
 *
 *   before day 1             "… begins on Monday at 10:15am"
 *   day 1, before start      "… begins today at 10:15am"
 *   day 1, sitting           "… has commenced"
 *   later day, before start  "… continues today at 10:15am"
 *   later day, sitting       "… has resumed"
 *   after a day rises, or on a non-sitting day in the run
 *                            "… continues tomorrow at 10:15am"
 *                            "… continues on Monday at 10:15am"
 *   after the last day rises null (the banner disappears)
 *
 * The clock is read in `timeZone`, never the reader's own zone, so a reader in
 * Perth sees the same banner as one in Sydney.
 */

const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

// `now`'s calendar date (YYYY-MM-DD) and minutes past midnight in `timeZone`.
function localParts(now, timeZone) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-AU', {
      timeZone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    })
      .formatToParts(now)
      .map(({ type, value }) => [type, value]),
  );
  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    minutes: Number(parts.hour) * 60 + Number(parts.minute),
  };
}

// `now`'s calendar date (YYYY-MM-DD) in `timeZone`.
export function localDate(now, timeZone) {
  return localParts(now, timeZone).date;
}

function toMinutes(hhmm) {
  const [h, m] = hhmm.split(':').map(Number);
  return h * 60 + m;
}

// Calendar arithmetic on YYYY-MM-DD strings, done in UTC so no zone shifts it.
function parseDate(ymd) {
  const [y, m, d] = ymd.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

function daysBetween(fromYmd, toYmd) {
  return Math.round((parseDate(toYmd) - parseDate(fromYmd)) / 86_400_000);
}

// "10:15am", "2pm".
export function formatClock(hhmm) {
  const [h, m] = hhmm.split(':').map(Number);
  const hour12 = h % 12 === 0 ? 12 : h % 12;
  const suffix = h < 12 ? 'am' : 'pm';
  return m === 0 ? `${hour12}${suffix}` : `${hour12}:${String(m).padStart(2, '0')}${suffix}`;
}

// How a future sitting day reads from `today`: "today", "tomorrow", "on
// Monday" within the coming week, "on Monday 9 November" further out.
function relativeDay(today, ymd) {
  const gap = daysBetween(today, ymd);
  if (gap === 0) return 'today';
  if (gap === 1) return 'tomorrow';
  const date = parseDate(ymd);
  const weekday = WEEKDAYS[date.getUTCDay()];
  if (gap < 7) return `on ${weekday}`;
  return `on ${weekday} ${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]}`;
}

/**
 * The banner title for `hearing` at `now`, or null once it has finished.
 *
 * `hearing` is `{ subject, sittingDays, startTime, endTime, timeZone }`;
 * `subject` is the start of the sentence ("Coles Kalgoorlie tribunal appeal
 * hearing").
 */
export function hearingPromoTitle(hearing, now) {
  const { subject, startTime, endTime, timeZone } = hearing;
  const sittingDays = [...hearing.sittingDays].sort();
  const { date: today, minutes } = localParts(now, timeZone);
  const start = toMinutes(startTime);
  const end = toMinutes(endTime);
  const at = formatClock(startTime);

  const todayIndex = sittingDays.indexOf(today);
  if (todayIndex !== -1) {
    const first = todayIndex === 0;
    if (minutes < start) {
      return `${subject} ${first ? 'begins' : 'continues'} today at ${at}`;
    }
    if (minutes < end) {
      return `${subject} ${first ? 'has commenced' : 'has resumed'}`;
    }
  }

  // Not sitting right now: point at the next sitting day, if there is one.
  const next = sittingDays.find((day) => day > today);
  if (!next) return null;
  const verb = today < sittingDays[0] ? 'begins' : 'continues';
  return `${subject} ${verb} ${relativeDay(today, next)} at ${at}`;
}
