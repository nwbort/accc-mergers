import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import Merged from '../Merged';
import { TrackingProvider } from '../../context/TrackingContext';
import { dataCache } from '../../utils/dataCache';

// The page draws whatever merged.json says it is: the figures and the
// sentences are both generated (scripts/generate/static_data/outputs/
// merged.py), so these tests are about the deck's *behaviour* — scoring,
// revealing, the reader's own card, and the accessibility the card format
// makes easy to get wrong — rather than about any particular number.

function ok(json) {
  return { ok: true, status: 200, json: () => Promise.resolve(json) };
}

const fixture = {
  year: 2026,
  as_at: '2026-11-27',
  complete: false,
  coverage: 'Figures cover 1 January to 27 November 2026; the year is not over.',
  share_text: '{matters} mergers. {refused} refused. I got {score}/{total} on Australia Merged',
  score_lines: { 0: 'You got none of them.', 1: 'You got one out of two.', 2: 'Both. Alarming.' },
  quiz_total: 2,
  facts: { volume: { matters: 896 }, outcomes: { refused: [{ merger_id: 'MN-1' }] } },
  cards: [
    {
      id: 'opening',
      kind: 'opening',
      index: 1,
      tone: 'primary',
      eyebrow: '2026 year in review',
      heading: 'Australia Merged',
      lede: 'Year one. **896 deals** went to the ACCC.',
      body: ['Almost.'],
    },
    {
      id: 'months',
      kind: 'months',
      index: 2,
      tone: 'surface',
      eyebrow: 'The shape of the year',
      heading: 'January was a trickle.',
      months: [
        { month: 1, label: 'Jan', name: 'January', count: 37, partial: false },
        { month: 11, label: 'Nov', name: 'November', count: 45, partial: true },
      ],
      body: [],
    },
    {
      id: 'busiest-day',
      kind: 'reveal',
      index: 3,
      tone: 'tertiary-container',
      glyph: 'Approved',
      eyebrow: 'Busiest day',
      heading: 'One day, 13 matters landed at once.',
      prompt: 'Which day?',
      answer: 'Friday 14 August',
      body: ['Fridays took 217 filings.'],
    },
    {
      id: 'quiz-one',
      kind: 'quiz',
      index: 4,
      tone: 'surface',
      eyebrow: 'Guess · 1 of 2',
      question: 'Which review took the longest?',
      options: [
        { key: 'MN-1', label: 'Ampol' },
        { key: 'MN-2', label: 'Coles' },
        { key: 'MN-3', label: 'MicroStar' },
      ],
      answer: 'MN-1',
      body: ['**Ampol: 147 business days.**'],
    },
    {
      id: 'quiz-two',
      kind: 'quiz',
      index: 5,
      tone: 'surface',
      eyebrow: 'Guess · 2 of 2',
      question: 'Who turned up most?',
      options: [
        { key: 'coles', label: 'Coles Group' },
        { key: 'avc', label: 'Australian Venue Co' },
        { key: 'blackstone', label: 'Blackstone' },
      ],
      answer: 'coles',
      body: ['**Coles Group: 21 matters.**'],
    },
    {
      id: 'your-year',
      kind: 'personal',
      index: 6,
      tone: 'tertiary-container',
      eyebrow: 'Your year',
      heading: 'You followed {followed} matters this year.',
      empty_heading: 'You followed nothing this year.',
      empty_body: 'Which is one way to do it.',
      note: 'Read from this browser alone.',
    },
    {
      id: 'closing',
      kind: 'closing',
      index: 7,
      tone: 'primary',
      eyebrow: 'That was year one',
      heading: '896 matters',
      figures: [{ value: 99.3, suffix: '%', label: 'cleared' }],
      lede: 'See you in 2027.',
    },
  ],
};

function renderMerged() {
  return render(
    <HelmetProvider>
      <MemoryRouter>
        <TrackingProvider>
          <Merged />
        </TrackingProvider>
      </MemoryRouter>
    </HelmetProvider>,
  );
}

