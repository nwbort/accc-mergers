import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useFetchData } from '../useFetchData';
import { dataCache } from '../../utils/dataCache';

const ok = (json) => ({ ok: true, status: 200, json: () => Promise.resolve(json) });

// routes.js preloads a page's data with dataCache.load before the app mounts;
// main.jsx stops waiting after a few seconds, so on a slow connection the page
// can mount while that request is still in flight.
describe('useFetchData with a preload in flight', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  it('shares one request between concurrent loads of a key', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(ok({ n: 1 }));
    const a = dataCache.load('k', '/data/x.json');
    const b = dataCache.load('k', '/data/x.json');
    expect(a).toBe(b);
    await expect(a).resolves.toEqual({ n: 1 });
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(dataCache.get('k')).toEqual({ n: 1 });
  });

  it('waits on the preload rather than downloading the file again', async () => {
    let release;
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => new Promise((resolve) => { release = () => resolve(ok({ n: 2 })); }),
    );
    dataCache.load('k', '/data/x.json');
    const { result } = renderHook(() => useFetchData('/data/x.json', { cacheKey: 'k' }));
    expect(result.current.loading).toBe(true);
    release();
    await waitFor(() => expect(result.current.data).toEqual({ n: 2 }));
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it('fetches for itself if the preload fails', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(ok({ n: 3 }));
    const preload = dataCache.load('k', '/data/x.json').catch(() => {});
    const { result } = renderHook(() => useFetchData('/data/x.json', { cacheKey: 'k' }));
    await preload;
    await waitFor(() => expect(result.current.data).toEqual({ n: 3 }));
    expect(result.current.error).toBeNull();
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });
});
