const SEEN_ITEMS_KEY = 'dashboard_seen_items';

/**
 * Gets the set of seen item IDs from localStorage
 * @returns {Set<string>} Set of merger IDs that have been seen
 */
export function getSeenItems() {
  const seenItems = localStorage.getItem(SEEN_ITEMS_KEY);
  return seenItems ? new Set(JSON.parse(seenItems)) : new Set();
}

/**
 * Marks a single item as seen
 * @param {string} itemId - The merger ID to mark as seen
 */
export function markItemAsSeen(itemId) {
  if (!itemId) return;

  const seenItems = getSeenItems();
  seenItems.add(itemId);
  localStorage.setItem(SEEN_ITEMS_KEY, JSON.stringify([...seenItems]));
}

/**
 * Marks multiple items as seen
 * @param {string[]} itemIds - Array of merger IDs to mark as seen
 */
export function markItemsAsSeen(itemIds) {
  if (!itemIds || itemIds.length === 0) return;

  const seenItems = getSeenItems();
  itemIds.forEach(id => {
    if (id) seenItems.add(id);
  });
  localStorage.setItem(SEEN_ITEMS_KEY, JSON.stringify([...seenItems]));
}

/**
 * Checks if an item is new (not yet seen by the user)
 * @param {string} itemId - The merger ID to check
 * @returns {boolean} True if the item has not been seen, false otherwise
 */
export function isNewItem(itemId) {
  if (!itemId) return false;

  const seenItems = getSeenItems();
  return !seenItems.has(itemId);
}

/**
 * Clears all seen items (useful for testing or reset)
 */
export function clearSeenItems() {
  localStorage.removeItem(SEEN_ITEMS_KEY);
}
