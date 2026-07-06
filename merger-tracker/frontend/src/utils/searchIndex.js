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
 * @param {Object} [options]
 * @param {boolean} [options.cache=true] - Whether to read/write the shared
 *   dataCache entry. Pass `false` while building an index over a partial
 *   (still-loading) merger list so an incomplete index is never mistaken for
 *   the cached, complete one.
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
export function buildSearchIndex(mergers, { cache = true } = {}) {
  // Check cache first
  if (cache && dataCache.has(SEARCH_INDEX_KEY)) {
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

    // Add other-party names
    if (merger.other_parties) {
      merger.other_parties.forEach((p) => {
        if (p?.name) searchParts.push(p.name);
      });
    }

    // Add canonical "related party" names so a search for the canonical name
    // (used by the party links on the merger detail page) surfaces every merger
    // involving the same entity, even when its on-record name differs.
    [merger.acquirers, merger.targets, merger.other_parties].forEach((parties) => {
      if (!parties) return;
      parties.forEach((p) => {
        if (p?.canonical?.name) searchParts.push(p.canonical.name);
      });
    });

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
  if (cache) {
    dataCache.set(SEARCH_INDEX_KEY, index);
  }

  return index;
}

// Matches quoted phrases (kept as a single token, quotes stripped) or
// runs of non-whitespace characters.
const TOKEN_PATTERN = /"([^"]+)"|(\S+)/g;

/**
 * Split a search term into lowercase tokens on whitespace, treating any
 * "quoted phrase" as a single token.
 *
 * @param {string} searchTerm - Raw search term
 * @returns {string[]} Non-empty, lowercased tokens
 */
function tokenize(searchTerm) {
  const tokens = [];
  let match;
  while ((match = TOKEN_PATTERN.exec(searchTerm)) !== null) {
    const token = (match[1] ?? match[2]).toLowerCase();
    if (token) tokens.push(token);
  }
  return tokens;
}

/**
 * Search mergers using the pre-built index.
 *
 * This is significantly faster than iterating through all mergers and
 * checking multiple fields, as it:
 * 1. Only does toLowerCase() once on the search term (not for every field)
 * 2. Performs a single .includes() check per token per merger (vs 5+ field checks)
 * 3. Uses O(1) Map lookups instead of array iterations
 *
 * The search term is split into whitespace-separated tokens (quoted phrases
 * count as one token); a merger matches only if every token is a substring
 * of its index string, so token order and adjacency don't matter.
 *
 * @param {Array} mergers - Array of merger objects to search
 * @param {string} searchTerm - Term to search for
 * @param {Map} searchIndex - Pre-built search index from buildSearchIndex()
 * @returns {Array} Filtered array of mergers matching every search token
 *
 * @example
 * const filtered = searchMergers(mergers, 'ampol', searchIndex);
 * // Returns all mergers where 'ampol' appears in name, ID, parties, or industries
 *
 * @example
 * const filtered = searchMergers(mergers, 'google wiz', searchIndex);
 * // Returns mergers whose index contains both 'google' and 'wiz',
 * // even non-adjacently (e.g. "... google ... wiz ...")
 */
export function searchMergers(mergers, searchTerm, searchIndex) {
  if (!searchTerm) return mergers;

  const tokens = tokenize(searchTerm);
  if (!tokens.length) return mergers;

  return mergers.filter((merger) => {
    const searchString = searchIndex.get(merger.merger_id);
    return searchString && tokens.every((token) => searchString.includes(token));
  });
}

/**
 * Clear the search index cache.
 * Call this when the merger data has been updated to force a rebuild.
 */
export function clearSearchIndex() {
  dataCache.clear(SEARCH_INDEX_KEY);
}
