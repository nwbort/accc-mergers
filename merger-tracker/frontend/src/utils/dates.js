import { format, parseISO, differenceInDays, differenceInCalendarDays, addDays, getDay, isValid } from 'date-fns';
import actPublicHolidays from '../data/act-public-holidays.json';

// Build a Set of public holiday dates for fast lookup
const publicHolidaySet = new Set();
actPublicHolidays.holidays.forEach(yearData => {
  yearData.dates.forEach(holiday => {
    publicHolidaySet.add(holiday.date);
  });
});

/**
 * Parse the calendar-date portion of an ISO string into a Date anchored at
 * local midnight.
 *
 * ACCC register dates are effectively date-only values encoded at noon UTC
 * (e.g. "2026-07-17T12:00:00Z"). Parsing that instant with parseISO and then
 * comparing or formatting it in the viewer's local timezone shifts the day for
 * anyone far enough east of Australia — for a viewer in New Zealand (UTC+12)
 * noon UTC falls at midnight, so 17 July becomes 18 July. We only ever care
 * about the calendar day the ACCC published, so read the YYYY-MM-DD prefix
 * directly and ignore the time/zone. Both display formatting and countdown
 * maths go through this so a target date and "today" are compared on the same
 * local-calendar footing.
 * @param {string} dateString - Date in ISO format
 * @returns {Date} A local Date for the calendar day, or an Invalid Date
 */
export const parseDateOnly = (dateString) => {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(dateString);
  if (match) {
    return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  }
  // Fall back to full ISO parsing for any unexpected format.
  return parseISO(dateString);
};

/**
 * Serialise a Date to a plain YYYY-MM-DD string using its local calendar day.
 *
 * The counterpart to parseDateOnly: use this instead of Date.toISOString()
 * (which serialises in UTC and would shift the day back for viewers east of
 * Australia) when a derived Date needs to travel as a date-only string.
 * @param {Date} date - A Date object
 * @returns {string|null} The YYYY-MM-DD string, or null if the date is invalid
 */
export const toDateString = (date) => {
  if (!(date instanceof Date) || !isValid(date)) return null;
  return format(date, 'yyyy-MM-dd');
};

// The ACCC works to the Canberra (ACT) calendar. Register dates are Australian
// calendar days, so countdowns are measured against "today" in Australia rather
// than the viewer's timezone — that way a viewer in New Zealand sees the same
// days-remaining as one in Sydney, consistent with the identical dates shown.
const AUSTRALIA_TIMEZONE = 'Australia/Sydney';

/**
 * The current date in the ACCC's timezone, as a Date anchored at local midnight
 * so it compares cleanly against parseDateOnly values.
 * @returns {Date} Today's Australian calendar day
 */
export const australianToday = () => {
  // en-CA formats as YYYY-MM-DD; Intl handles AEST/AEDT (incl. DST) for us.
  const dateString = new Intl.DateTimeFormat('en-CA', {
    timeZone: AUSTRALIA_TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
  return parseDateOnly(dateString);
};

/**
 * Check if a date falls in the Christmas/New Year period (23 Dec - 10 Jan)
 * As per ACCC Act: days occurring between 23 December and 10 January are not business days
 */
const isChristmasNewYearPeriod = (date) => {
  const month = date.getMonth(); // 0-11
  const day = date.getDate();

  // December 23-31
  if (month === 11 && day >= 23) return true;

  // January 1-10
  if (month === 0 && day <= 10) return true;

  return false;
};

/**
 * Check if a date is a business day according to ACCC Act
 * Business day excludes:
 * - Saturdays (day 6)
 * - Sundays (day 0)
 * - ACT public holidays
 * - Days between 23 December and 10 January (inclusive)
 */
export const isBusinessDay = (date) => {
  const dayOfWeek = getDay(date);

  // Saturday or Sunday
  if (dayOfWeek === 0 || dayOfWeek === 6) return false;

  // Christmas/New Year period (23 Dec - 10 Jan)
  if (isChristmasNewYearPeriod(date)) return false;

  // Check if it's a public holiday
  const dateString = format(date, 'yyyy-MM-dd');
  if (publicHolidaySet.has(dateString)) return false;

  return true;
};

/**
 * Calculate the number of business days between two dates
 * @param {Date|string} startDate - Start date
 * @param {Date|string} endDate - End date
 * @returns {number} Number of business days
 */
export const calculateBusinessDays = (startDate, endDate) => {
  if (!startDate || !endDate) return null;

  try {
    const start = typeof startDate === 'string' ? parseDateOnly(startDate) : startDate;
    const end = typeof endDate === 'string' ? parseDateOnly(endDate) : endDate;

    if (!isValid(start) || !isValid(end)) return null;

    let businessDays = 0;
    // Start from the day after start — application date is day 0
    let currentDate = addDays(new Date(start), 1);

    while (currentDate <= end) {
      if (isBusinessDay(currentDate)) {
        businessDays++;
      }
      currentDate = addDays(currentDate, 1);
    }

    return businessDays;
  } catch {
    return null;
  }
};

/**
 * Get the number of business days remaining until a date
 * @param {string} endDate - End date in ISO format
 * @returns {number} Number of business days remaining (0 if date has passed)
 */
export const getBusinessDaysRemaining = (endDate) => {
  if (!endDate) return null;
  try {
    const end = parseDateOnly(endDate);
    if (!isValid(end)) return null;
    const today = australianToday();

    if (end <= today) return 0;

    return calculateBusinessDays(today, end);
  } catch {
    return null;
  }
};

/**
 * Add a number of business days to a date (ACCC business-day definition).
 * The start date is day 0, mirroring calculateBusinessDays.
 * @param {Date|string} startDate - Start date
 * @param {number} count - Number of business days to add
 * @returns {Date|null} The resulting date, or null if inputs are invalid
 */
export const addBusinessDays = (startDate, count) => {
  if (!startDate || count == null) return null;

  try {
    const start = typeof startDate === 'string' ? parseDateOnly(startDate) : startDate;
    if (!isValid(start)) return null;

    let added = 0;
    let currentDate = new Date(start);

    while (added < count) {
      currentDate = addDays(currentDate, 1);
      if (isBusinessDay(currentDate)) {
        added++;
      }
    }

    return currentDate;
  } catch {
    return null;
  }
};

export const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    return format(parseDateOnly(dateString), 'dd/MM/yyyy');
  } catch {
    return 'Invalid date';
  }
};

