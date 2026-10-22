import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import Quarterly from '../Quarterly';
import { dataCache } from '../../utils/dataCache';

// Assertions read rendered figures and the sr-only data tables, never the
// canvas, so the chart component is stubbed (see CurrentStatus.test.jsx for
// the jsdom resize crash a live Chart.js instance trips on re-render).
vi.mock('react-chartjs-2', () => ({ Bar: () => null, Line: () => null }));

function ok(json) {
  return { ok: true, status: 200, json: () => Promise.resolve(json) };
}

const BUCKETS = ['0–4', '5–9', '10–14', '15–19', '20–24', '25–29', '30–49', '50+'];

function block(key, label, { filed, decided, p1Median, wMedian, preMedian = 15, milestones = [], findings = [], appeals = null }) {
  return {
    quarter: key,
    label,
    start: `${key.slice(0, 4)}-0${(Number(key.slice(-1)) - 1) * 3 + 1}-01`.replace('-010-', '-10-'),
    end: '2026-09-30',
    notifications: {
      filed,
      phase_1_decided: 40,
      cleared: 39,
      referred_to_phase_2: 1,
      refused: 0,
      ceased: 0,
      clearance_rate: 39 / 40,
      timing: { count: 40, median: p1Median, average: 20, p90: 30, buckets: [0, 0, 0, 30, 6, 2, 2, 0] },
      average_cleared: 19.5,
      average_referred: 42,
    },
    waivers: {
      decided,
      granted: decided - 4,
      refused: 4,
      refused_refiled: 1,
      clearance_rate: (decided - 4) / decided,
      timing: { count: decided, median: wMedian, average: 15, p90: 21, buckets: [0, 10, 40, decided - 60, 10, 0, 0, 0] },
      average_granted: 15.1,
      average_refused: 18.9,
    },
    pre_notification: {
      count: filed, median: preMedian, average: 18.4, p90: 36, buckets: [2, 20, filed - 40, 12, 4, 2],
    },
    matters: filed + decided,
    overseas_party: 50,
    industries: [
      { code: 'K', name: 'Financial and Insurance Services', count: 40 },
      { code: 'C', name: 'Manufacturing', count: 20 },
    ],
    milestones,
    findings,
    appeals: appeals ?? { lodged: 0, concluded: 0, open_at_end: 0, matters: [] },
  };
}

const FIXTURE = {
  as_at: '2026-10-22',
  duration_buckets: BUCKETS,
  pre_notification_buckets: ['0', '1–10', '11–20', '21–40', '41–60', '61+'],
  quarters: [
    block('2026-Q2', 'Q2 2026', { filed: 95, decided: 176, p1Median: 17, wMedian: 12, preMedian: 14.5 }),
    block('2026-Q3', 'Q3 2026', {
      filed: 113,
      decided: 183,
      p1Median: 18,
      wMedian: 17,
      preMedian: 16,
      appeals: {
        lodged: 1,
        concluded: 0,
        open_at_end: 1,
        matters: [{
          tribunal_number: 'ACT 1 of 2026',
          tribunal_url: 'https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026',
          merger_id: 'MN-01068',
          merger_name: 'Coles – Kalgoorlie',
          appellant: 'Coles',
          filed_date: '2026-07-15',
          note: 'Lodged this quarter; open at quarter end; hearing listed for 9 Nov 2026',
        }],
      },
      findings: [
        '113 notifications filed, up 19% on Q2 2026, and 183 waiver applications decided, up 4% on Q2 2026.',
        '1 matter referred to phase 2; 1 phase 2 review concluded (1 not approved).',
      ],
      milestones: [
        { merger_id: 'MN-01068', merger_name: 'Coles – Kalgoorlie', kind: 'phase_2_outcome', date: '2026-07-01', detail: 'Not approved' },
        { merger_id: 'MN-01068', merger_name: 'Coles – Kalgoorlie', kind: 'tribunal_application', date: '2026-07-15', detail: 'Coles' },
      ],
    }),
  ],
};

function renderPage(initialEntry = '/quarterly') {
  vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
    if (url.includes('quarterly.json')) return Promise.resolve(ok(FIXTURE));
    return Promise.reject(new Error(`Unexpected fetch: ${url}`));
  });
  return render(
    <HelmetProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Quarterly />
      </MemoryRouter>
    </HelmetProvider>
  );
}

async function ready() {
  await waitFor(() => {
    expect(screen.getByRole('heading', { level: 1, name: 'Quarterly report' })).toBeInTheDocument();
  });
}

