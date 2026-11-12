// The one record browser notifications keep in IndexedDB.
//
// The service worker can't read localStorage, where the follow list lives, so
// while notifications are on the page (PushSync.jsx) mirrors what the worker
// needs here, and the worker keeps its own note of what it has announced in
// the same record. Plain IndexedDB, no library: one database, one store, one
// key.

const DB_NAME = 'mergers-fyi-push';
const STORE = 'state';
const KEY = 'state';

function open() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function run(mode, action) {
  const db = await open();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      const request = action(tx.objectStore(STORE));
      tx.oncomplete = () => resolve(request.result);
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}

/** The stored record, or null. */
export function readPushState() {
  return run('readonly', (store) => store.get(KEY)).then((value) => value ?? null);
}

/**
 * Merge *changes* (an object, or a function of the stored record returning
 * one) into the stored record. Read and written in one transaction, so the
 * page's mirror and the worker's notes can't overwrite each other's fields.
 */
export function updatePushState(changes) {
  return run('readwrite', (store) => {
    const get = store.get(KEY);
    get.onsuccess = () => {
      const current = get.result || {};
      const next = typeof changes === 'function' ? changes(current) : changes;
      store.put({ ...current, ...next }, KEY);
    };
    return get;
  });
}

/** Forget everything: notifications were turned off. */
export function clearPushState() {
  return run('readwrite', (store) => store.delete(KEY));
}
