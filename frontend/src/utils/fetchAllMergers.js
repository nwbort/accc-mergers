import { API_ENDPOINTS } from '../config';
import { dataCache } from './dataCache';
import { buildSearchIndex, clearSearchIndex } from './searchIndex';

const MERGERS_LIST_KEY = 'mergers-list';
// Max concurrent page fetches to avoid saturating the connection pool
const FETCH_BATCH_SIZE = 4;

/**
 * Fetch every page of the merger list, cache it, and rebuild the search
 * index over the full result. Shared by any UI that needs the complete
 * cached merger list (the Mergers page, the command palette).
 *
 * @returns {Promise<{ mergers: Array, searchIndex: Map }>}
 */
export async function fetchAllMergers() {
  const metaResponse = await fetch(API_ENDPOINTS.mergersListMeta);
  if (!metaResponse.ok) throw new Error('Failed to fetch merger list metadata');

  const meta = await metaResponse.json();
  const totalPages = meta.total_pages;

  // Fetch pages in batches to avoid saturating the browser's connection pool.
  // Promise.all within each batch still parallelises those requests.
  const allResponses = [];
  for (let i = 1; i <= totalPages; i += FETCH_BATCH_SIZE) {
    const batch = [];
    for (let j = i; j < i + FETCH_BATCH_SIZE && j <= totalPages; j++) {
      batch.push(fetch(API_ENDPOINTS.mergersListPage(j)));
    }
    const batchResponses = await Promise.all(batch);
    allResponses.push(...batchResponses);
  }

  const pagesResults = await Promise.allSettled(
    allResponses.map((r) => {
      if (!r.ok) throw new Error('Failed to fetch merger page');
      return r.json();
    })
  );

  const allMergers = pagesResults
    .filter((r) => r.status === 'fulfilled')
    .flatMap((r) => r.value.mergers);

  dataCache.set(MERGERS_LIST_KEY, allMergers);

  // Clear the session-cached index so it is rebuilt from the freshly fetched
  // data rather than returning a stale index from a previous navigation.
  clearSearchIndex();
  const searchIndex = buildSearchIndex(allMergers);

  return { mergers: allMergers, searchIndex };
}
