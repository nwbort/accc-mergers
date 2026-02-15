const SEEN_ITEMS_KEY = 'dashboard_seen_items';
const MAX_SEEN_ITEMS = 100; // Limit to prevent unbounded growth

/**
 * Gets the set of seen item IDs from localStorage
 * @returns {Set<string>} Set of merger IDs that have been seen
 */
export function getSeenItems() {
  const seenItems = localStorage.getItem(SEEN_ITEMS_KEY);
  return seenItems ? new Set(JSON.parse(seenItems)) : new Set();
}

/**
 * Prunes the seen items set to stay within MAX_SEEN_ITEMS limit
 * Removes oldest items (from the beginning of the array) when limit is exceeded
 * @param {Set<string>} seenItems - The current set of seen items
 * @returns {Set<string>} The pruned set of seen items
 */
function pruneSeenItems(seenItems) {
  if (seenItems.size <= MAX_SEEN_ITEMS) {
    return seenItems;
  }

  // Convert to array, keep only the most recent MAX_SEEN_ITEMS entries
  const itemsArray = [...seenItems];
  const prunedArray = itemsArray.slice(-MAX_SEEN_ITEMS);
  return new Set(prunedArray);
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

  const prunedItems = pruneSeenItems(seenItems);
  localStorage.setItem(SEEN_ITEMS_KEY, JSON.stringify([...prunedItems]));
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

