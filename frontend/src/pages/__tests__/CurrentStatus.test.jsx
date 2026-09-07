import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import CurrentStatus from '../CurrentStatus';
import { dataCache } from '../../utils/dataCache';

// The assertions here are all about rendered figures and the chart's sr-only
// data table, never the canvas — so the chart component is stubbed out. That
// keeps the window-selector test honest: re-rendering with a live Chart.js
// instance trips a jsdom-only crash in its resize path (getComputedStyle on a
// detached canvas's null parent), which has nothing to do with the behaviour
// under test.
vi.mock('react-chartjs-2', () => ({
  Line: () => null,
  Bar: () => null,
  Scatter: () => null,
}));

function ok(json) {
  return { ok: true, status: 200, json: () => Promise.resolve(json) };
}

// The page fetches analysis.json but reads only these two blocks from it.
const caseloadFixture = {
  labels: ['2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07', '2026-08', '2026-09'],
  notifications: [22, 25, 32, 42, 41, 46, 37, 35],
  as_at: '2026-09-02',
};

function renderCurrentStatus() {
  return render(
    <HelmetProvider>
      <MemoryRouter>
        <CurrentStatus />
      </MemoryRouter>
    </HelmetProvider>
  );
}

describe('Current status', () => {
  const turnaroundFixture = {
    open_caseload: caseloadFixture,
    current_status: {
      as_at: '2026-09-02',
      windows: [
        {
          days: 30,
          notifications_filed: 36,
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
          notifications_filed: 111,
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
      // Keyed by filing date, so its own window list — and running slightly
      // shorter than baseline while the review clock runs longer.
      pre_notification: {
        windows: [
          { days: 30, median: 19, average: 21.7, p90: 37, min: 0, max: 88, count: 36, median_delta: -1 },
          { days: 90, median: 21, average: 26.5, p90: 43, min: 0, max: 120, count: 111, median_delta: 1 },
        ],
        all_time: { median: 20, average: 24.6, p90: 51, min: 0, max: 166, count: 227 },
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

  async function renderPage(payload = turnaroundFixture) {
    mockAnalysis(payload);
    const view = renderCurrentStatus();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Current status' })).toBeInTheDocument();
    });
    return view;
  }

  // "Waivers" also labels a chart legend entry and a column in the trend
  // chart's sr-only table, so headline assertions scope to their own panel.
  function headline(label) {
    return screen.getByText(label, { selector: 'p' }).parentElement;
  }

  it('leads with the recent median and how it sits against the baseline', async () => {
    await renderPage();

    const waiver = headline('Waiver');
    expect(within(waiver).getByText('17')).toBeInTheDocument();
    expect(within(waiver).getByText('4 business days slower than usual')).toBeInTheDocument();
  });

  it('phrases a faster-than-baseline window as faster, without a sign', async () => {
    await renderPage();

    const notifications = headline('Notification – phase 1');
    expect(within(notifications).getByText('18.5')).toBeInTheDocument();
    expect(within(notifications).getByText('1.5 business days faster than usual')).toBeInTheDocument();
  });

  it('colours a slower headline adverse and a faster one favourable', async () => {
    await renderPage();

    // Waivers are running slower than usual, notifications faster — the two
    // directions have to reach for different ends of the outcome palette.
    expect(within(headline('Waiver')).getByText('17')).toHaveClass('text-declined-dark');
    expect(
      within(headline('Notification – phase 1')).getByText('18.5')
    ).toHaveClass('text-cleared-dark');
  });

  it('gives the 90th percentile under each headline', async () => {
    await renderPage();

    expect(within(headline('Waiver')).getByText('90% within 21 BD')).toBeInTheDocument();
    expect(
      within(headline('Notification – phase 1')).getByText('90% within 27 BD')
    ).toBeInTheDocument();
  });

  it('states pre-notification in calendar days', async () => {
    await renderPage();

    expect(screen.getByText(/in pre-notification/)).toHaveTextContent(
      'Average 19 calendar days in pre-notification'
    );
  });

  it('switches every figure when another window is selected', async () => {
    const user = userEvent.setup();
    await renderPage();

    await user.click(screen.getByRole('button', { name: 'Last 90 days' }));

    expect(within(headline('Waiver')).getByText('15')).toBeInTheDocument();
    expect(within(headline('Waiver')).getByText('2 business days slower than usual')).toBeInTheDocument();
    expect(screen.getByText(/in pre-notification/)).toHaveTextContent(
      'Average 21 calendar days in pre-notification'
    );
    expect(screen.getByRole('button', { name: 'Last 90 days' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('says so plainly when a window has no decisions rather than showing a blank stat', async () => {
    await renderPage({
      ...turnaroundFixture,
      current_status: {
        ...turnaroundFixture.current_status,
        windows: [{
          days: 30,
          notifications_filed: 36,
          notifications: turnaroundFixture.current_status.windows[0].notifications,
          waivers: {
            median: null, average: null, p90: null, min: null, max: null,
            count: 0, median_delta: null,
          },
        }],
      },
    });

    expect(screen.getByText('Nothing decided in this window.')).toBeInTheDocument();
  });

  it('pairs each decision month with the caseload it came out of in the data table', async () => {
    await renderPage();

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
    await renderPage();

    const table = screen.getByRole('table', {
      name: /Median business days to decide by decision month/,
    });
    const september = within(table).getByRole('row', { name: /Sep 2026/ });
    expect(within(september).getAllByText('Not reported')).toHaveLength(2);
    expect(within(september).getAllByText('2')).toHaveLength(2);
  });

  it('hides pre-notification when the payload predates it, keeping the headlines', async () => {
    const { pre_notification: _dropped, ...withoutPre } = turnaroundFixture.current_status;
    await renderPage({ ...turnaroundFixture, current_status: withoutPre });

    expect(screen.queryByText(/in pre-notification/)).not.toBeInTheDocument();
    expect(within(headline('Waiver')).getByText('17')).toBeInTheDocument();
  });

  it('says the page is still generating when the payload predates the series', async () => {
    // A deployed analysis.json generated before current_status existed. The
    // whole page is this block, so there is nothing else to fall back to.
    mockAnalysis({ open_caseload: caseloadFixture });
    renderCurrentStatus();

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Current status' })).toBeInTheDocument();
    });

    expect(screen.getByText(/still being generated/)).toBeInTheDocument();
    expect(screen.queryByText(/business days/)).not.toBeInTheDocument();
  });
});
