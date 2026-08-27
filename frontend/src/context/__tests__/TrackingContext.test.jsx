import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TrackingProvider, useTracking } from '../TrackingContext';

// Minimal Response stand-in (matches the style in useFetchData.test.js).
function okResponse(json) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve(json),
  };
}

function notFoundResponse() {
  return {
    ok: false,
    status: 404,
    json: () => Promise.resolve({}),
  };
}

// Stub globalThis.fetch from a map of merger_id -> detail object. Any merger not
// in the map resolves to a 404 (mirrors a missing per-merger JSON file). Assigns
// directly (rather than spyOn) so a test can swap the dataset mid-flight to
// simulate the data being refreshed between visits.
const originalFetch = globalThis.fetch;
function mockFetchFromMergers(mergers) {
  globalThis.fetch = vi.fn((url) => {
    const match = /\/data\/mergers\/([^/]+)\.json$/.exec(url);
    if (match) {
      const merger = mergers[match[1]];
      return Promise.resolve(merger ? okResponse(merger) : notFoundResponse());
    }
    // Industry detail / anything else: irrelevant to these tests.
    return Promise.resolve(notFoundResponse());
  });
}

const wrapper = ({ children }) => <TrackingProvider>{children}</TrackingProvider>;

describe('TrackingContext auto-tracking of related mergers', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('auto-tracks the re-filed matter when tracking the earlier (waiver) one', async () => {
    mockFetchFromMergers({
      'WA-1': {
        merger_id: 'WA-1',
        merger_name: 'Waiver',
        events: [],
        related_merger: { merger_id: 'MN-2', relationship: 'refiled_as', merger_name: 'Notification' },
      },
      'MN-2': {
        merger_id: 'MN-2',
        merger_name: 'Notification',
        events: [],
        related_merger: { merger_id: 'WA-1', relationship: 'refiled_from', merger_name: 'Waiver' },
      },
    });

    const { result } = renderHook(() => useTracking(), { wrapper });

    act(() => {
      result.current.trackMerger('WA-1');
    });

    await waitFor(() => {
      expect(result.current.trackedMergerIds).toContain('MN-2');
    });
    expect(result.current.trackedMergerIds).toEqual(expect.arrayContaining(['WA-1', 'MN-2']));
  });

  it('does NOT auto-track the historical matter when tracking the re-filed one', async () => {
    mockFetchFromMergers({
      'WA-1': {
        merger_id: 'WA-1',
        merger_name: 'Waiver',
        events: [],
        related_merger: { merger_id: 'MN-2', relationship: 'refiled_as', merger_name: 'Notification' },
      },
      'MN-2': {
        merger_id: 'MN-2',
        merger_name: 'Notification',
        events: [],
        related_merger: { merger_id: 'WA-1', relationship: 'refiled_from', merger_name: 'Waiver' },
      },
    });

    const { result } = renderHook(() => useTracking(), { wrapper });

    act(() => {
      result.current.trackMerger('MN-2');
    });

    // Give any (incorrect) auto-track a chance to run before asserting.
    await waitFor(() => {
      expect(result.current.trackedMergerIds).toContain('MN-2');
    });
    expect(result.current.trackedMergerIds).not.toContain('WA-1');
  });

  it('auto-tracks the re-filed matter for a suspended-then-refiled pair', async () => {
    mockFetchFromMergers({
      'MN-10': {
        merger_id: 'MN-10',
        merger_name: 'Suspended',
        events: [],
        related_merger: { merger_id: 'MN-20', relationship: 'suspended_refiled_as', merger_name: 'Refiled' },
      },
      'MN-20': {
        merger_id: 'MN-20',
        merger_name: 'Refiled',
        events: [],
        related_merger: { merger_id: 'MN-10', relationship: 'suspended_refiled_from', merger_name: 'Suspended' },
      },
    });

    const { result } = renderHook(() => useTracking(), { wrapper });

    act(() => {
      result.current.toggleTracking('MN-10');
    });

    await waitFor(() => {
      expect(result.current.trackedMergerIds).toContain('MN-20');
    });
  });

  it('does not re-add a related matter that was untracked while the source stays tracked', async () => {
    mockFetchFromMergers({
      'WA-1': {
        merger_id: 'WA-1',
        merger_name: 'Waiver',
        events: [],
        related_merger: { merger_id: 'MN-2', relationship: 'refiled_as', merger_name: 'Notification' },
      },
      'MN-2': {
        merger_id: 'MN-2',
        merger_name: 'Notification',
        events: [],
        related_merger: { merger_id: 'WA-1', relationship: 'refiled_from', merger_name: 'Waiver' },
      },
    });

    const { result } = renderHook(() => useTracking(), { wrapper });

    act(() => {
      result.current.trackMerger('WA-1');
    });
    await waitFor(() => {
      expect(result.current.trackedMergerIds).toContain('MN-2');
    });

    // Untracking the re-filed matter must stick even though its source is tracked.
    act(() => {
      result.current.untrackMerger('MN-2');
    });
    await waitFor(() => {
      expect(result.current.trackedMergerIds).not.toContain('MN-2');
    });
    expect(result.current.trackedMergerIds).toContain('WA-1');
  });

  it('follows a forward chain of re-filings', async () => {
    mockFetchFromMergers({
      'A': {
        merger_id: 'A',
        merger_name: 'A',
        events: [],
        related_merger: { merger_id: 'B', relationship: 'refiled_as', merger_name: 'B' },
      },
      'B': {
        merger_id: 'B',
        merger_name: 'B',
        events: [],
        related_merger: { merger_id: 'C', relationship: 'suspended_refiled_as', merger_name: 'C' },
      },
      'C': {
        merger_id: 'C',
        merger_name: 'C',
        events: [],
        related_merger: { merger_id: 'B', relationship: 'suspended_refiled_from', merger_name: 'B' },
      },
    });

    const { result } = renderHook(() => useTracking(), { wrapper });

    act(() => {
      result.current.trackMerger('A');
    });

    await waitFor(() => {
      expect(result.current.trackedMergerIds).toEqual(expect.arrayContaining(['A', 'B', 'C']));
    });
  });

  it('surfaces an auto-tracked re-filing as an unseen notification (ping)', async () => {
    mockFetchFromMergers({
      'WA-1': {
        merger_id: 'WA-1',
        merger_name: 'Waiver',
        events: [{ date: '2024-01-01', title: 'Waiver lodged' }],
        related_merger: { merger_id: 'MN-2', relationship: 'refiled_as', merger_name: 'Notification' },
      },
      'MN-2': {
        merger_id: 'MN-2',
        merger_name: 'Notification',
        events: [{ date: '2024-06-01', title: 'Notification lodged' }],
        related_merger: { merger_id: 'WA-1', relationship: 'refiled_from', merger_name: 'Waiver' },
      },
    });

    const { result } = renderHook(() => useTracking(), { wrapper });

    act(() => {
      result.current.trackMerger('WA-1');
    });

    await waitFor(() => {
      expect(result.current.trackedMergerIds).toContain('MN-2');
    });

    // The re-filed matter's events surface as unseen → the user gets a ping.
    await waitFor(() => {
      expect(result.current.unseenEvents.some((e) => e.merger_id === 'MN-2')).toBe(true);
    });
    expect(result.current.unseenCount).toBeGreaterThan(0);

    // The manually-tracked source's own events stay seen (tracking it yourself
    // shouldn't ping you about its history).
    expect(result.current.unseenEvents.some((e) => e.merger_id === 'WA-1')).toBe(false);
  });

  it('auto-tracks a re-filing that is only recorded after the source was tracked', async () => {
    // First visit: the waiver is tracked while still live — no re-filing exists
    // yet, so its detail carries no related_merger link.
    mockFetchFromMergers({
      'WA-1': { merger_id: 'WA-1', merger_name: 'Waiver', events: [] },
    });

    const first = renderHook(() => useTracking(), { wrapper });
    act(() => {
      first.result.current.trackMerger('WA-1');
    });
    await waitFor(() => {
      expect(first.result.current.loading).toBe(false);
    });
    expect(first.result.current.trackedMergerIds).toEqual(['WA-1']);
    first.unmount();

    // Later visit: the waiver was declined and re-filed, the pair is now recorded,
    // and WA-1's detail carries the forward link. (localStorage still holds the
    // WA-1 tracking from the first visit.)
    mockFetchFromMergers({
      'WA-1': {
        merger_id: 'WA-1',
        merger_name: 'Waiver',
        events: [],
        related_merger: { merger_id: 'MN-2', relationship: 'refiled_as', merger_name: 'Notification' },
      },
      'MN-2': {
        merger_id: 'MN-2',
        merger_name: 'Notification',
        events: [],
        related_merger: { merger_id: 'WA-1', relationship: 'refiled_from', merger_name: 'Waiver' },
      },
    });

    const second = renderHook(() => useTracking(), { wrapper });
    await waitFor(() => {
      expect(second.result.current.trackedMergerIds).toContain('MN-2');
    });
    expect(second.result.current.trackedMergerIds).toContain('WA-1');
  });
});

