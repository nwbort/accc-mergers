import { render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import Dashboard from '../Dashboard';
import { dataCache } from '../../utils/dataCache';

function ok(json) {
  return { ok: true, status: 200, json: () => Promise.resolve(json) };
}

// chart.js can't paint in jsdom, so the doughnuts are asserted through the
// sr-only summary tables they're described by — the same data, in the form
// screen readers get it.
function statsFixture(overrides = {}) {
  return {
    total_mergers: 10,
    total_waivers: 4,
    by_status: { 'Under assessment': 2 },
    by_determination: { Approved: 6, 'Referred to phase 2': 3 },
    by_phase_2_determination: {
      'Assessment ceased': 1,
      'Not approved': 1,
      'Approved with conditions': 1,
    },
    by_waiver_determination: { Approved: 4 },
    phase_duration: { average_business_days: 20, median_business_days: 18 },
    ...overrides,
  };
}

function renderDashboard(stats) {
  vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
    if (url.includes('stats.json')) return Promise.resolve(ok(stats));
    if (url.includes('upcoming-events.json')) return Promise.resolve(ok({ events: [] }));
    return Promise.resolve(ok({}));
  });
  return render(
    <HelmetProvider>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </HelmetProvider>
  );
}

describe('Dashboard phase 2 determination chart', () => {
  beforeEach(() => {
    dataCache.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  it('charts conditional approvals and ceased assessments as their own outcomes', async () => {
    renderDashboard(statsFixture());

    const summary = await screen.findByRole('table', {
      name: /Phase 2 determination breakdown/,
    });
    const rows = within(summary).getAllByRole('row').slice(1); // drop the header
    // Fixed cleared → blocked → withdrawn order, whatever order stats.json
    // happens to list the outcomes in.
    expect(rows.map((row) => row.textContent)).toEqual([
      'Approved with conditions1',
      'Not approved1',
      'Assessment ceased1',
    ]);
  });

  // `sr-only`'s width: 1px is only a minimum for a table box, so an sr-only
  // table lays out at its full content width and, being absolutely positioned,
  // widens the whole page on mobile. The clipping has to happen on a div.
  it('hides each chart summary table behind an sr-only wrapper, not on the table', async () => {
    renderDashboard(statsFixture());

    const summaries = await screen.findAllByRole('table', { hidden: true });
    expect(summaries).toHaveLength(3);
    for (const table of summaries) {
      expect(table).not.toHaveClass('sr-only');
      expect(table.parentElement).toHaveClass('sr-only');
    }
  });

  it('omits the chart until a phase 2 review has concluded', async () => {
    renderDashboard(statsFixture({ by_phase_2_determination: {} }));

    // Wait for the page to render before asserting an absence.
    await waitFor(() => expect(screen.getByText('Phase 1 determinations')).toBeInTheDocument());
    expect(screen.queryByText('Phase 2 determinations')).not.toBeInTheDocument();
  });
});

describe('Dashboard head', () => {
  beforeEach(() => {
    dataCache.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  // The prerendered homepage carries the WebSite JSON-LD marked for Helmet
  // (data-rh), so Helmet drops it on mount unless <SEO> writes it again.
  it('keeps the WebSite JSON-LD in the head once mounted', async () => {
    renderDashboard(statsFixture());
    await waitFor(() => {
      const types = [...document.head.querySelectorAll('script[type="application/ld+json"]')]
        .flatMap((s) => [].concat(JSON.parse(s.textContent)))
        .map((d) => d['@type']);
      expect(types).toContain('WebSite');
    });
  });
});

describe('Dashboard first render', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  // main.jsx preloads stats.json into dataCache before mounting (routes.js);
  // the dashboard must read that same entry, or the spinner comes back.
  it('renders from the entry routes.js preloads, with no spinner', async () => {
    const { routeData } = await import('../../routes');
    const [[cacheKey]] = routeData('/');
    dataCache.set(cacheKey, statsFixture());
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('offline'));
    render(
      <HelmetProvider>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </HelmetProvider>
    );
    expect(screen.getByText('2 under assessment')).toBeInTheDocument();
  });

  // The event timelines sit above the charts: had either arrived after the
  // first render, it would have pushed the charts down. The preload carries
  // all three files, so with them in the cache the dashboard fetches nothing.
  it('preloads the event timelines too, so nothing loads in above the charts', async () => {
    const { routeData } = await import('../../routes');
    const entries = routeData('/');
    expect(entries.map(([, url]) => url)).toEqual(
      expect.arrayContaining(['/data/stats.json', '/data/upcoming-events.json', '/data/recent-events.json']),
    );
    for (const [cacheKey, url] of entries) {
      dataCache.set(cacheKey, url.endsWith('stats.json') ? statsFixture() : { events: [] });
    }
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('offline'));
    render(
      <HelmetProvider>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </HelmetProvider>
    );
    expect(screen.getByText('2 under assessment')).toBeInTheDocument();
    const fetched = fetchSpy.mock.calls.map(([url]) => String(url));
    for (const [, url] of entries) expect(fetched, url).not.toContain(url);
  });
});

describe('Dashboard fade-in', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  // Last in this file: marking the app settled is one-way, as in the app.
  it('fades in when navigated to, not when replacing the prerendered homepage', async () => {
    const { routeData } = await import('../../routes');
    const { markAppSettled } = await import('../../utils/appMount');
    const [[cacheKey]] = routeData('/');
    dataCache.set(cacheKey, statsFixture());
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('offline'));
    const wrapper = () => screen.getByText('2 under assessment').closest('.max-w-7xl');
    const mount = () =>
      render(
        <HelmetProvider>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </HelmetProvider>,
      );

    const first = mount();
    expect(wrapper()).not.toHaveClass('animate-fade-in');
    first.unmount();

    markAppSettled();
    mount();
    expect(wrapper()).toHaveClass('animate-fade-in');
  });
});
