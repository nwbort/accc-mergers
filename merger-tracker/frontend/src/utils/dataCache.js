// Simple in-memory data cache to prevent reload flicker when switching tabs
// Data persists across route changes since this is a module-level cache

const cache = new Map();

// Pre-populate from build-time embedded data (SSG).
// The prerender script injects a <script id="__SSG_DATA__" type="application/json">
// tag containing a JSON map of cache-key → data for the current page.
try {
  const el = document.getElementById('__SSG_DATA__');
  if (el) {
    const ssgData = JSON.parse(el.textContent);
    for (const [key, value] of Object.entries(ssgData)) {
      cache.set(key, value);
    }
    // Clean up — no longer needed in the DOM
    el.remove();
  }
} catch {
  // Silently ignore parse errors; pages will fetch data normally
}

export const dataCache = {
  get(key) {
    return cache.get(key);
  },

  set(key, data) {
    cache.set(key, data);
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
};