/**
 * Format a date as "DD Mmm Yyyy" (e.g. 18 May 2026).
 * @param {string} dateString - Date in ISO format
 * @returns {string} The formatted date
 */
export const formatDateMedium = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    return format(parseDateOnly(dateString), 'dd MMM yyyy');
  } catch {
    return 'Invalid date';
  }
};

/**
 * Format a date as "D Month Yyyy" with the full month name (e.g. 15 July 2026).
 * @param {string} dateString - Date in ISO format
 * @returns {string} The formatted date
 */
export const formatDateLong = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    return format(parseDateOnly(dateString), 'd MMMM yyyy');
  } catch {
    return 'Invalid date';
  }
};

/**
 * Format a date as a short weekday + day + month for agenda views
 * (e.g. "Mon 29 Jun").
 * @param {string} dateString - Date in ISO format
 * @returns {string} The formatted day
 */
export const formatWeekday = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    return format(parseDateOnly(dateString), 'EEE d MMM');
  } catch {
    return 'Invalid date';
  }
};

/**
 * Format a date range as day + month for each end (e.g. "2 Sep – 7 Sep"),
 * for agenda views that bundle several days under one heading.
 * @param {string} startDate - Start date in ISO format
 * @param {string} endDate - End date in ISO format
 * @returns {string} The formatted range
 */
export const formatDateRange = (startDate, endDate) => {
  if (!startDate || !endDate) return 'N/A';
  try {
    const start = parseDateOnly(startDate);
    const end = parseDateOnly(endDate);
    if (!isValid(start) || !isValid(end)) return 'Invalid date';
    return `${format(start, 'd MMM')} – ${format(end, 'd MMM')}`;
  } catch {
    return 'Invalid date';
  }
};

export const calculateDuration = (startDate, endDate) => {
  if (!startDate || !endDate) return null;
  try {
    const start = parseDateOnly(startDate);
    const end = parseDateOnly(endDate);
    if (!isValid(start) || !isValid(end)) return null;
    return differenceInDays(end, start);
  } catch {
    return null;
  }
};

export const getDaysRemaining = (endDate) => {
  if (!endDate) return null;
  try {
    const parsed = parseDateOnly(endDate);
    if (!isValid(parsed)) return null;
    const days = differenceInDays(parsed, new Date());
    return days > 0 ? days : 0;
  } catch {
    return null;
  }
};

/**
 * Get the number of calendar days from today until a date. Unlike
 * getDaysRemaining (which counts full 24-hour periods), this counts day-boundary
 * crossings, so an event later today is 0, tomorrow is 1, and so on regardless
 * of the time of day. Past dates return a negative value.
 * @param {string} endDate - End date in ISO format
 * @returns {number|null} Calendar days until the date, or null if invalid
 */
export const getCalendarDaysUntil = (endDate) => {
  if (!endDate) return null;
  try {
    const parsed = parseDateOnly(endDate);
    if (!isValid(parsed)) return null;
    return differenceInCalendarDays(parsed, australianToday());
  } catch {
    return null;
  }
};

/**
 * Check if a date is in the past (before the start of today)
 * @param {string} dateString - Date in ISO format
 * @returns {boolean} True if the date is before today
 */
export const isDatePast = (dateString) => {
  if (!dateString) return false;
  try {
    const date = parseDateOnly(dateString);
    return date < australianToday();
  } catch {
    return false;
  }
};
