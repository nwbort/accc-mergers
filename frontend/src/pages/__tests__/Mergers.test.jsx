import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Link, MemoryRouter, Route, Routes, useNavigate } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import Mergers from '../Mergers';
import { TrackingProvider } from '../../context/TrackingContext';
import { dataCache } from '../../utils/dataCache';
import { RESTORE_LIST_POSITION_STATE, saveListPosition } from '../../utils/mergerListPosition';

function ok(json) {
  return { ok: true, status: 200, json: () => Promise.resolve(json) };
}

// 200 matters, enough to run past the pages loaded automatically. Every
// tenth is a Phase 1 retail deal; the rest are wholesale waivers.
const MERGERS = Array.from({ length: 200 }, (_, i) => {
  const retail = i % 10 === 0;
  const day = String((i % 28) + 1).padStart(2, '0');
  return {
    merger_id: `${retail ? 'MN' : 'WA'}-${10000 + i}`,
    merger_name: `${retail ? 'Retail' : 'Wholesale'} deal ${String(i).padStart(3, '0')}`,
    status: 'Assessment completed',
    accc_determination: 'Approved',
    is_waiver: !retail,
    stage: retail ? 'Phase 1 - initial assessment' : 'Waiver application',
    effective_notification_datetime: `2026-0${(i % 9) + 1}-${day}T12:00:00Z`,
    determination_publication_date: `2026-0${(i % 9) + 1}-${day}T12:00:00Z`,
    latest_event_date: `2026-0${(i % 9) + 1}-${day}T12:00:00Z`,
    acquirers: [],
    targets: [],
    other_parties: [],
    anzsic_codes: [retail ? { code: '4000', name: 'Fuel Retailing' } : { code: '3600', name: 'Grocery Wholesaling' }],
  };
});

// jsdom has no IntersectionObserver. This one records what it watches, and
// scrollToEnd() reports the infinite-scroll sentinel as visible, as a reader
// reaching the bottom of the list would.
const observers = new Set();
class StubIntersectionObserver {
  constructor(callback) {
    this.callback = callback;
  }
  observe() {
    observers.add(this);
  }
  disconnect() {
    observers.delete(this);
  }
}

function scrollToEnd() {
  act(() => {
    observers.forEach((o) => o.callback([{ isIntersecting: true }]));
  });
}

// Stands in for the detail page: just a way back.
function GoBack() {
  const navigate = useNavigate();
  return <button type="button" onClick={() => navigate(-1)}>Back</button>;
}

let fetchSpy;

