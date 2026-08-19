import { render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import RefiledNotifications from '../RefiledNotifications';
import { dataCache } from '../../utils/dataCache';

function ok(json) {
  return { ok: true, status: 200, json: () => Promise.resolve(json) };
}

// A re-filed notification that was itself referred to Phase 2 (the MN-40017
// shape): Phase 1 ended at the referral, and the review now runs to the
// statutory Phase 2 deadline rather than to a determination.
const REFERRED_PAIR = {
  waiver_id: 'WA-85016',
  waiver_name: 'Vets Central – Hills Veterinary Centre',
  waiver_filed_date: '2026-03-16T12:00:00Z',
  waiver_declined_date: '2026-04-14T12:00:00Z',
  notification_id: 'MN-40017',
  notification_name: 'Vets Central – Hills Veterinary Centre',
  notification_filed_date: '2026-07-01T12:00:00Z',
  notification_status: 'Under assessment',
  notification_determination: null,
  notification_determination_date: null,
  notification_phase_1_determination: 'Referred to phase 2',
  notification_phase_1_end_date: '2026-08-18T12:00:00Z',
  notification_end_of_determination_period: '2027-01-12T12:00:00Z',
};

const PHASE_1_PAIR = {
  waiver_id: 'WA-30010',
  waiver_name: 'MAG South Coast',
  waiver_filed_date: '2026-04-20T12:00:00Z',
  waiver_declined_date: '2026-05-15T12:00:00Z',
  notification_id: 'MN-65026',
  notification_name: "McCarroll's Automotive Group",
  notification_filed_date: '2026-07-22T12:00:00Z',
  notification_status: 'Under assessment',
  notification_determination: null,
  notification_determination_date: null,
  notification_phase_1_determination: null,
  notification_phase_1_end_date: null,
  notification_end_of_determination_period: '2026-09-02T12:00:00Z',
};

function payload(overrides = {}) {
  return {
    current: [PHASE_1_PAIR, REFERRED_PAIR],
    completed: [],
    count: { current: 2, completed: 0 },
    phase_1_clearance_rate: { cleared: 10, referred: 1, total: 11, rate: 0.909 },
    straight_phase_1_clearance_rate: { cleared: 159, referred: 8, total: 167, rate: 0.952 },
    phase_duration: null,
    straight_phase_duration: null,
    ...overrides,
  };
}

function renderPage(data) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(() => Promise.resolve(ok(data)));
  return render(
    <HelmetProvider>
      <MemoryRouter>
        <RefiledNotifications />
      </MemoryRouter>
    </HelmetProvider>
  );
}

// Each pair's timeline carries a descriptive aria-label, which is also the
// handle for the card it sits in (the merger IDs are split across elements).
function timelineFor(name) {
  return screen.findByRole('img', { name: new RegExp(`^Timeline for ${name}`) });
}

async function cardFor(name) {
  return (await timelineFor(name)).closest('li');
}

describe('RefiledNotifications', () => {
  beforeEach(() => {
    dataCache.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  it('reports the Phase 1 clearance rate against the straight-to-Phase-1 baseline', async () => {
    renderPage(payload());

    const card = (await screen.findByText('Phase 1 clearance rate')).closest('dl');
    expect(within(card).getByText('91%')).toBeInTheDocument();
    expect(within(card).getByText('95% filed as Phase 1 from the outset')).toBeInTheDocument();
  });

  it('shows a referred matter as being in Phase 2, running to its deadline', async () => {
    renderPage(payload());

    const card = await cardFor('Vets Central – Hills Veterinary Centre');
    expect(within(card).getByText('Referred to phase 2')).toBeInTheDocument();
    expect(within(card).getByText('Phase 2')).toBeInTheDocument();
    // The track ends at the statutory Phase 2 deadline, not at "today".
    expect(within(card).getByText('Due by')).toBeInTheDocument();
    expect(within(card).getByText('12 Jan 2027')).toBeInTheDocument();
    expect(await timelineFor('Vets Central – Hills Veterinary Centre')).toHaveAccessibleName(
      /referred to Phase 2 18 Aug 2026, determination due by 12 Jan 2027$/
    );
  });

  it('leaves a matter still in Phase 1 running to today', async () => {
    renderPage(payload());

    const card = await cardFor("McCarroll's Automotive Group");
    expect(within(card).getByText('Today')).toBeInTheDocument();
    expect(within(card).getByText('Ongoing')).toBeInTheDocument();
    expect(within(card).queryByText('Phase 2')).not.toBeInTheDocument();
    expect(within(card).queryByText('Referred to phase 2')).not.toBeInTheDocument();
  });

  it('draws the Phase 2 leg on a completed matter that went through Phase 2', async () => {
    const determined = {
      ...REFERRED_PAIR,
      notification_status: 'Assessment completed',
      notification_determination: 'Approved',
      notification_determination_date: '2026-12-10T12:00:00Z',
    };
    renderPage(payload({ current: [], completed: [determined], count: { current: 0, completed: 1 } }));

    const card = await cardFor('Vets Central – Hills Veterinary Centre');
    // The determination, not the referral, is what the badge and the track end
    // report once the matter is done.
    expect(within(card).getByText('Approved')).toBeInTheDocument();
    expect(within(card).getByText('Determined')).toBeInTheDocument();
    expect(within(card).getByText('10 Dec 2026')).toBeInTheDocument();
    expect(within(card).getByText('Phase 2')).toBeInTheDocument();
  });
});
