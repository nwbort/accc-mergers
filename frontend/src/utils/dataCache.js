// Simple in-memory data cache to prevent reload flicker when switching tabs,
// and to power background revalidation so a tab left open on a page picks up
// freshly published data without a full reload.
// Data persists across route changes since this is a module-level cache.

const cache = new Map(); // key -> { data, fetchedAt }
const listeners = new Map(); // key -> Set<(data) => void>
const activeUrls = new Map(); // key -> url, for cacheKeys currently on screen
const activeRefCounts = new Map(); // key -> number of mounted consumers

export const dataCache = {
  get(key) {
    return cache.get(key)?.data;
  },

  set(key, data) {
    cache.set(key, { data, fetchedAt: Date.now() });
  },

  has(key) {
    return cache.has(key);
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
  // mounted useFetchData hooks re-render with the fresh data. `no-store`
  // bypasses the browser's HTTP cache — the whole point is checking whether
  // the pipeline has published something new since the last fetch. Errors
  // (offline, a bad response) are swallowed: this runs silently, leaving
  // whatever's already cached in place.
  async revalidate(key, url) {
    try {
      const res = await fetch(url, { cache: 'no-store' });
      if (!res.ok) return;
      const data = await res.json();
      const previous = cache.get(key);
      cache.set(key, { data, fetchedAt: Date.now() });
      if (!previous || JSON.stringify(previous.data) !== JSON.stringify(data)) {
        listeners.get(key)?.forEach((cb) => cb(data));
      }
    } catch {
      // Offline, aborted, or an unparseable body — leave the cache as-is.
    }
  },
};
