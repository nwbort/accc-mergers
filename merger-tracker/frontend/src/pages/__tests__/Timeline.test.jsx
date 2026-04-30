import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import Timeline from '../Timeline';
import { dataCache } from '../../utils/dataCache';

function ok(json) {
  return { ok: true, status: 200, json: () => Promise.resolve(json) };
}

function makeEvents(count, pageNum) {
  return Array.from({ length: count }, (_, i) => ({
    merger_id: `M-${pageNum}-${i}`,
    merger_name: `Merger ${pageNum}-${i}`,
    title: `Event ${pageNum}-${i}`,
    display_title: `Event ${pageNum}-${i}`,
    date: `2024-${String(pageNum).padStart(2, '0')}-${String((i % 28) + 1).padStart(2, '0')}`,
  }));
}

function renderTimeline() {
  return render(
    <HelmetProvider>
      <MemoryRouter>
        <Timeline />
      </MemoryRouter>
    </HelmetProvider>
  );
}

function readShowingCount() {
  // The page shows "Showing X of Y events" while more events are available,
  // and "Showing all N events" once everything is loaded.
  const text = document.body.textContent || '';
  const partial = text.match(/Showing (\d+) of \d+ events/);
  if (partial) return Number(partial[1]);
  const all = text.match(/Showing all (\d+) events/);
  if (all) return Number(all[1]);
  return null;
}

describe('Timeline auto-load when last page is small', () => {
  beforeEach(() => {
    dataCache.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  it('auto-loads the previous page when the last page has too few events to scroll', async () => {
    // Mirrors the real bug: 503 events / 100 per page → only 3 events on
    // page 6, which won't fill the viewport so the scroll handler never
    // fires. The component should pull page 5 automatically.
    const lastPageEvents = makeEvents(3, 6);
    const prevPageEvents = makeEvents(100, 5);

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('timeline-meta.json')) {
        return Promise.resolve(ok({ total: 503, page_size: 100, total_pages: 6 }));
      }
      if (url.includes('timeline-page-6.json')) {
        return Promise.resolve(ok({ events: lastPageEvents }));
      }
      if (url.includes('timeline-page-5.json')) {
        return Promise.resolve(ok({ events: prevPageEvents }));
      }
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    });

    renderTimeline();

    await waitFor(() => {
      const urls = fetchSpy.mock.calls.map((c) => c[0]);
      expect(urls.some((u) => u.includes('timeline-page-5.json'))).toBe(true);
    });

    await waitFor(() => {
      const count = readShowingCount();
      expect(count).not.toBeNull();
      // 3 from page 6 + LOAD_MORE_COUNT (10) from page 5 = 13. The contract
      // we care about is "enough to scroll", i.e. at least the threshold.
      expect(count).toBeGreaterThanOrEqual(8);
    });
  });

  it('does not auto-load when the last page already has enough events to scroll', async () => {
    const lastPageEvents = makeEvents(100, 1);

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('timeline-meta.json')) {
        return Promise.resolve(ok({ total: 100, page_size: 100, total_pages: 1 }));
      }
      if (url.includes('timeline-page-1.json')) {
        return Promise.resolve(ok({ events: lastPageEvents }));
      }
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    });

    renderTimeline();

    // Events are reversed on display (stored ascending), so the highest
    // index appears first.
    await waitFor(() => {
      expect(screen.getByText('Merger 1-99')).toBeInTheDocument();
    });

    // Give any spurious auto-load a chance to fire — none should, because
    // the first slice already exceeds the threshold.
    await new Promise((resolve) => setTimeout(resolve, 50));

    const pageFetches = fetchSpy.mock.calls
      .map((c) => c[0])
      .filter((u) => u.includes('timeline-page-'));
    expect(pageFetches).toHaveLength(1);
  });

  it('keeps loading further pages if even the previous page does not push past the threshold', async () => {
    // Construct a degenerate case: last two pages are tiny. The auto-load
    // effect should chain until either the threshold is met or pages run out.
    const page3Events = makeEvents(2, 3);
    const page2Events = makeEvents(2, 2);
    const page1Events = makeEvents(100, 1);

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('timeline-meta.json')) {
        // total doesn't have to match for the component's logic — it only
        // reads total_pages.
        return Promise.resolve(ok({ total: 104, page_size: 100, total_pages: 3 }));
      }
      if (url.includes('timeline-page-3.json')) {
        return Promise.resolve(ok({ events: page3Events }));
      }
      if (url.includes('timeline-page-2.json')) {
        return Promise.resolve(ok({ events: page2Events }));
      }
      if (url.includes('timeline-page-1.json')) {
        return Promise.resolve(ok({ events: page1Events }));
      }
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    });

    renderTimeline();

    await waitFor(() => {
      const urls = fetchSpy.mock.calls.map((c) => c[0]);
      expect(urls.some((u) => u.includes('timeline-page-2.json'))).toBe(true);
    });

    await waitFor(() => {
      const count = readShowingCount();
      expect(count).not.toBeNull();
      expect(count).toBeGreaterThanOrEqual(8);
    });
  });
});
