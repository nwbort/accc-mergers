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
 */
const isChristmasNewYearPeriod = (date) => {
  const month = date.getMonth();
  const day = date.getDate();
  if (month === 11 && day >= 23) return true;
  if (month === 0 && day <= 10) return true;
  return false;
};

export const isBusinessDay = (date) => {
  const dayOfWeek = getDay(date);
  if (dayOfWeek === 0 || dayOfWeek === 6) return false;
  if (isChristmasNewYearPeriod(date)) return false;
  const dateString = format(date, 'yyyy-MM-dd');
  if (publicHolidaySet.has(dateString)) return false;
  return true;
};

export const calculateBusinessDays = (startDate, endDate) => {
  if (!startDate || !endDate) return null;
  try {
    const start = typeof startDate === 'string' ? parseISO(startDate) : startDate;
    const end = typeof endDate === 'string' ? parseISO(endDate) : endDate;
    let businessDays = 0;
    let currentDate = addDays(new Date(start), 1);
    while (currentDate <= end) {
      if (isBusinessDay(currentDate)) businessDays++;
      currentDate = addDays(currentDate, 1);
    }
    return businessDays;
  } catch {
    return null;
  }
};

export const getBusinessDaysRemaining = (endDate) => {
  if (!endDate) return null;
  try {
    const end = parseISO(endDate);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    if (end <= today) return 0;
    return calculateBusinessDays(today, end);
  } catch {
    return null;
  }
};

export const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    return format(parseISO(dateString), 'dd/MM/yyyy');
  } catch {
    return 'Invalid date';
  }
};

export const calculateDuration = (startDate, endDate) => {
  if (!startDate || !endDate) return null;
  try {
    return differenceInDays(parseISO(endDate), parseISO(startDate));
  } catch {
    return null;
  }
};

export const getDaysRemaining = (endDate) => {
  if (!endDate) return null;
  try {
    const days = differenceInDays(parseISO(endDate), new Date());
    return days > 0 ? days : 0;
  } catch {
    return null;
  }
};

export const isDatePast = (dateString) => {
  if (!dateString) return false;
  try {
    const date = parseISO(dateString);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return date < today;
  } catch {
    return false;
  }
};
