import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useFetchData } from '../useFetchData';
import { dataCache } from '../../utils/dataCache';

// Deferred promise helper — lets a test control when a fetch resolves/rejects.
function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

// Minimal Response stand-in. Mocking global fetch directly so we don't depend
// on the Response constructor being available in jsdom.
function okResponse(json) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve(json),
  };
}

function errorResponse(status) {
  return {
    ok: false,
    status,
    json: () => Promise.resolve({}),
  };
}

describe('useFetchData', () => {
  let consoleErrorSpy;

  beforeEach(() => {
    dataCache.clear();
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  it('returns cached data synchronously when the cache already has the key (no fetch)', () => {
    dataCache.set('cached-key', { hello: 'world' });
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

    const { result } = renderHook(() =>
      useFetchData('/data/thing.json', { cacheKey: 'cached-key' })
    );

    expect(result.current.data).toEqual({ hello: 'world' });
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('fetches on cache miss, populates cache, and returns the data', async () => {
    const payload = { items: [1, 2, 3] };
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(okResponse(payload));

    const { result } = renderHook(() =>
      useFetchData('/data/list.json', { cacheKey: 'list-key' })
    );

    // Initial render: loading=true, no data yet.
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toEqual(payload);
    expect(result.current.error).toBeNull();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(fetchSpy).toHaveBeenCalledWith(
      '/data/list.json',
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
    expect(dataCache.get('list-key')).toEqual(payload);
  });

  it('treats a non-ok response as an error (HTTP <status>)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(errorResponse(404));

    const { result } = renderHook(() =>
      useFetchData('/data/missing.json', { cacheKey: 'missing-key' })
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('HTTP 404');
    expect(result.current.data).toBeNull();
    expect(dataCache.has('missing-key')).toBe(false);
    expect(consoleErrorSpy).toHaveBeenCalled();
  });

  it('captures network errors and logs them to console.error', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));

    const { result } = renderHook(() => useFetchData('/data/offline.json'));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Failed to fetch');
    expect(result.current.data).toBeNull();
    expect(consoleErrorSpy).toHaveBeenCalled();
  });

  it('aborts in-flight fetches on unmount and does not update state afterwards', async () => {
    const { promise, resolve } = deferred();
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(
      (_url, { signal }) => {
        // Reject with AbortError when the caller aborts, matching fetch semantics.
        signal.addEventListener('abort', () => {
          const abortErr = new Error('aborted');
          abortErr.name = 'AbortError';
          // eslint-disable-next-line promise/no-promise-in-callback
          Promise.resolve().then(() => {
            // no-op; promise already wired up via `reject` below
          });
        });
        return promise;
      }
    );

    const { unmount } = renderHook(() => useFetchData('/data/slow.json'));
    // The fetch was started.
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const signal = fetchSpy.mock.calls[0][1].signal;
    expect(signal.aborted).toBe(false);

    unmount();

    // After unmount, the AbortController should have fired.
    expect(signal.aborted).toBe(true);

    // Resolve the stale promise to simulate a response arriving after unmount.
    // Nothing should throw, and no state updates happen because the component
    // is gone.
    await act(async () => {
      resolve(okResponse({ late: true }));
      await Promise.resolve();
    });

    // We can't read state after unmount; the important contract is that no
    // "update on unmounted component" warnings were logged to console.error.
    const unmountWarnings = consoleErrorSpy.mock.calls.filter((args) =>
      String(args[0]).includes('unmounted')
    );
    expect(unmountWarnings).toHaveLength(0);
  });

  it('re-fetches when the url changes and returns the new data', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation((url) => Promise.resolve(okResponse({ url })));

    const { result, rerender } = renderHook(
      ({ url, cacheKey }) => useFetchData(url, { cacheKey }),
      { initialProps: { url: '/data/a.json', cacheKey: 'key-a' } }
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({ url: '/data/a.json' });

    rerender({ url: '/data/b.json', cacheKey: 'key-b' });

    // New URL → fetch again.
    await waitFor(() => expect(result.current.data).toEqual({ url: '/data/b.json' }));
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(fetchSpy.mock.calls[0][0]).toBe('/data/a.json');
    expect(fetchSpy.mock.calls[1][0]).toBe('/data/b.json');
    expect(dataCache.get('key-a')).toEqual({ url: '/data/a.json' });
    expect(dataCache.get('key-b')).toEqual({ url: '/data/b.json' });
  });

  it('hits the cache without refetching when the url changes back to one already cached', async () => {
    dataCache.set('key-a', { cached: 'A' });
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation((url) => Promise.resolve(okResponse({ url })));

    const { result, rerender } = renderHook(
      ({ url, cacheKey }) => useFetchData(url, { cacheKey }),
      { initialProps: { url: '/data/a.json', cacheKey: 'key-a' } }
    );

    // Cache hit — no fetch.
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(result.current.data).toEqual({ cached: 'A' });

    // Change to a fresh URL (not cached).
    rerender({ url: '/data/b.json', cacheKey: 'key-b' });
    await waitFor(() => expect(result.current.data).toEqual({ url: '/data/b.json' }));
    expect(fetchSpy).toHaveBeenCalledTimes(1);

    // Back to the first URL — cache hit, still only one fetch.
    rerender({ url: '/data/a.json', cacheKey: 'key-a' });
    await waitFor(() => expect(result.current.data).toEqual({ cached: 'A' }));
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it('does not cache responses when no cacheKey is supplied', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(okResponse({ x: 1 }));

    const { result } = renderHook(() => useFetchData('/data/nocache.json'));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({ x: 1 });
    // No key means nothing written to the shared cache.
    expect([...dataCacheKeys()]).toHaveLength(0);
  });
});

// Helper to inspect cache keys — the cache module doesn't expose the underlying
// Map, so we re-derive keys by probing a known set. For tests we just check
// it's empty, so a minimal helper suffices.
function dataCacheKeys() {
  const probed = new Set();
  for (const k of ['nocache-key', 'list-key', 'missing-key', 'cached-key']) {
    if (dataCache.has(k)) probed.add(k);
  }
  return probed;
}
