const LAST_VISIT_KEY = 'dashboard_last_visit';

/**
 * Gets the last visit timestamp from localStorage
 * @returns {Date|null} The last visit date, or null if this is the first visit
 */
export function getLastVisit() {
  const lastVisit = localStorage.getItem(LAST_VISIT_KEY);
  return lastVisit ? new Date(lastVisit) : null;
}

/**
 * Updates the last visit timestamp in localStorage to the current time
 */
export function updateLastVisit() {
  localStorage.setItem(LAST_VISIT_KEY, new Date().toISOString());
}

/**
 * Checks if an item is new (created after the last visit)
 * @param {string} itemDate - The date string of the item
 * @param {Date|null} lastVisit - The last visit date
 * @returns {boolean} True if the item is new, false otherwise
 */
export function isNewItem(itemDate, lastVisit) {
  if (!lastVisit || !itemDate) {
    return false;
  }

  const itemDateTime = new Date(itemDate);
  return itemDateTime > lastVisit;
}