beforeEach(() => {
  dataCache.clear();
  sessionStorage.clear();
  observers.clear();
  vi.stubGlobal('IntersectionObserver', StubIntersectionObserver);
  window.matchMedia = window.matchMedia || (() => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
  fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => (
    url.includes('mergers/list.json')
      ? Promise.resolve(ok({ mergers: MERGERS }))
      : Promise.reject(new Error(`Unexpected fetch: ${url}`))
  ));
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function renderPage(entry = '/mergers') {
  return render(
    <HelmetProvider>
      <TrackingProvider>
        <MemoryRouter initialEntries={[entry]}>
          <Mergers />
        </MemoryRouter>
      </TrackingProvider>
    </HelmetProvider>
  );
}

describe('Mergers', () => {
  it('loads the whole list in one request', async () => {
    renderPage();
    expect(await screen.findByText(/^Showing \d+ of 200 mergers$/)).toBeInTheDocument();
    const listFetches = fetchSpy.mock.calls.filter(([url]) => url.includes('/data/mergers/'));
    expect(listFetches).toHaveLength(1);
  });

  it('loads the next 50 as the reader scrolls to the end of the list', async () => {
    renderPage();
    expect(await screen.findByText('Showing 50 of 200 mergers')).toBeInTheDocument();
    scrollToEnd();
    expect(screen.getByText('Showing 100 of 200 mergers')).toBeInTheDocument();
  });

  it('filters by industry division from the URL', async () => {
    renderPage('/mergers?industry=G');
    expect(await screen.findByText('Showing 20 of 20 mergers')).toBeInTheDocument();
  });

  it('shows each filter option with its count', async () => {
    const user = userEvent.setup();
    renderPage('/mergers?phase=waivers');
    await screen.findByText(/^Showing/);
    // A filter in the URL opens the panel only on wide screens.
    if (!screen.queryByLabelText('Industry')) {
      await user.click(screen.getByRole('button', { name: 'Toggle filters' }));
    }
    const industry = screen.getByLabelText('Industry');
    // Counted under the phase filter: only the 180 wholesale waivers remain.
    expect(within(industry).getByRole('option', { name: 'Wholesale Trade (180)' })).toBeInTheDocument();
    expect(within(industry).getByRole('option', { name: 'Retail Trade (0)' })).toBeInTheDocument();
    // The phase select's own counts ignore the phase filter.
    expect(within(screen.getByLabelText('Phase')).getByRole('option', { name: /^Phase 1.*\(20\)$/ })).toBeInTheDocument();
  });

  it('switches to a table whose headers sort the list', async () => {
    const user = userEvent.setup();
    renderPage('/mergers?view=table&industry=G');
    const table = await screen.findByRole('table');
    expect(within(table).getAllByRole('row')).toHaveLength(21);

    await user.click(within(table).getByRole('button', { name: 'Merger' }));
    const header = within(table).getByRole('columnheader', { name: 'Merger' });
    expect(header).toHaveAttribute('aria-sort', 'ascending');
    const firstRow = within(table).getAllByRole('row')[1];
    expect(within(firstRow).getByRole('link', { name: 'Retail deal 000' })).toBeInTheDocument();

    await user.click(within(table).getByRole('button', { name: 'Merger' }));
    expect(header).toHaveAttribute('aria-sort', 'descending');
  });

  it('comes back to as many pages as were showing when returning to the list', async () => {
    saveListPosition('', 4, 0);
    render(
      <HelmetProvider>
        <TrackingProvider>
          <MemoryRouter initialEntries={[{ pathname: '/mergers', state: RESTORE_LIST_POSITION_STATE }]}>
            <Mergers />
          </MemoryRouter>
        </TrackingProvider>
      </HelmetProvider>
    );
    expect(await screen.findByText('Showing 200 of 200 mergers')).toBeInTheDocument();
  });

  it('comes back to as many pages as were showing on Back', async () => {
    const user = userEvent.setup();
    render(
      <HelmetProvider>
        <TrackingProvider>
          <MemoryRouter initialEntries={['/mergers']}>
            <Routes>
              <Route path="/mergers" element={<Mergers />} />
              <Route path="/mergers/:id/:slug" element={<GoBack />} />
            </Routes>
          </MemoryRouter>
        </TrackingProvider>
      </HelmetProvider>
    );
    await screen.findByText('Showing 50 of 200 mergers');
    for (let i = 0; i < 3; i++) scrollToEnd();
    expect(screen.getByText('Showing 200 of 200 mergers')).toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: 'View merger details for Wholesale deal 171' }));
    await user.click(await screen.findByRole('button', { name: 'Back' }));
    expect(await screen.findByText('Showing 200 of 200 mergers')).toBeInTheDocument();
  });

  it('starts from the top on an ordinary visit', async () => {
    saveListPosition('', 4, 0);
    const user = userEvent.setup();
    render(
      <HelmetProvider>
        <TrackingProvider>
          <MemoryRouter initialEntries={['/']}>
            <Routes>
              <Route path="/" element={<Link to="/mergers">Mergers</Link>} />
              <Route path="/mergers" element={<Mergers />} />
            </Routes>
          </MemoryRouter>
        </TrackingProvider>
      </HelmetProvider>
    );
    // A link to the list, with no restore state: back to the first page.
    await user.click(screen.getByRole('link', { name: 'Mergers' }));
    expect(await screen.findByText('Showing 50 of 200 mergers')).toBeInTheDocument();
  });
});