describe('Quarterly report', () => {
  beforeEach(() => {
    dataCache.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  it('opens on the latest quarter', async () => {
    renderPage();
    await ready();
    expect(screen.getByRole('button', { name: 'Q3 2026', pressed: true })).toBeInTheDocument();
    expect(screen.getByText(/1 July 2026/)).toBeInTheDocument();
  });

  it('leads with the quarter in brief, compared with the one before', async () => {
    renderPage();
    await ready();
    const brief = screen.getByRole('heading', { name: 'The quarter in brief' }).parentElement;
    expect(within(brief).getByText(/113 notifications filed, up 19% on Q2 2026/)).toBeInTheDocument();
    expect(within(brief).getByText(/1 phase 2 review concluded \(1 not approved\)/)).toBeInTheDocument();
  });

  it('colours a slower median as adverse', async () => {
    renderPage();
    await ready();
    expect(screen.getByText('5 days slower than Q2 2026')).toHaveClass('text-declined-dark');
  });

  it('lists post-phase-1 milestones with links to the matter', async () => {
    renderPage();
    await ready();
    const list = screen.getByRole('heading', { name: 'Beyond phase 1' }).closest('section');
    const links = within(list).getAllByRole('link', { name: 'Coles – Kalgoorlie' });
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute('href', expect.stringMatching(/^\/mergers\/MN-01068/));
    expect(within(list).getByText('Tribunal review sought')).toBeInTheDocument();
  });

  it('switches quarter, with no quarter in progress on offer', async () => {
    const user = userEvent.setup();
    renderPage();
    await ready();
    expect(screen.queryByRole('button', { name: 'Q4 2026' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Q2 2026' }));
    expect(screen.getByText('Nothing went beyond phase 1 this quarter.')).toBeInTheDocument();
    expect(screen.getByText('No Tribunal reviews were live this quarter.')).toBeInTheDocument();
    expect(screen.queryByText(/to date/)).not.toBeInTheDocument();
  });

  it('lists Tribunal reviews, linking out to the Tribunal and in to the merger', async () => {
    renderPage();
    await ready();
    const card = screen.getByRole('heading', { name: 'Tribunal reviews' }).closest('section');
    expect(within(card).getByRole('link', { name: /ACT 1 of 2026/ })).toHaveAttribute(
      'href',
      'https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026'
    );
    expect(within(card).getByRole('link', { name: 'Coles – Kalgoorlie' })).toHaveAttribute(
      'href',
      expect.stringMatching(/^\/mergers\/MN-01068/)
    );
    expect(within(card).getByText(/hearing listed for 9 Nov 2026/)).toBeInTheDocument();
    expect(within(card).getByText('Open at quarter end').nextSibling).toHaveTextContent('1');
  });

  it('links card headings into the rest of the site', async () => {
    renderPage();
    await ready();
    const href = (name) => screen.getByRole('link', { name }).getAttribute('href');
    expect(href('Volume by quarter')).toBe('/analysis');
    expect(href('Pre-notification')).toBe('/current-status');
    expect(href('Where the deals were')).toBe('/industries');
    expect(href('Beyond phase 1')).toBe('/phase-2');
    expect(href('re-filed as a notification')).toBe('/refiled-notifications');
  });

  it('honours a quarter named in the URL', async () => {
    renderPage('/quarterly?q=2026-Q2');
    await ready();
    expect(screen.getByRole('button', { name: 'Q2 2026', pressed: true })).toBeInTheDocument();
  });

  it('pairs each chart with a data table', async () => {
    renderPage();
    await ready();
    const volume = document.getElementById('chart-quarterly-volume-summary');
    expect(within(volume).getAllByRole('row')).toHaveLength(3);
    const waiverTiming = document.getElementById('chart-quarterly-waiver-timing-summary');
    expect(within(waiverTiming).getAllByRole('columnheader').map((th) => th.textContent)).toEqual([
      'Business days',
      'Q2 2026',
      'Q3 2026',
    ]);
  });
});

describe('Quarterly report pre-notification', () => {
  beforeEach(() => {
    dataCache.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  it('gives the median against the previous quarter, longer as adverse', async () => {
    renderPage();
    await ready();
    const card = screen.getByRole('heading', { name: 'Pre-notification' }).closest('section');
    expect(within(card).getByText(/113 notifications/)).toBeInTheDocument();
    expect(within(card).getByText('1.5 longer than Q2 2026')).toHaveClass('text-declined-dark');
    expect(within(card).getByText('90% within')).toBeInTheDocument();
  });

  it('pairs its chart with a data table over its own buckets', async () => {
    renderPage();
    await ready();
    const table = document.getElementById('chart-quarterly-pre-notification-summary');
    expect(within(table).getAllByRole('row')).toHaveLength(7);
    expect(within(table).getByText('61+')).toBeInTheDocument();
  });
});

describe('Quarterly report PDF link', () => {
  beforeEach(() => {
    dataCache.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  it('offers the quarter as a PDF', async () => {
    renderPage();
    await ready();
    expect(screen.getByRole('link', { name: 'Download PDF' })).toHaveAttribute(
      'href',
      '/data/reports/quarterly-report-2026-Q3.pdf'
    );
  });
});
