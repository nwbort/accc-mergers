import { useEffect } from 'react';
import { act, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TrackingProvider, useTracking } from '../../context/TrackingContext';
import { setFollowHandler } from '../followOffer';

// A follow tells browser notifications from inside the click, so the
// browser's permission prompt can be shown; an unfollow doesn't.
describe('notifyFollowed from TrackingContext', () => {
  let followed;
  let removeHandler;
  const latest = { current: null };

  function Probe() {
    const value = useTracking();
    useEffect(() => {
      latest.current = value;
    });
    return null;
  }

  beforeEach(() => {
    localStorage.clear();
    globalThis.fetch = vi.fn(async () => ({ ok: false, json: async () => null }));
    followed = vi.fn();
    removeHandler = setFollowHandler(followed);
    render(<TrackingProvider><Probe /></TrackingProvider>);
  });
  afterEach(() => removeHandler());

  it('fires on following a merger, not on unfollowing it', () => {
    act(() => latest.current.toggleTracking('MN-01016'));
    expect(followed).toHaveBeenCalledTimes(1);
    act(() => latest.current.toggleTracking('MN-01016'));
    expect(followed).toHaveBeenCalledTimes(1);
    act(() => latest.current.trackMerger('MN-02000'));
    expect(followed).toHaveBeenCalledTimes(2);
  });

  it('fires on following an industry, and on following every Phase 2 matter', () => {
    act(() => latest.current.toggleIndustryTracking('G', 'Retail'));
    act(() => latest.current.toggleIndustryTracking('G', 'Retail'));
    act(() => latest.current.trackIndustry('H', 'Accommodation'));
    expect(followed).toHaveBeenCalledTimes(2);
    act(() => latest.current.toggleAutoTrackPhase2());
    act(() => latest.current.toggleAutoTrackPhase2());
    expect(followed).toHaveBeenCalledTimes(3);
  });
});