describe('Australia Merged', () => {
  beforeEach(() => {
    dataCache.clear?.();
    localStorage.clear();
    global.fetch = vi.fn(() => Promise.resolve(ok(fixture)));
    // jsdom has neither, and the deck uses both to move between cards.
    window.IntersectionObserver = class {
      observe() {}
      disconnect() {}
    };
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.documentElement.classList.remove('merged-snap');
  });

  it('draws a card for everything merged.json lists', async () => {
    renderMerged();
    expect(await screen.findByText('Australia Merged')).toBeInTheDocument();
    expect(document.querySelectorAll('[data-card]')).toHaveLength(fixture.cards.length);
  });

  it('renders a generated sentence as markdown rather than literal asterisks', async () => {
    renderMerged();
    expect(await screen.findByText('896 deals')).toBeInTheDocument();
    expect(screen.queryByText(/\*\*/)).not.toBeInTheDocument();
  });

  // --- accessibility the card format makes easy to get wrong ---------------

  it('gives the whole deck one h1 and every card its own h2', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    // Every card bar the reveal-before-reveal has a visible heading.
    expect(screen.getAllByRole('heading', { level: 2 }).length).toBeGreaterThanOrEqual(5);
  });

  it('pairs the monthly chart with a data table, and says which month is short', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');
    const table = screen.getByRole('table', { name: /Matters filed per month/i });
    expect(within(table).getByRole('row', { name: /January 2026 37/ })).toBeInTheDocument();
    expect(within(table).getByRole('row', { name: /November 2026 45 \(month incomplete\)/ }))
      .toBeInTheDocument();
  });

  it('leaves the document unsnapped once the deck unmounts', async () => {
    const { unmount } = renderMerged();
    await screen.findByText('Australia Merged');
    expect(document.documentElement.classList.contains('merged-snap')).toBe(true);
    unmount();
    expect(document.documentElement.classList.contains('merged-snap')).toBe(false);
  });

  // --- the reveal ----------------------------------------------------------

  it('holds a reveal back until it is asked for', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');
    expect(screen.queryByText('Friday 14 August')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Which day?' }));
    expect(screen.getByText('Friday 14 August')).toBeInTheDocument();
  });

  // --- the quiz ------------------------------------------------------------

  it('scores a right answer and shows the reveal', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');
    expect(screen.getByText('0 / 2')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Ampol' }));
    expect(screen.getByText('1 / 2')).toBeInTheDocument();
    expect(screen.getByText('Correct')).toBeInTheDocument();
    expect(screen.getByText('Ampol: 147 business days.')).toBeInTheDocument();
  });

  it('scores a wrong answer without hiding which one was right', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');

    await userEvent.click(screen.getByRole('button', { name: 'Coles' }));
    expect(screen.getByText('0 / 2')).toBeInTheDocument();
    expect(screen.getByText('Not quite')).toBeInTheDocument();
    // The reveal still names the answer, so a wrong guess still teaches it.
    expect(screen.getByText('Ampol: 147 business days.')).toBeInTheDocument();
  });

  it('takes one answer per question and no more', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');

    await userEvent.click(screen.getByRole('button', { name: 'Coles' }));
    await userEvent.click(screen.getByRole('button', { name: 'Ampol' }));
    // The second click lands on a disabled button, so the score stays put.
    expect(screen.getByText('0 / 2')).toBeInTheDocument();
  });

  it('withholds the closing line until every question is answered', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');

    await userEvent.click(screen.getByRole('button', { name: 'Ampol' }));
    expect(screen.queryByText('You got one out of two.')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Blackstone' }));
    expect(screen.getByText('You got one out of two.')).toBeInTheDocument();
  });

  it('builds the share line from the score and the data, not from a template', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');

    await userEvent.click(screen.getByRole('button', { name: 'Ampol' }));
    await userEvent.click(screen.getByRole('button', { name: 'Coles Group' }));
    expect(
      screen.getByText('896 mergers. 1 refused. I got 2/2 on Australia Merged → mergers.fyi/merged'),
    ).toBeInTheDocument();
  });

  // --- the reader's own card ------------------------------------------------

  it('has something to say to a reader who followed nothing', async () => {
    renderMerged();
    expect(await screen.findByText('You followed nothing this year.')).toBeInTheDocument();
    expect(screen.getByText('Which is one way to do it.')).toBeInTheDocument();
  });

  it('counts the follows this browser already holds', async () => {
    localStorage.setItem('merger_tracker_tracked', JSON.stringify(['MN-1', 'MN-2', 'MN-3']));
    localStorage.setItem(
      'merger_tracker_tracked_industries',
      JSON.stringify([{ code: '4520', name: 'Veterinary Services' }]),
    );
    renderMerged();
    expect(await screen.findByText('You followed 3 matters this year.')).toBeInTheDocument();
    expect(screen.getByText(/Veterinary Services/)).toBeInTheDocument();
  });

  // --- failure --------------------------------------------------------------

  it('says so rather than rendering an empty deck when the data will not load', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('offline')));
    renderMerged();
    expect(await screen.findByText(/offline/i)).toBeInTheDocument();
  });
});
