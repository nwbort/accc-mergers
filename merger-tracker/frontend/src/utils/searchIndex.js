import { dataCache } from './dataCache';

const SEARCH_INDEX_KEY = 'mergers-search-index';

/**
 * Build a pre-computed search index for fast lookups.
 * Creates a normalized lowercase searchable string for each merger
 * by concatenating all searchable fields (name, ID, parties, industries).
 *
 * The index is cached using the dataCache utility for performance.
 *
 * @param {Array} mergers - Array of merger objects
 * @returns {Map} Map of merger_id -> searchable string
 *
 * @example
 * const mergers = [{
 *   merger_id: 'MN-01019',
 *   merger_name: 'Ampol / Z Energy',
 *   acquirers: [{name: 'Ampol Limited'}],
 *   targets: [{name: 'Z Energy'}],
 *   anzsic_codes: [{name: 'Petroleum Retailing'}]
 * }];
 * const index = buildSearchIndex(mergers);
 * // index.get('MN-01019') => 'ampol / z energy mn-01019 ampol limited z energy petroleum retailing'
 */
export function buildSearchIndex(mergers) {
  // Check cache first
  if (dataCache.has(SEARCH_INDEX_KEY)) {
    return dataCache.get(SEARCH_INDEX_KEY);
  }

  const index = new Map();

  for (const merger of mergers) {
    const searchParts = [];

    // Add merger name and ID
    if (merger.merger_name) searchParts.push(merger.merger_name);
    if (merger.merger_id) searchParts.push(merger.merger_id);

    // Add acquirer names
    if (merger.acquirers) {
      merger.acquirers.forEach((a) => {
        if (a?.name) searchParts.push(a.name);
      });
    }

    // Add target names
    if (merger.targets) {
      merger.targets.forEach((t) => {
        if (t?.name) searchParts.push(t.name);
      });
    }

    // Add ANZSIC code names
    if (merger.anzsic_codes) {
      merger.anzsic_codes.forEach((c) => {
        if (c?.name) searchParts.push(c.name);
      });
    }

    // Create single normalized search string
    const searchString = searchParts.join(' ').toLowerCase();
    index.set(merger.merger_id, searchString);
  }

  // Cache for future use
  dataCache.set(SEARCH_INDEX_KEY, index);

  return index;
}

/**
 * Search mergers using the pre-built index.
 *
 * This is significantly faster than iterating through all mergers and
 * checking multiple fields, as it:
 * 1. Only does toLowerCase() once on the search term (not for every field)
 * 2. Performs a single .includes() check per merger (vs 5+ checks)
 * 3. Uses O(1) Map lookups instead of array iterations
 *
 * @param {Array} mergers - Array of merger objects to search
 * @param {string} searchTerm - Term to search for
 * @param {Map} searchIndex - Pre-built search index from buildSearchIndex()
 * @returns {Array} Filtered array of mergers matching the search term
 *
 * @example
 * const filtered = searchMergers(mergers, 'ampol', searchIndex);
 * // Returns all mergers where 'ampol' appears in name, ID, parties, or industries
 */
export function searchMergers(mergers, searchTerm, searchIndex) {
  if (!searchTerm) return mergers;

  const term = searchTerm.toLowerCase().trim();
  if (!term) return mergers;

  return mergers.filter((merger) => {
    const searchString = searchIndex.get(merger.merger_id);
    return searchString && searchString.includes(term);
  });
}

/**
 * Clear the search index cache.
 * Call this when the merger data has been updated to force a rebuild.
 */
export function clearSearchIndex() {
  dataCache.clear(SEARCH_INDEX_KEY);
}