// Stub globalThis.fetch to serve a phase2.json payload (current + completed) and
// treat any per-merger detail URL as an empty, event-less matter so the main
// event-fetch effect resolves cleanly.
function mockFetchFromPhase2(phase2) {
  globalThis.fetch = vi.fn((url) => {
    if (/\/data\/phase2\.json$/.test(url)) {
      return Promise.resolve(okResponse(phase2));
    }
    const match = /\/data\/mergers\/([^/]+)\.json$/.exec(url);
    if (match) {
      return Promise.resolve(okResponse({ merger_id: match[1], merger_name: match[1], events: [] }));
    }
    return Promise.resolve(notFoundResponse());
  });
}

describe('TrackingContext synthetic upcoming events', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  // Far-future deadline so the "due date is in the future" check always passes.
  const FUTURE = '2099-01-01T12:00:00Z';

  it('synthesises a determination-due event for an undetermined merger', async () => {
    mockFetchFromMergers({
      'MN-1': {
        merger_id: 'MN-1',
        merger_name: 'Open matter',
        status: 'Under assessment',
        events: [],
        end_of_determination_period: FUTURE,
      },
    });

    const { result } = renderHook(() => useTracking(), { wrapper });
    act(() => {
      result.current.trackMerger('MN-1');
    });

    await waitFor(() => {
      expect(result.current.trackedEvents.some((e) => e.type === 'determination_due')).toBe(true);
    });
  });

  it('skips due events once accc_determination is set, even without a publication date', async () => {
    // The register sometimes publishes the outcome before the date field is
    // scraped; the panel must not keep showing "Determination due" (mirrors
    // upcoming_events.py's candidate filter).
    mockFetchFromMergers({
      'MN-1': {
        merger_id: 'MN-1',
        merger_name: 'Decided matter',
        status: 'Assessment completed',
        accc_determination: 'Approved',
        events: [],
        end_of_determination_period: FUTURE,
      },
    });

    const { result } = renderHook(() => useTracking(), { wrapper });
    act(() => {
      result.current.trackMerger('MN-1');
    });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.trackedEvents.some((e) => e.type === 'determination_due')).toBe(false);
  });
});

