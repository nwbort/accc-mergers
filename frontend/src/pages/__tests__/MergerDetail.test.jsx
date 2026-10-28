import { render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import MergerDetail from '../MergerDetail';
import { TrackingProvider } from '../../context/TrackingContext';
import { dataCache } from '../../utils/dataCache';

// One ACCC decision can be taken to the Tribunal by more than one applicant —
// both parties to MN-65005 lodged their own — so the detail page lists every
// matter, not just the merger-level summary.

function ok(json) {
  return { ok: true, status: 200, json: () => Promise.resolve(json) };
}

function matter(number, appellant, filedDate, documentUrl) {
  return {
    tribunal_number: number,
    tribunal_url: `https://www.competitiontribunal.gov.au/current-matters/${number.toLowerCase().replaceAll(' ', '-')}`,
    appeal_type: 'party_denial',
    appellant,
    status: 'current',
    outcome: null,
    effective_determination: null,
    filed_date: filedDate,
    hearing_date: null,
    concluded_date: null,
    documents: [
      {
        date: filedDate,
        filed_by: appellant,
        description: 'Application to Tribunal for Review',
        confidentiality: 'Non-confidential',
        url: documentUrl,
      },
    ],
  };
}

function appealEvent(number, appellant, date) {
  return {
    date: `${date}T12:00:00Z`,
    title: 'Application for Review',
    display_title: 'Tribunal appeal – Application for Review',
    is_appeal: true,
    appeal_filed_by: appellant,
    appeal_confidentiality: 'Non-confidential',
    tribunal_number: number,
  };
}

function merger(appeals) {
  return {
    merger_id: 'MN-65005',
    merger_name: 'Insurance Australia Group – RAC Insurance',
    status: 'Assessment completed',
    stage: 'Phase 2 - detailed assessment',
    accc_determination: 'Not approved',
    determination_publication_date: '2026-09-23T12:00:00Z',
    effective_notification_datetime: '2026-03-01T12:00:00Z',
    acquirers: [],
    targets: [],
    anzsic_codes: [],
    under_appeal: true,
    appeal: {
      tribunal_number: appeals.map((a) => a.tribunal_number).join(' and '),
      tribunal_url: appeals[0].tribunal_url,
      appeal_type: 'party_denial',
      appellant: appeals.map((a) => a.appellant).join(' and '),
      status: 'current',
      filed_date: appeals[0].filed_date,
    },
    appeals,
    events: appeals.map((a) => appealEvent(a.tribunal_number, a.appellant, a.filed_date)),
  };
}

function renderMerger(data) {
  vi.spyOn(globalThis, 'fetch').mockImplementation((url) =>
    Promise.resolve(url.includes('/data/mergers/MN-65005') ? ok(data) : ok({}))
  );
  render(
    <HelmetProvider>
      <TrackingProvider>
        <MemoryRouter initialEntries={['/mergers/MN-65005']}>
          <Routes>
            <Route path="/mergers/:id" element={<MergerDetail />} />
            {/* The page redirects to its slug URL once loaded. */}
            <Route path="/mergers/:id/:slug" element={<MergerDetail />} />
          </Routes>
        </MemoryRouter>
      </TrackingProvider>
    </HelmetProvider>
  );
}

describe('MergerDetail tribunal appeals', () => {
  beforeEach(() => {
    dataCache.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  it('lists each tribunal matter with its own link and application', async () => {
    renderMerger(merger([
      matter('ACT 3 of 2026', 'IAG', '2026-10-01', 'https://example.test/iag.pdf'),
      matter('ACT 4 of 2026', 'RACWA', '2026-10-05', 'https://example.test/racwa.pdf'),
    ]));

    const heading = await screen.findByRole('heading', { name: 'Tribunal appeals' });
    const field = within(heading.parentElement);
    expect(field.getByRole('link', { name: /ACT 3 of 2026/ })).toHaveAttribute(
      'href', 'https://www.competitiontribunal.gov.au/current-matters/act-3-of-2026'
    );
    expect(field.getByRole('link', { name: /ACT 4 of 2026/ })).toHaveAttribute(
      'href', 'https://www.competitiontribunal.gov.au/current-matters/act-4-of-2026'
    );

    expect(screen.getByRole('link', { name: /appeal document filed by IAG/ }))
      .toHaveAttribute('href', 'https://example.test/iag.pdf');
    expect(screen.getByRole('link', { name: /appeal document filed by RACWA/ }))
      .toHaveAttribute('href', 'https://example.test/racwa.pdf');

    // Each timeline document says which matter it was filed in.
    expect(screen.getByText('RACWA · Non-confidential · ACT 4 of 2026')).toBeInTheDocument();
  });

  it('keeps the single-matter wording when there is one matter', async () => {
    renderMerger(merger([
      matter('ACT 3 of 2026', 'IAG', '2026-10-01', 'https://example.test/iag.pdf'),
    ]));

    const heading = await screen.findByRole('heading', { name: 'Tribunal appeal' });
    expect(within(heading.parentElement).getByRole('link', { name: /Ongoing/ }))
      .toHaveTextContent(/^Ongoing$/);
    expect(screen.getByText('IAG · Non-confidential')).toBeInTheDocument();
  });
});

// A Federal Court judicial review, as the pipeline publishes one read off the
// Commonwealth Courts Portal: NSD1310/2026, Coles' review of MN-01068.
function judicialReview(overrides = {}) {
  return {
    case_number: 'NSD1310/2026',
    case_url: 'https://www.comcourts.gov.au/file/Federal/P/nsd1310/2026/actions',
    applicant: 'Coles',
    filed_date: '2026-07-17',
    status: 'concluded',
    outcome: 'withdrawn',
    concluded_date: '2026-08-27',
    court: 'Federal Court of Australia, New South Wales Registry',
    listings: [
      {
        date: '2026-08-27', time: '8:30', reason: 'Administrative Listing', location: 'Chambers',
        outcome: 'Finalised - Discontinued/Withdrawn', hearing: false,
      },
    ],
    ...overrides,
  };
}

function reviewEvent(title, date, extra = {}) {
  return {
    date: `${date}T12:00:00Z`,
    title,
    display_title: `Federal Court – ${title}`,
    is_appeal: true,
    review_forum: 'federal_court',
    case_number: 'NSD1310/2026',
    ...extra,
  };
}

function mergerWithReview(review, { underReview = false } = {}) {
  const base = merger([matter('ACT 3 of 2026', 'IAG', '2026-07-15', 'https://example.test/iag.pdf')]);
  return {
    ...base,
    judicial_reviews: [review],
    judicial_review: { applicant: review.applicant, case_number: review.case_number, status: review.status },
    under_judicial_review: underReview,
    events: [
      ...base.events,
      reviewEvent('Originating Application for Judicial Review', '2026-07-17',
        { appeal_filed_by: 'Coles Supermarkets Australia Pty Limited' }),
      reviewEvent('Judgment [2026] FCA 1000', '2026-07-28',
        { url_gh: '/mergers/MN-65005/2026FCA1000.pdf', court_outcome: 'Adjourned - For review of progress' }),
      reviewEvent('Administrative Listing', '2026-08-27',
        { court_outcome: 'Finalised - Discontinued/Withdrawn' }),
    ],
  };
}

describe('MergerDetail judicial reviews', () => {
  beforeEach(() => {
    dataCache.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  it('states the review in the header and links the portal file', async () => {
    renderMerger(mergerWithReview(judicialReview()));
    const heading = await screen.findByRole('heading', { name: 'Judicial review' });
    expect(within(heading.parentElement).getByRole('link', { name: /Review discontinued/ }))
      .toHaveAttribute('href', 'https://www.comcourts.gov.au/file/Federal/P/nsd1310/2026/actions');
    // Concluded, so the header line doesn't carry it as a live status.
    expect(screen.queryByText('Under judicial review')).not.toBeInTheDocument();
  });

  it('carries a live review on the header line', async () => {
    renderMerger(mergerWithReview(
      judicialReview({ status: 'current', outcome: null, concluded_date: null }),
      { underReview: true },
    ));
    expect(await screen.findByText('Under judicial review')).toBeInTheDocument();
  });

  it('makes the whole review card the link to the portal, saying how it ended', async () => {
    renderMerger(mergerWithReview(judicialReview()));
    const card = await screen.findByRole('link', { name: /Judicial review requested by Coles on 17 July 2026/ });
    expect(card).toHaveAttribute('href', 'https://www.comcourts.gov.au/file/Federal/P/nsd1310/2026/actions');
    expect(card).toHaveTextContent('Federal Court of Australia · NSD1310/2026 · Review discontinued on 27 August 2026');
    expect(within(card).queryByText('Concluded')).not.toBeInTheDocument();
    expect(screen.queryByText('Courts Portal')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /court listing/ })).not.toBeInTheDocument();
  });

  it('gives a live review its next hearing on the card', async () => {
    const future = new Date();
    future.setDate(future.getDate() + 30);
    const date = `${future.getFullYear()}-${String(future.getMonth() + 1).padStart(2, '0')}-${String(future.getDate()).padStart(2, '0')}`;
    renderMerger(mergerWithReview(
      judicialReview({
        status: 'current', outcome: null, concluded_date: null,
        listings: [{ date, time: '10:15', reason: 'Case Management Hearing', location: 'Court 18A', hearing: true }],
      }),
      { underReview: true },
    ));
    const card = await screen.findByRole('link', { name: /Judicial review requested by Coles/ });
    expect(card).toHaveTextContent(/Next hearing .* · Case Management Hearing · 10:15 · Court 18A/);
  });

  it('puts the court listings on the timeline, collapsed with the Tribunal documents', async () => {
    renderMerger(mergerWithReview(judicialReview()));
    expect(await screen.findByRole('button', { name: 'Show 3 more Tribunal and Federal Court documents' }))
      .toBeInTheDocument();
    // The newest, the finalising listing, heads the run with its outcome.
    expect(screen.getByText('Federal Court – Administrative Listing')).toBeInTheDocument();
    expect(screen.getByText('Finalised - Discontinued/Withdrawn')).toBeInTheDocument();
  });
});
