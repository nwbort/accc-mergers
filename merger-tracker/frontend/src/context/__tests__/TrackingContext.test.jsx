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

// Stub fetch for the Phase 2 auto-track tests: serves the Phase 2 feed from
// `phase2Ids` and per-merger details from `mergers` (404 for anything missing).
function mockFetchPhase2(phase2Ids, mergers = {}) {
  globalThis.fetch = vi.fn((url) => {
    if (/\/data\/phase-2-mergers\.json$/.test(url)) {
      return Promise.resolve(
        okResponse({ mergers: phase2Ids.map((id) => ({ merger_id: id })) })
      );
    }
    const match = /\/data\/mergers\/([^/]+)\.json$/.exec(url);
    if (match) {
      const merger = mergers[match[1]];
      return Promise.resolve(merger ? okResponse(merger) : notFoundResponse());
    }
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

describe('TrackingContext auto-tracking of Phase 2 mergers', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('does NOT track existing Phase 2 mergers on the first ever load (baseline only)', async () => {
    mockFetchPhase2(['MN-1', 'MN-2']);

    const { result } = renderHook(() => useTracking(), { wrapper });

    // Give the Phase 2 effect a chance to run.
    await waitFor(() => {
      expect(localStorage.getItem('merger_tracker_phase2_initialized')).toBe('1');
    });
    expect(result.current.trackedMergerIds).toEqual([]);
    // The baseline IDs are recorded as seen so they're never tracked later.
    expect(JSON.parse(localStorage.getItem('merger_tracker_phase2_seen'))).toEqual(
      expect.arrayContaining(['MN-1', 'MN-2'])
    );
  });

  it('auto-tracks a merger that becomes Phase 2 after the baseline was seeded', async () => {
    // First visit establishes the baseline (MN-1 already in Phase 2).
    mockFetchPhase2(['MN-1']);
    const first = renderHook(() => useTracking(), { wrapper });
    await waitFor(() => {
      expect(localStorage.getItem('merger_tracker_phase2_initialized')).toBe('1');
    });
    expect(first.result.current.trackedMergerIds).toEqual([]);
    first.unmount();

    // Later visit: MN-2 has since been referred to Phase 2.
    mockFetchPhase2(['MN-1', 'MN-2'], {
      'MN-2': {
        merger_id: 'MN-2',
        merger_name: 'Newly referred',
        events: [{ date: '2026-01-01', title: 'Subject to Phase 2 review' }],
      },
    });
    const second = renderHook(() => useTracking(), { wrapper });

    await waitFor(() => {
      expect(second.result.current.trackedMergerIds).toContain('MN-2');
    });
    // The pre-existing Phase 2 matter is still not tracked.
    expect(second.result.current.trackedMergerIds).not.toContain('MN-1');
  });

  it('surfaces an auto-tracked Phase 2 referral as an unseen notification (ping)', async () => {
    localStorage.setItem('merger_tracker_phase2_initialized', '1');
    localStorage.setItem('merger_tracker_phase2_seen', JSON.stringify(['MN-1']));

    mockFetchPhase2(['MN-1', 'MN-2'], {
      'MN-2': {
        merger_id: 'MN-2',
        merger_name: 'Newly referred',
        events: [{ date: '2026-01-01', title: 'Subject to Phase 2 review' }],
      },
    });

    const { result } = renderHook(() => useTracking(), { wrapper });

    await waitFor(() => {
      expect(result.current.unseenEvents.some((e) => e.merger_id === 'MN-2')).toBe(true);
    });
    expect(result.current.unseenCount).toBeGreaterThan(0);
  });

  it('does not re-track a Phase 2 merger the user has untracked', async () => {
    // MN-2 was already auto-tracked-and-untracked: it's in the seen set but not tracked.
    localStorage.setItem('merger_tracker_phase2_initialized', '1');
    localStorage.setItem('merger_tracker_phase2_seen', JSON.stringify(['MN-1', 'MN-2']));

    mockFetchPhase2(['MN-1', 'MN-2']);

    const { result } = renderHook(() => useTracking(), { wrapper });

    // Let the effect run; MN-2 must stay untracked.
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.trackedMergerIds).not.toContain('MN-2');
  });
});