describe('TrackingContext auto-tracking of Phase 2 matters', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('does nothing while the setting is off', async () => {
    mockFetchFromPhase2({ current: [{ merger_id: 'MN-1' }], completed: [] });

    const { result } = renderHook(() => useTracking(), { wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.autoTrackPhase2).toBe(false);
    expect(result.current.trackedMergerIds).not.toContain('MN-1');
  });

  it('tracks all current Phase 2 matters when the setting is enabled', async () => {
    mockFetchFromPhase2({
      current: [{ merger_id: 'MN-1' }, { merger_id: 'MN-2' }],
      completed: [{ merger_id: 'MN-OLD' }],
    });

    const { result } = renderHook(() => useTracking(), { wrapper });

    act(() => {
      result.current.toggleAutoTrackPhase2();
    });

    await waitFor(() => {
      expect(result.current.trackedMergerIds).toEqual(expect.arrayContaining(['MN-1', 'MN-2']));
    });
    // Completed matters are not retroactively tracked.
    expect(result.current.trackedMergerIds).not.toContain('MN-OLD');
  });

  it('does not re-add a Phase 2 matter the user untracked while the setting stays on', async () => {
    mockFetchFromPhase2({ current: [{ merger_id: 'MN-1' }], completed: [] });

    const { result, unmount } = renderHook(() => useTracking(), { wrapper });

    act(() => {
      result.current.toggleAutoTrackPhase2();
    });
    await waitFor(() => {
      expect(result.current.trackedMergerIds).toContain('MN-1');
    });

    act(() => {
      result.current.untrackMerger('MN-1');
    });
    await waitFor(() => {
      expect(result.current.trackedMergerIds).not.toContain('MN-1');
    });

    // Re-mounting (a later visit) with the same feed must not silently re-add it.
    unmount();
    const second = renderHook(() => useTracking(), { wrapper });
    await waitFor(() => {
      expect(second.result.current.loading).toBe(false);
    });
    expect(second.result.current.trackedMergerIds).not.toContain('MN-1');
  });

  it('picks up a matter that reaches Phase 2 after the setting was enabled', async () => {
    mockFetchFromPhase2({ current: [{ merger_id: 'MN-1' }], completed: [] });

    const first = renderHook(() => useTracking(), { wrapper });
    act(() => {
      first.result.current.toggleAutoTrackPhase2();
    });
    await waitFor(() => {
      expect(first.result.current.trackedMergerIds).toContain('MN-1');
    });
    first.unmount();

    // Later visit: a new matter has entered Phase 2. The setting persists via
    // localStorage, so the new matter is auto-tracked too.
    mockFetchFromPhase2({ current: [{ merger_id: 'MN-1' }, { merger_id: 'MN-3' }], completed: [] });
    const second = renderHook(() => useTracking(), { wrapper });
    await waitFor(() => {
      expect(second.result.current.trackedMergerIds).toContain('MN-3');
    });
    expect(second.result.current.trackedMergerIds).toContain('MN-1');
  });
});
