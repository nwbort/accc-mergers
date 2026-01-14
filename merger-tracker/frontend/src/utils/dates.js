import { format, parseISO, differenceInDays, addDays, getDay } from 'date-fns';
import actPublicHolidays from '../data/act-public-holidays.json';

// Build a Set of public holiday dates for fast lookup
const publicHolidaySet = new Set();
actPublicHolidays.holidays.forEach(yearData => {
  yearData.dates.forEach(holiday => {
    publicHolidaySet.add(holiday.date);
  });
});

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
    const start = typeof startDate === 'string' ? parseISO(startDate) : startDate;
    const end = typeof endDate === 'string' ? parseISO(endDate) : endDate;

    let businessDays = 0;
    let currentDate = new Date(start);

    // Include the start date in the calculation
    while (currentDate <= end) {
      if (isBusinessDay(currentDate)) {
        businessDays++;
      }
      currentDate = addDays(currentDate, 1);
    }

    return businessDays;
  } catch (e) {
    console.error('Error calculating business days:', e);
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
    const end = parseISO(endDate);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    if (end <= today) return 0;
    
    // Start counting from tomorrow
    const tomorrow = addDays(today, 1);
    return calculateBusinessDays(tomorrow, end);
  } catch (e) {
    console.error('Error calculating business days remaining:', e);
    return null;
  }
};

export const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    return format(parseISO(dateString), 'dd/MM/yyyy');
  } catch (e) {
    return 'Invalid date';
  }
};

export const formatDateTime = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    return format(parseISO(dateString), 'dd/MM/yyyy HH:mm');
  } catch (e) {
    return 'Invalid date';
  }
};

export const calculateDuration = (startDate, endDate) => {
  if (!startDate || !endDate) return null;
  try {
    return differenceInDays(parseISO(endDate), parseISO(startDate));
  } catch (e) {
    return null;
  }
};

export const getDaysRemaining = (endDate) => {
  if (!endDate) return null;
  try {
    const days = differenceInDays(parseISO(endDate), new Date());
    return days > 0 ? days : 0;
  } catch (e) {
    return null;
  }
};
