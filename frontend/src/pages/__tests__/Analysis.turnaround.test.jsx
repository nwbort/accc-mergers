import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import Analysis from '../Analysis';
import { dataCache } from '../../utils/dataCache';

// The turnaround assertions are all about the rendered figures and the chart's
// sr-only data table, never the canvas — so the chart components are stubbed
// out. That keeps the window-selector test honest: re-rendering the page with
// live Chart.js instances trips a jsdom-only crash in Chart.js's resize path
// (getComputedStyle on a detached canvas's null parent), which has nothing to
// do with the behaviour under test.
vi.mock('react-chartjs-2', () => ({
  Line: () => null,
  Bar: () => null,
  Scatter: () => null,
}));

function ok(json) {
  return { ok: true, status: 200, json: () => Promise.resolve(json) };
}

// Only the fields the turnaround section and its siblings read; the page's
// other charts are stubbed, so their payloads just need to be well-formed.
const analysisFixture = {
  phase1_duration: {
    durations: [{ business_days: 10, calendar_days: 15, in_progress: false }],
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

describe('Analysis current turnaround', () => {
  // Waivers running slower than their all-time median, notifications faster:
  // the two directions the delta sentence has to phrase differently.
  const turnaroundFixture = {
    ...analysisFixture,
    current_turnaround: {
      as_at: '2026-09-02',
      windows: [
        {
          days: 30,
          notifications: {
            median: 18.5, average: 21, p90: 27, min: 15, max: 56,
            count: 46, median_delta: -1.5,
          },
          waivers: {
            median: 17, average: 16.4, p90: 21, min: 8, max: 23,
            count: 64, median_delta: 4,
          },
        },
        {
          days: 90,
          notifications: {
            median: 18, average: 20.6, p90: 28, min: 15, max: 56,
            count: 116, median_delta: 0,
          },
          waivers: {
            median: 15, average: 15.2, p90: 21, min: 5, max: 24,
            count: 179, median_delta: 2,
          },
        },
      ],
      all_time: {
        notifications: { median: 20, average: 20, p90: 28, min: 8, max: 56, count: 206 },
        waivers: { median: 13, average: 13.3, p90: 19, min: 3, max: 24, count: 372 },
      },
      monthly: {
        labels: ['2026-07', '2026-08', '2026-09'],
        notifications: [
          { median: 17.5, average: 20.1, count: 38 },
          { median: 18, average: 21.3, count: 45 },
          { median: null, average: null, count: 2 },
        ],
        waivers: [
          { median: 15, average: 15.4, count: 52 },
          { median: 17, average: 16.9, count: 71 },
          { median: null, average: null, count: 2 },
        ],
        open_caseload: [46, 37, 35],
      },
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

  async function renderTurnaround(payload = turnaroundFixture) {
    mockAnalysis(payload);
    const view = renderAnalysis();
    await waitFor(() => {
      expect(screen.getByText('Current turnaround')).toBeInTheDocument();
    });
    return view;
  }

  // "Waivers" also labels one of the all-time summary cards at the top of the
  // page, so every panel assertion scopes to the turnaround section first.
  function panel(name) {
    const section = screen.getByText('Current turnaround').closest('section');
    return within(section).getByText(name, { selector: 'p' }).parentElement;
  }

  it('leads with the recent median and how it compares to the all-time one', async () => {
    await renderTurnaround();

    const waivers = panel('Waivers');
    expect(within(waivers).getByText('17')).toBeInTheDocument();
    expect(within(waivers).getByText('+4 BD')).toBeInTheDocument();
    expect(within(waivers).getByText(/slower than the all-time median of 13 BD/)).toBeInTheDocument();
  });

  it('phrases a faster-than-baseline window as faster, without a plus sign', async () => {
    await renderTurnaround();

    const notifications = panel('Notifications – phase 1');
    expect(within(notifications).getByText('18.5')).toBeInTheDocument();
    expect(within(notifications).getByText('−1.5 BD')).toBeInTheDocument();
    expect(within(notifications).getByText(/faster than the all-time median of 20 BD/)).toBeInTheDocument();
  });

  it('reports the tail and sample size an adviser needs to quote a range', async () => {
    await renderTurnaround();

    const waivers = panel('Waivers');
    expect(within(waivers).getByText('21 BD')).toBeInTheDocument();   // 9 in 10 within
    expect(within(waivers).getByText('8–23 BD')).toBeInTheDocument(); // range
    expect(within(waivers).getByText('64')).toBeInTheDocument();      // decided in window
  });

  it('switches the whole panel when another window is selected', async () => {
    const user = userEvent.setup();
    await renderTurnaround();

    await user.click(screen.getByRole('button', { name: 'Last 90 days' }));

    const waivers = panel('Waivers');
    expect(within(waivers).getByText('15')).toBeInTheDocument();
    expect(within(waivers).getByText('+2 BD')).toBeInTheDocument();
    expect(within(waivers).getByText('179')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Last 90 days' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Last 30 days' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('says so plainly when a window has no decisions rather than showing a blank stat', async () => {
    await renderTurnaround({
      ...turnaroundFixture,
      current_turnaround: {
        ...turnaroundFixture.current_turnaround,
        windows: [{
          days: 30,
          notifications: turnaroundFixture.current_turnaround.windows[0].notifications,
          waivers: {
            median: null, average: null, p90: null, min: null, max: null,
            count: 0, median_delta: null,
          },
        }],
      },
    });

    expect(screen.getByText('No matters decided in the last 30 days.')).toBeInTheDocument();
  });

  it('pairs each decision month with the caseload it came out of in the data table', async () => {
    await renderTurnaround();

    const table = screen.getByRole('table', {
      name: /Median business days to decide by decision month/,
    });
    const august = within(table).getByRole('row', { name: /Aug 2026/ });
    expect(within(august).getByText('18')).toBeInTheDocument();  // notifications median
    expect(within(august).getByText('45')).toBeInTheDocument();  // notifications decided
    expect(within(august).getByText('17')).toBeInTheDocument();  // waivers median
    expect(within(august).getByText('71')).toBeInTheDocument();  // waivers decided
    expect(within(august).getByText('37')).toBeInTheDocument();  // open caseload
  });

  it('marks a month held back for a thin sample as not reported, keeping its count', async () => {
    await renderTurnaround();

    const table = screen.getByRole('table', {
      name: /Median business days to decide by decision month/,
    });
    const september = within(table).getByRole('row', { name: /Sep 2026/ });
    expect(within(september).getAllByText('Not reported')).toHaveLength(2);
    expect(within(september).getAllByText('2')).toHaveLength(2);
  });

  it('renders the rest of the page when the payload predates the turnaround series', async () => {
    // A deployed analysis.json generated before current_turnaround existed.
    mockAnalysis(analysisFixture);
    renderAnalysis();

    await waitFor(() => {
      expect(screen.getByText('Monthly notification volume')).toBeInTheDocument();
    });

    expect(screen.queryByText('Current turnaround')).not.toBeInTheDocument();
  });
});
