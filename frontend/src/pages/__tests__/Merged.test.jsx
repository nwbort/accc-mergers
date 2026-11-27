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
  share_text: '{matters} mergers. {refused} refused.\nI got {score} out of {total} on Australia Merged {year}\nhttps://mergers.fyi/merged',
  score_lines: { 0: 'None of them.', 1: 'One of three.', 2: 'Two of three.', 3: 'All three.' },
  quiz_total: 3,
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
      coda: 'But 1 came back.',
      coda_merger_id: 'MN-00002',
      months: [
        { month: 1, label: 'Jan', name: 'January', count: 37, partial: false },
        { month: 11, label: 'Nov', name: 'November', count: 45, partial: true },
      ],
      body: [],
    },
    {
      id: 'quiz-weekday',
      kind: 'quiz',
      index: 3,
      tone: 'tertiary-container',
      eyebrow: 'Guess · 1 of 3',
      question: 'One day, 13 matters landed at once. What day of the week was it?',
      options: [
        { key: 'Monday', label: 'Monday' },
        { key: 'Tuesday', label: 'Tuesday' },
        { key: 'Wednesday', label: 'Wednesday' },
        { key: 'Thursday', label: 'Thursday' },
        { key: 'Friday', label: 'Friday' },
        { key: 'Saturday', label: 'Saturday' },
        { key: 'Sunday', label: 'Sunday' },
      ],
      answer: 'Friday',
      answer_fill: 'navy',
      body: ['**Friday 14 August.** Fridays took 217 filings.'],
      weekdays: [
        { day: 'Monday', short: 'Mon', count: 139, weekend: false },
        { day: 'Friday', short: 'Fri', count: 217, weekend: false },
        { day: 'Sunday', short: 'Sun', count: 5, weekend: true },
      ],
    },
    {
      id: 'verdict',
      kind: 'stat',
      index: 4,
      tone: 'cleared',
      glyph: 'Approved',
      eyebrow: 'The verdict',
      stat: 99.7,
      stat_suffix: '%',
      heading: 'of decided notifications ended in clearance',
      body: ['**95.1%** of waiver applications were granted, [Alpha](/mergers/MN-00001) among them.'],
      coda: 'Almost.',
    },
    {
      id: 'quiz-one',
      kind: 'quiz',
      index: 5,
      tone: 'surface',
      eyebrow: 'Guess · 2 of 3',
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
      index: 6,
      tone: 'surface',
      eyebrow: 'Guess · 3 of 3',
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
      index: 7,
      tone: 'tertiary-container',
      eyebrow: 'Your year',
      heading: 'You followed {followed} this year.',
      body: ['Keep it up.'],
      industries_line: 'You followed {industries}: {names}.',
      empty_heading: "You didn't follow any matters this year.",
      empty_body: "There's always next year.",
    },
    {
      id: 'closing',
      kind: 'closing',
      index: 8,
      tone: 'primary',
      eyebrow: 'That was year one',
      heading: '896 matters',
      figures: [{ value: 99.3, suffix: '%', label: 'cleared' }],
      lede: 'See you in 2027.',
      share_label: 'Share your result',
      copy_label: 'Copy your result',
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
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => Promise.resolve(ok(fixture)));
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

  it('puts the week behind the busiest day, once it has been guessed', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');
    // Held back with the answer: the tallest bar is the answer.
    expect(screen.queryByRole('table', { name: /day of the week/i })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Friday' }));
    const table = screen.getByRole('table', { name: /day of the week/i });
    expect(within(table).getByRole('row', { name: /Monday 139/ })).toBeInTheDocument();
    // A weekend day is a sliver on the chart but an exact number in the table.
    expect(within(table).getByRole('row', { name: /Sunday 5/ })).toBeInTheDocument();
  });

  it('closes a card with its coda, after the body rather than before it', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');
    const verdict = document.querySelectorAll('[data-card]')[3];
    const text = verdict.textContent;
    expect(text).toContain('Almost.');
    // "Almost." is the turn after the reassurance, so it has to follow it.
    expect(text.indexOf('95.1%')).toBeLessThan(text.indexOf('Almost.'));
  });

  it('links a matter named in a sentence to its page', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');
    expect(screen.getByRole('link', { name: 'Alpha' })).toHaveAttribute(
      'href',
      '/mergers/MN-00001',
    );
  });

  it('links a coda that names a matter', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');
    expect(screen.getByRole('link', { name: 'But 1 came back.' })).toHaveAttribute(
      'href',
      '/mergers/MN-00002',
    );
  });

  it('puts the card in the URL without navigating the router', async () => {
    // The deck only rewrites a URL that is its own, so the browser has to be
    // on one. (MemoryRouter leaves jsdom's own location at "/".)
    window.history.replaceState({}, '', '/merged');
    renderMerged();
    await screen.findByText('Australia Merged');
    // A router navigation would be a pathname change, which ScrollToTop
    // answers by scrolling to the top — and the deck would walk itself back
    // to the first card. The URL is written with replaceState instead.
    const replace = vi.spyOn(window.history, 'replaceState');
    await userEvent.click(screen.getByRole('button', { name: 'Next card' }));
    expect(replace).toHaveBeenCalledWith(expect.anything(), '', '/merged/2');
  });

  it("leaves a URL that is not the deck's alone", async () => {
    window.history.replaceState({}, '', '/mergers/MN-00001');
    renderMerged();
    await screen.findByText('Australia Merged');
    const replace = vi.spyOn(window.history, 'replaceState');
    await userEvent.click(screen.getByRole('button', { name: 'Next card' }));
    // Following a merger link off the deck must not be undone by it.
    expect(replace).not.toHaveBeenCalled();
  });

  it('marks every card as a snap target', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');
    for (const card of document.querySelectorAll('[data-card]')) {
      expect(card.className).toContain('snap-start');
    }
  });

  it('leaves the document unsnapped once the deck unmounts', async () => {
    const { unmount } = renderMerged();
    await screen.findByText('Australia Merged');
    expect(document.documentElement.classList.contains('merged-snap')).toBe(true);
    unmount();
    expect(document.documentElement.classList.contains('merged-snap')).toBe(false);
  });

  // --- the reveal ----------------------------------------------------------

  it('holds an answer back until the question is answered', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');
    expect(screen.queryByText('Friday 14 August.')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Friday' }));
    expect(screen.getByText('Friday 14 August.')).toBeInTheDocument();
  });

  // --- the quiz ------------------------------------------------------------

  it('scores a right answer and shows the reveal', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');
    expect(screen.getByText('0 / 3')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Ampol' }));
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
    expect(screen.getByText('Correct')).toBeInTheDocument();
    expect(screen.getByText('Ampol: 147 business days.')).toBeInTheDocument();
  });

  it('scores a wrong answer without hiding which one was right', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');

    await userEvent.click(screen.getByRole('button', { name: 'Coles' }));
    expect(screen.getByText('0 / 3')).toBeInTheDocument();
    expect(screen.getByText('Not quite')).toBeInTheDocument();
    // The reveal still names the answer, so a wrong guess still teaches it.
    expect(screen.getByText('Ampol: 147 business days.')).toBeInTheDocument();
    // A short list keeps every option on screen, the right one among them.
    expect(screen.getByRole('button', { name: 'Ampol' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'MicroStar' })).toBeInTheDocument();
  });

  it("collapses a long option list to the reader's own pick", async () => {
    renderMerged();
    await screen.findByText('Australia Merged');
    // Seven days are a lot of dead pills to leave above the reveal.
    expect(screen.getByRole('button', { name: 'Wednesday' })).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Monday' }));

    expect(screen.getByRole('button', { name: 'Monday' })).toBeInTheDocument();
    for (const day of ['Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']) {
      expect(screen.queryByRole('button', { name: day })).not.toBeInTheDocument();
    }
    // What the pills stop saying, the reveal still says.
    expect(screen.getByText('Friday 14 August.')).toBeInTheDocument();
  });

  it('keeps the right answer on a collapsed card with no reveal copy', async () => {
    const bare = {
      ...fixture,
      cards: fixture.cards.map((card) =>
        card.id === 'quiz-weekday' ? { ...card, body: [], weekdays: undefined } : card,
      ),
    };
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => Promise.resolve(ok(bare)));
    renderMerged();
    await screen.findByText('Australia Merged');

    await userEvent.click(screen.getByRole('button', { name: 'Monday' }));

    // Nothing underneath would name it, so the winning pill stays put.
    expect(screen.getByRole('button', { name: 'Monday' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Friday' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Wednesday' })).not.toBeInTheDocument();
  });

  it('marks an answer that is not an outcome in its own colour', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');

    await userEvent.click(screen.getByRole('button', { name: 'Friday' }));
    await userEvent.click(screen.getByRole('button', { name: 'Ampol' }));

    // A day of the week has no cleared/refused reading, so it does not wear
    // the green that means "cleared" everywhere else in the deck.
    expect(screen.getByRole('button', { name: 'Friday' }).className).toContain('bg-blue-900');
    expect(screen.getByRole('button', { name: 'Ampol' }).className).toContain('bg-emerald-700');
  });

  it('takes one answer per question and no more', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');

    await userEvent.click(screen.getByRole('button', { name: 'Coles' }));
    await userEvent.click(screen.getByRole('button', { name: 'Ampol' }));
    // The second click lands on a disabled button, so the score stays put.
    expect(screen.getByText('0 / 3')).toBeInTheDocument();
  });

  it('withholds the closing line until every question is answered', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');

    await userEvent.click(screen.getByRole('button', { name: 'Ampol' }));
    await userEvent.click(screen.getByRole('button', { name: 'Blackstone' }));
    expect(screen.queryByText('One of three.')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Friday' }));
    expect(screen.getByText('Two of three.')).toBeInTheDocument();
  });

  it('builds the share line from the score and the data, not from a template', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');

    await userEvent.click(screen.getByRole('button', { name: 'Friday' }));
    await userEvent.click(screen.getByRole('button', { name: 'Ampol' }));
    await userEvent.click(screen.getByRole('button', { name: 'Coles Group' }));

    // Nothing is printed on the card; the text only exists on the clipboard,
    // reached through the one button the card ends on.
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    await userEvent.click(screen.getByRole('button', { name: /Share your result/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Copy your result' }));
    expect(writeText).toHaveBeenCalledWith(
      '896 mergers. 1 refused.\nI got 3 out of 3 on Australia Merged 2026\nhttps://mergers.fyi/merged',
    );
  });

  it('ends on one button, not a copy button beside a share button', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');

    await userEvent.click(screen.getByRole('button', { name: /Share your result/ }));
    // The menu it opens carries the copy, so the card needs no second pill.
    const menu = screen.getByRole('dialog', { name: /Share/ });
    expect(within(menu).getByRole('button', { name: 'Copy your result' })).toBeInTheDocument();
    expect(within(menu).getByRole('link', { name: /LinkedIn/ })).toBeInTheDocument();
    expect(within(menu).getByRole('link', { name: /Bluesky/ })).toBeInTheDocument();
  });

  it('starts the deck over without its answers', async () => {
    renderMerged();
    await screen.findByText('Australia Merged');
    await userEvent.click(screen.getByRole('button', { name: 'Friday' }));
    expect(screen.getByText('1 / 3')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Start again/ }));
    expect(screen.getByText('0 / 3')).toBeInTheDocument();
    // The question is askable again.
    expect(screen.getByRole('button', { name: 'Friday' })).toBeEnabled();
  });

  // --- the reader's own card ------------------------------------------------

  it('has something to say to a reader who followed nothing', async () => {
    renderMerged();
    expect(await screen.findByText("You didn't follow any matters this year.")).toBeInTheDocument();
    expect(screen.getByText("There's always next year.")).toBeInTheDocument();
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

  it('counts one follow in the singular', async () => {
    localStorage.setItem('merger_tracker_tracked', JSON.stringify(['MN-1']));
    localStorage.setItem(
      'merger_tracker_tracked_industries',
      JSON.stringify([{ code: '4520', name: 'Veterinary Services' }]),
    );
    renderMerged();
    expect(await screen.findByText('You followed 1 matter this year.')).toBeInTheDocument();
    // The industries line already read the singular; the matters line now does.
    expect(screen.getByText('You followed 1 industry: Veterinary Services.')).toBeInTheDocument();
  });

  // --- failure --------------------------------------------------------------

  it('says so rather than rendering an empty deck when the data will not load', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => Promise.reject(new Error('offline')));
    renderMerged();
    expect(await screen.findByText(/offline/i)).toBeInTheDocument();
  });
});
