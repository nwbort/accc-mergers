import { useState, useEffect } from 'react';
import { dataCache } from '../utils/dataCache';

/**
 * Fetches JSON from a URL with shared caching and the usual loading/error state.
 *
 * - If `cacheKey` is provided and the cache already has it, data is returned
 *   synchronously on first render and no network request is made.
 * - On cache miss, fetches the URL, stores the parsed JSON in the cache (if a
 *   `cacheKey` is provided), and updates state.
 * - Non-OK responses are treated as errors. The thrown Error has message
 *   `HTTP <status>` and a `status` property for callers that need to
 *   distinguish (e.g. 404 not found).
 * - The in-flight request is aborted on unmount (and on URL change) via
 *   AbortController, so stale responses never touch state after unmount.
 * - Re-runs when `url` changes.
 *
 * Passing a falsy `url` (null/undefined/'') pauses the hook — useful when a
 * URL depends on the result of a previous fetch.
 *
 * @param {string|null|undefined} url - URL to fetch JSON from.
 * @param {{ cacheKey?: string }} [options]
 * @returns {{ data: any, loading: boolean, error: string|null }}
 */
export function useFetchData(url, { cacheKey } = {}) {
  // Track the completed-fetch result, tagged with the URL it came from so we
  // can detect a stale result after the URL prop changes. Cache hits are
  // surfaced via the derived return below — they don't need to live in state.
  const [result, setResult] = useState(() => {
    if (url && cacheKey && dataCache.has(cacheKey)) {
      return { data: dataCache.get(cacheKey), error: null, url };
    }
    return { data: null, error: null, url: null };
  });

  useEffect(() => {
    if (!url) return undefined;
    // Cache hit: nothing to fetch; the derived return handles display.
    if (cacheKey && dataCache.has(cacheKey)) return undefined;

    const controller = new AbortController();

    fetch(url, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) {
          const err = new Error(`HTTP ${res.status}`);
          err.status = res.status;
          throw err;
        }
        return res.json();
      })
      .then((json) => {
        if (controller.signal.aborted) return;
        if (cacheKey) dataCache.set(cacheKey, json);
        setResult({ data: json, error: null, url });
      })
      .catch((err) => {
        if (err.name === 'AbortError' || controller.signal.aborted) return;
        console.error(`useFetchData failed for ${url}:`, err);
        setResult({ data: null, error: err.message, url });
      });

    return () => {
      controller.abort();
    };
  }, [url, cacheKey]);

  // Derive the return value during render so we can honour:
  //   - a falsy url (paused hook),
  //   - an up-to-the-moment cache hit (possibly populated by a sibling hook),
  //   - a stale `result` left over from a previous url (still loading).
  if (!url) return { data: null, loading: false, error: null };
  if (cacheKey && dataCache.has(cacheKey)) {
    return { data: dataCache.get(cacheKey), loading: false, error: null };
  }
  if (result.url !== url) {
    return { data: null, loading: true, error: null };
  }
  return { data: result.data, loading: false, error: result.error };
}
