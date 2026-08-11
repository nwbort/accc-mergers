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

  it('omits the chart until a phase 2 review has concluded', async () => {
    renderDashboard(statsFixture({ by_phase_2_determination: {} }));

    // Wait for the page to render before asserting an absence.
    await waitFor(() => expect(screen.getByText('Phase 1 determinations')).toBeInTheDocument());
    expect(screen.queryByText('Phase 2 determinations')).not.toBeInTheDocument();
  });
});
