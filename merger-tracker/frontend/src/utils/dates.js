import { format, parseISO, differenceInDays } from 'date-fns';

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
