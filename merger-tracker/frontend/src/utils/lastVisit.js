const SEEN_ITEMS_KEY = 'dashboard_seen_items';
const MAX_SEEN_ITEMS = 100; // Limit to prevent unbounded growth

/**
 * Gets the set of seen item IDs from localStorage
 * @returns {Set<string>} Set of merger IDs that have been seen
 */
export function getSeenItems() {
  // Guarded like TrackingContext's localStorage reads: a corrupted value or
  // blocked storage must degrade to "nothing seen", not throw during render.
  try {
    const seenItems = localStorage.getItem(SEEN_ITEMS_KEY);
    return seenItems ? new Set(JSON.parse(seenItems)) : new Set();
  } catch (err) {
    console.error('Failed to read seen items from localStorage:', err);
    return new Set();
  }
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
  try {
    localStorage.setItem(SEEN_ITEMS_KEY, JSON.stringify([...prunedItems]));
  } catch (err) {
    console.error('Failed to save seen items to localStorage:', err);
  }
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
 * Floats unseen ("New") items to the top of a list while preserving the
 * incoming order within the seen and unseen groups.
 *
 * The dashboard lists arrive sorted by event date (determination date /
 * notification datetime), but the ACCC register frequently backdates records,
 * so a brand-new card can carry an older date and get buried mid-list even
 * though it shows a "New" badge. Partitioning unseen items to the front keeps
 * the "New" cards where the eye lands first. The partition is stable, so within
 * each group the original date ordering is untouched; once an item is marked
 * seen it settles back into chronological order on the next load.
 *
 * @param {Array} items - The items to order (already date-sorted).
 * @param {(item: any) => string} getId - Extracts the merger ID used to test
 *   whether the item has been seen.
 * @returns {Array} A new array with unseen items first.
 */
export function sortUnseenFirst(items, getId) {
  if (!items || items.length === 0) return [];

  const seenItems = getSeenItems();
  const unseen = [];
  const seen = [];
  for (const item of items) {
    const id = getId(item);
    if (id && !seenItems.has(id)) {
      unseen.push(item);
    } else {
      seen.push(item);
    }
  }
  return [...unseen, ...seen];
}

