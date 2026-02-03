// Simple in-memory data cache to prevent reload flicker when switching tabs
// Data persists across route changes since this is a module-level cache

const cache = new Map();

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
