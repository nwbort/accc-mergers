// Simple in-memory data cache to prevent reload flicker when switching tabs,
// and to power background revalidation so a tab left open on a page picks up
// freshly published data without a full reload.
// Data persists across route changes since this is a module-level cache.

const cache = new Map(); // key -> { data, fetchedAt, validator }
const listeners = new Map(); // key -> Set<(data) => void>
const activeUrls = new Map(); // key -> url, for cacheKeys currently on screen
const activeRefCounts = new Map(); // key -> number of mounted consumers
const pendingLoads = new Map(); // key -> Promise of the data, while a preload is in flight

/**
 * The response's cache validator: its ETag, else its Last-Modified, else null.
 * Stored with each entry so revalidate() can tell an unchanged file from its
 * headers alone. A test double without headers just has none.
 */
export function validatorOf(res) {
  const headers = res?.headers;
  if (!headers || typeof headers.get !== 'function') return null;
  return headers.get('ETag') || headers.get('Last-Modified') || null;
}

export const dataCache = {
  get(key) {
    return cache.get(key)?.data;
  },

  // `validator` is the response's validatorOf(), when the caller fetched it.
  set(key, data, validator = null) {
    cache.set(key, { data, fetchedAt: Date.now(), validator });
  },

  has(key) {
    return cache.has(key);
  },

  /**
   * Fetch `url` as JSON into `key`, sharing the request while it is in flight:
   * routes.js preloads a page's data with it before the app mounts, and if the
   * page mounts first (main.jsx stops waiting after a few seconds), its
   * useFetchData waits on the same request (pending) rather than downloading
   * the file again. TrackingContext reads followed files through it too, so a
   * followed merger's page and the notification panel share one download.
   * Rejects as fetch does, or with an `HTTP <status>` error carrying `status`.
   */
  load(key, url) {
    if (!pendingLoads.has(key)) {
      const request = fetch(url)
        .then((res) => {
          if (!res.ok) {
            const err = new Error(`HTTP ${res.status}`);
            err.status = res.status;
            throw err;
          }
          return res.json().then((data) => {
            cache.set(key, { data, fetchedAt: Date.now(), validator: validatorOf(res) });
            return data;
          });
        })
        .finally(() => pendingLoads.delete(key));
      pendingLoads.set(key, request);
    }
    return pendingLoads.get(key);
  },

  /** The in-flight load() for `key`, if there is one. */
  pending(key) {
    return pendingLoads.get(key);
  },

  clear(key) {
    if (key) {
      cache.delete(key);
    } else {
      cache.clear();
    }
  },

  // When `key` was last (re)fetched, or null if it's never been cached.
  fetchedAt(key) {
    return cache.get(key)?.fetchedAt ?? null;
  },

  // Registers `url` as the resource behind `key` while it's on screen, so
  // background revalidation (useBackgroundRefresh) knows what to re-fetch.
  // Consumers of the same key share one entry. Returns an unregister
  // function to call on unmount.
  registerActive(key, url) {
    activeUrls.set(key, url);
    activeRefCounts.set(key, (activeRefCounts.get(key) || 0) + 1);
    return () => {
      const count = (activeRefCounts.get(key) || 1) - 1;
      if (count <= 0) {
        activeRefCounts.delete(key);
        activeUrls.delete(key);
      } else {
        activeRefCounts.set(key, count);
      }
    };
  },

  // [key, url] pairs currently on screen.
  activeEntries() {
    return [...activeUrls.entries()];
  },

  // Subscribes to changes to `key`'s cached value. Called only when
  // `revalidate` finds the data has actually changed — a plain `set()`
  // (the normal fetch-once path) does not notify. Returns an unsubscribe
  // function.
  subscribe(key, callback) {
    if (!listeners.has(key)) listeners.set(key, new Set());
    listeners.get(key).add(callback);
    return () => {
      listeners.get(key)?.delete(callback);
    };
  },

  // Re-fetches `url` in the background and, if the result differs from
  // what's cached under `key`, stores it and notifies subscribers so any
  // mounted useFetchData hooks re-render with the fresh data.
  //
  // `no-cache` makes the browser revalidate its HTTP-cached copy with the
  // server (If-None-Match), so an unchanged file costs a 304 rather than the
  // whole body; the browser then hands back its cached copy, validator and
  // all. A validator matching the one stored with the entry means nothing
  // changed, and the body isn't even parsed. Otherwise (no validator, or a
  // new one) the parsed data is compared with what's cached, so a redeploy
  // that changes a file's ETag but not its content doesn't re-render anything.
  //
  // Errors (offline, a bad response) are swallowed: this runs silently,
  // leaving whatever's already cached in place.
  async revalidate(key, url) {
    try {
      const res = await fetch(url, { cache: 'no-cache' });
      if (!res.ok) return;
      const validator = validatorOf(res);
      const previous = cache.get(key);
      if (previous && validator && previous.validator === validator) {
        cache.set(key, { ...previous, fetchedAt: Date.now() });
        return;
      }
      const data = await res.json();
      // Re-read: the entry may have been replaced while the body downloaded.
      const current = cache.get(key);
      if (current && JSON.stringify(current.data) === JSON.stringify(data)) {
        // Keep the cached object, so consumers holding it see no change.
        cache.set(key, { data: current.data, fetchedAt: Date.now(), validator });
        return;
      }
      cache.set(key, { data, fetchedAt: Date.now(), validator });
      listeners.get(key)?.forEach((cb) => cb(data));
    } catch {
      // Offline, aborted, or an unparseable body — leave the cache as-is.
    }
  },
};
