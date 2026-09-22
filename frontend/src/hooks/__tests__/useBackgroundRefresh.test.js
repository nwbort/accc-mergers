import { renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useBackgroundRefresh } from '../useBackgroundRefresh';
import { dataCache } from '../../utils/dataCache';

function setVisibility(state) {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    get: () => state,
  });
}

describe('useBackgroundRefresh', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setVisibility('visible');
  });

  afterEach(() => {
    dataCache.clear();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('revalidates a stale active key on regaining visibility', () => {
    dataCache.registerActive('k', '/data/k.json');
    dataCache.set('k', { a: 1 });
    vi.setSystemTime(Date.now() + 10 * 60 * 1000); // past the 5-minute staleness window
    const revalidateSpy = vi.spyOn(dataCache, 'revalidate').mockResolvedValue(undefined);

    renderHook(() => useBackgroundRefresh());
    setVisibility('visible');
    document.dispatchEvent(new Event('visibilitychange'));

    expect(revalidateSpy).toHaveBeenCalledWith('k', '/data/k.json');
  });

  it('does not revalidate a key that was fetched recently', () => {
    dataCache.registerActive('k', '/data/k.json');
    dataCache.set('k', { a: 1 });
    const revalidateSpy = vi.spyOn(dataCache, 'revalidate').mockResolvedValue(undefined);

    renderHook(() => useBackgroundRefresh());
    document.dispatchEvent(new Event('visibilitychange'));

    expect(revalidateSpy).not.toHaveBeenCalled();
  });

  it('does not revalidate a key that has never been fetched', () => {
    dataCache.registerActive('k', '/data/k.json');
    const revalidateSpy = vi.spyOn(dataCache, 'revalidate').mockResolvedValue(undefined);

    renderHook(() => useBackgroundRefresh());
    document.dispatchEvent(new Event('visibilitychange'));

    expect(revalidateSpy).not.toHaveBeenCalled();
  });

  it('ignores a visibilitychange to hidden', () => {
    dataCache.registerActive('k', '/data/k.json');
    dataCache.set('k', { a: 1 });
    vi.setSystemTime(Date.now() + 10 * 60 * 1000);
    const revalidateSpy = vi.spyOn(dataCache, 'revalidate').mockResolvedValue(undefined);

    renderHook(() => useBackgroundRefresh());
    setVisibility('hidden');
    document.dispatchEvent(new Event('visibilitychange'));

    expect(revalidateSpy).not.toHaveBeenCalled();
  });

  it('polls on a fallback interval while the tab stays visible', () => {
    dataCache.registerActive('k', '/data/k.json');
    dataCache.set('k', { a: 1 });
    const revalidateSpy = vi.spyOn(dataCache, 'revalidate').mockResolvedValue(undefined);

    renderHook(() => useBackgroundRefresh());
    vi.advanceTimersByTime(15 * 60 * 1000 + 1);

    expect(revalidateSpy).toHaveBeenCalledWith('k', '/data/k.json');
  });

  it('removes its listeners and timer on unmount', () => {
    const addSpy = vi.spyOn(document, 'addEventListener');
    const removeSpy = vi.spyOn(document, 'removeEventListener');

    const { unmount } = renderHook(() => useBackgroundRefresh());
    expect(addSpy).toHaveBeenCalledWith('visibilitychange', expect.any(Function));

    unmount();

    expect(removeSpy).toHaveBeenCalledWith('visibilitychange', expect.any(Function));
  });
});
