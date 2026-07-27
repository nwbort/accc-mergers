import { render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import Analysis from '../Analysis';
import { dataCache } from '../../utils/dataCache';

function ok(json) {
  return { ok: true, status: 200, json: () => Promise.resolve(json) };
}

// Business-day durations chosen so the ECDF has clean, distinct jump points:
// 10, 10, 20, 30, 40 (completed) plus one in-progress matter that must be
// excluded from the curve entirely.
const analysisFixture = {
  phase1_duration: {
    durations: [
      { business_days: 10, calendar_days: 15, in_progress: false },
      { business_days: 10, calendar_days: 15, in_progress: false },
      { business_days: 20, calendar_days: 28, in_progress: false },
      { business_days: 30, calendar_days: 42, in_progress: false },
      { business_days: 40, calendar_days: 56, in_progress: false },
      { business_days: 5, calendar_days: 7, in_progress: true },
    ],
    stats: { average: 22, median: 20, min: 10, max: 40, count: 5 },
    calendar_stats: { average: 30, median: 28, min: 15, max: 56, count: 5 },
  },
  waiver_duration: {
    durations: [],
    stats: { average: null, median: null, min: null, max: null, count: 0 },
    calendar_stats: { average: null, median: null, min: null, max: null, count: 0 },
  },
  monthly_volume: { labels: ['2025-01'], notifications: [1], waivers: [0] },
  industry_phase1_duration: [],
};

function renderAnalysis() {
  return render(
    <HelmetProvider>
      <MemoryRouter>
        <Analysis />
      </MemoryRouter>
    </HelmetProvider>
  );
}

describe('Analysis phase 1 duration ECDF', () => {
  beforeEach(() => {
    dataCache.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  it('computes cumulative percentages from completed matters only, excluding in-progress ones', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('analysis.json')) return Promise.resolve(ok(analysisFixture));
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    });

    renderAnalysis();

    await waitFor(() => {
      expect(screen.getByText('Phase 1 duration: share of reviews concluded')).toBeInTheDocument();
    });

    const table = document.getElementById('chart-phase1-ecdf-summary');
    expect(table).toBeInTheDocument();

    // 5 completed matters, durations 10,10,20,30,40 -> jumps at 10 (2/5=40%),
    // 20 (3/5=60%), 30 (4/5=80%), 40 (5/5=100%). The in-progress matter at 5
    // business days must not appear as its own row or shift the totals.
    const rows = within(table).getAllByRole('row').slice(1); // drop header row
    const cellsFor = (row) => within(row).getAllByRole('cell').map((c) => c.textContent);

    expect(cellsFor(rows[0])).toEqual(['10', '40%', '2 of 5']);
    expect(cellsFor(rows[1])).toEqual(['20', '60%', '3 of 5']);
    expect(cellsFor(rows[2])).toEqual(['30', '80%', '4 of 5']);
    expect(cellsFor(rows[3])).toEqual(['40', '100%', '5 of 5']);
    expect(rows).toHaveLength(4);

    expect(within(table).queryByText('5')).not.toBeInTheDocument();
  });

  it('omits the ECDF section when there are no completed matters', async () => {
    const emptyFixture = {
      ...analysisFixture,
      phase1_duration: {
        ...analysisFixture.phase1_duration,
        durations: analysisFixture.phase1_duration.durations.filter((d) => d.in_progress),
      },
    };

    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('analysis.json')) return Promise.resolve(ok(emptyFixture));
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    });

    renderAnalysis();

    await waitFor(() => {
      expect(screen.getByText('Monthly notification volume')).toBeInTheDocument();
    });

    expect(screen.queryByText('Phase 1 duration: share of reviews concluded')).not.toBeInTheDocument();
  });
});

describe('Analysis waiver duration ECDF', () => {
  beforeEach(() => {
    dataCache.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  it('computes cumulative percentages for completed waivers', async () => {
    const fixture = {
      ...analysisFixture,
      waiver_duration: {
        durations: [
          { business_days: 10, calendar_days: 15 },
          { business_days: 20, calendar_days: 28 },
        ],
        stats: { average: 15, median: 15, min: 10, max: 20, count: 2 },
        calendar_stats: { average: 21.5, median: 21.5, min: 15, max: 28, count: 2 },
      },
    };

    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('analysis.json')) return Promise.resolve(ok(fixture));
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    });

    renderAnalysis();

    await waitFor(() => {
      expect(screen.getByText('Waiver duration: share of applications concluded')).toBeInTheDocument();
    });

    const table = document.getElementById('chart-waiver-ecdf-summary');
    const rows = within(table).getAllByRole('row').slice(1);
    const cellsFor = (row) => within(row).getAllByRole('cell').map((c) => c.textContent);

    expect(cellsFor(rows[0])).toEqual(['10', '50%', '1 of 2']);
    expect(cellsFor(rows[1])).toEqual(['20', '100%', '2 of 2']);
  });

  it('omits the waiver ECDF section when there are no completed waivers', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('analysis.json')) return Promise.resolve(ok(analysisFixture));
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    });

    renderAnalysis();

    await waitFor(() => {
      expect(screen.getByText('Monthly notification volume')).toBeInTheDocument();
    });

    expect(screen.queryByText('Waiver duration: share of applications concluded')).not.toBeInTheDocument();
  });
});
