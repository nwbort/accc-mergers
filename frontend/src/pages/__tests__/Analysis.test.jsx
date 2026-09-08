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
// 10, 10, 20, 30, 40. The histogram is analysis.json's nested count map,
// business days -> calendar days -> number of reviews with that exact pair,
// so the repeated 10 is a count of 2 rather than two entries.
const analysisFixture = {
  phase1_duration: {
    duration_histogram: {
      10: { 15: 2 },
      20: { 28: 1 },
      30: { 42: 1 },
      40: { 56: 1 },
    },
    stats: { average: 22, median: 20, min: 10, max: 40, count: 5 },
    calendar_stats: { average: 30, median: 28, min: 15, max: 56, count: 5 },
  },
  waiver_duration: {
    duration_histogram: {},
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

  it('computes cumulative percentages by expanding the duration histogram', async () => {
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
    // 20 (3/5=60%), 30 (4/5=80%), 40 (5/5=100%). The repeated 10 arrives as a
    // count of 2, so it must move the curve twice while getting one row.
    const rows = within(table).getAllByRole('row').slice(1); // drop header row
    const cellsFor = (row) => within(row).getAllByRole('cell').map((c) => c.textContent);

    expect(cellsFor(rows[0])).toEqual(['10', '40%', '2 of 5']);
    expect(cellsFor(rows[1])).toEqual(['20', '60%', '3 of 5']);
    expect(cellsFor(rows[2])).toEqual(['30', '80%', '4 of 5']);
    expect(cellsFor(rows[3])).toEqual(['40', '100%', '5 of 5']);
    expect(rows).toHaveLength(4);
  });

  it('omits the ECDF section when there are no completed matters', async () => {
    const emptyFixture = {
      ...analysisFixture,
      phase1_duration: {
        ...analysisFixture.phase1_duration,
        duration_histogram: {},
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
        duration_histogram: { 10: { 15: 1 }, 20: { 28: 1 } },
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

describe('Analysis open caseload', () => {
  const caseloadFixture = {
    ...analysisFixture,
    open_caseload: {
      labels: ['2026-06', '2026-07', '2026-08'],
      notifications: [41, 56, 52],
      as_at: '2026-08-19',
    },
  };

  beforeEach(() => {
    dataCache.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  function mockAnalysis(payload) {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('analysis.json')) return Promise.resolve(ok(payload));
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    });
  }

  it('shows the latest open caseload and its movement', async () => {
    mockAnalysis(caseloadFixture);
    renderAnalysis();

    await waitFor(() => {
      expect(screen.getByText(/Open caseload . notifications/)).toBeInTheDocument();
    });

    const openNow = screen.getByText('Open now').parentElement;
    expect(within(openNow).getByText('52')).toBeInTheDocument();
    expect(within(openNow).getByText('as at 19 Aug 2026')).toBeInTheDocument();

    const change = screen.getByText('Change').parentElement;
    expect(within(change).getByText('+11')).toBeInTheDocument();
    expect(within(change).getByText('since Jun 2026')).toBeInTheDocument();
  });

  it('compares against six months back once the series is long enough', async () => {
    mockAnalysis({
      ...analysisFixture,
      open_caseload: {
        labels: [
          '2026-01', '2026-02', '2026-03', '2026-04', '2026-05',
          '2026-06', '2026-07', '2026-08',
        ],
        notifications: [11, 22, 25, 32, 42, 41, 46, 52],
        as_at: '2026-08-19',
      },
    });
    renderAnalysis();

    await waitFor(() => {
      expect(screen.getByText(/Open caseload . notifications/)).toBeInTheDocument();
    });

    // Six months back from Aug 2026 is Feb 2026, at 22 open.
    const change = screen.getByText('Change').parentElement;
    expect(within(change).getByText('+30')).toBeInTheDocument();
    expect(within(change).getByText('since Feb 2026')).toBeInTheDocument();
  });

  it('falls back to the start of the series when less than six months exist', async () => {
    mockAnalysis(caseloadFixture);
    renderAnalysis();

    await waitFor(() => {
      expect(screen.getByText(/Open caseload . notifications/)).toBeInTheDocument();
    });

    const change = screen.getByText('Change').parentElement;
    expect(within(change).getByText('since Jun 2026')).toBeInTheDocument();
  });

  it('renders the rest of the page when the payload predates the caseload series', async () => {
    // A deployed analysis.json generated before open_caseload existed.
    mockAnalysis(analysisFixture);
    renderAnalysis();

    await waitFor(() => {
      expect(screen.getByText('Monthly notification volume')).toBeInTheDocument();
    });

    expect(screen.queryByText(/Open caseload/)).not.toBeInTheDocument();
  });
});
