import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import UpcomingEventsTimeline from '../UpcomingEventsTimeline';

const renderTimeline = (events) =>
  render(
    <MemoryRouter>
      <UpcomingEventsTimeline events={events} />
    </MemoryRouter>
  );

const makeEvent = (overrides) => ({
  type: 'consultation_due',
  event_type_display: 'Consultation responses due',
  date: '2026-06-30T12:00:00Z',
  merger_id: 'MN-00001',
  merger_name: 'Acme – Globex',
  status: 'Under assessment',
  stage: 'Phase 1 - initial assessment',
  ...overrides,
});

describe('UpcomingEventsTimeline', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-28T00:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders an empty state when there are no events', () => {
    renderTimeline([]);
    expect(screen.getByText('No upcoming events.')).toBeInTheDocument();
  });

  it('exposes each day as a heading under the section heading, for screen-reader navigation', () => {
    renderTimeline([
      makeEvent({ date: '2026-06-28T12:00:00Z', merger_id: 'MN-1' }),
      makeEvent({ date: '2026-06-29T12:00:00Z', merger_id: 'MN-2' }),
    ]);

    expect(screen.getByRole('heading', { level: 2, name: 'Upcoming events' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: 'Today' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: 'Tomorrow' })).toBeInTheDocument();
  });

  it('groups events by day with relative labels and the event date', () => {
    renderTimeline([
      makeEvent({ date: '2026-06-28T12:00:00Z', merger_id: 'MN-1' }),
      makeEvent({ date: '2026-06-29T12:00:00Z', merger_id: 'MN-2' }),
      makeEvent({ date: '2026-07-02T12:00:00Z', merger_id: 'MN-3' }),
    ]);

    expect(screen.getByText('Today')).toBeInTheDocument();
    expect(screen.getByText('Tomorrow')).toBeInTheDocument();
    expect(screen.getByText('In 4 days')).toBeInTheDocument();
    // Weekday label for the 4-days-out event.
    expect(screen.getByText('Thu 2 Jul')).toBeInTheDocument();
  });

  it('places multiple events under the same day heading', () => {
    renderTimeline([
      makeEvent({ date: '2026-06-30T12:00:00Z', merger_id: 'MN-A', merger_name: 'Alpha – Beta' }),
      makeEvent({
        date: '2026-06-30T12:00:00Z',
        merger_id: 'MN-B',
        merger_name: 'Gamma – Delta',
        type: 'determination_due',
      }),
    ]);

    // A single day heading, two events beneath it.
    expect(screen.getAllByText('In 2 days')).toHaveLength(1);
    expect(screen.getByText('Alpha – Beta')).toBeInTheDocument();
    expect(screen.getByText('Gamma – Delta')).toBeInTheDocument();
  });

  it('orders events within a day: determinations first, Phase 2 above Phase 1, then name', () => {
    renderTimeline([
      makeEvent({
        date: '2026-06-30T12:00:00Z',
        merger_id: 'MN-1',
        merger_name: 'Zeta – Consultation P1',
        type: 'consultation_due',
        stage: 'Phase 1 - initial assessment',
      }),
      makeEvent({
        date: '2026-06-30T12:00:00Z',
        merger_id: 'MN-2',
        merger_name: 'Alpha – Determination P1',
        type: 'determination_due',
        stage: 'Phase 1 - initial assessment',
      }),
      makeEvent({
        date: '2026-06-30T12:00:00Z',
        merger_id: 'MN-3',
        merger_name: 'Beta – Determination P2',
        type: 'determination_due',
        stage: 'Phase 2 - in-depth review',
      }),
      makeEvent({
        date: '2026-06-30T12:00:00Z',
        merger_id: 'MN-4',
        merger_name: 'Aardvark – Determination P2',
        type: 'determination_due',
        stage: 'Phase 2 - in-depth review',
      }),
    ]);

    // Three determination_due events collapse into a summary by default;
    // expand it to check the ordering underneath.
    fireEvent.click(screen.getByRole('button', { name: /3 determinations due/ }));

    const links = screen.getAllByRole('link');
    const names = links.map((link) => within(link).getByText(/–/).textContent);

    expect(names).toEqual([
      // Phase 2 determinations first, broken by merger name…
      'Aardvark – Determination P2',
      'Beta – Determination P2',
      // …then the Phase 1 determination…
      'Alpha – Determination P1',
      // …and consultations last.
      'Zeta – Consultation P1',
    ]);
  });

  it('labels by calendar day, not elapsed 24-hour periods', () => {
    // Afternoon on the 28th: an event at noon UTC on the 29th is under 24h away
    // but is still the next calendar day, so it must read "Tomorrow", not "Today".
    vi.setSystemTime(new Date('2026-06-28T13:00:00Z'));
    renderTimeline([makeEvent({ date: '2026-06-29T12:00:00Z' })]);

    expect(screen.getByText('Tomorrow')).toBeInTheDocument();
    expect(screen.queryByText('Today')).not.toBeInTheDocument();
  });

  it('labels events by type and links to the merger', () => {
    renderTimeline([
      makeEvent({ type: 'determination_due', merger_name: 'Acme – Globex' }),
    ]);

    const link = screen.getByRole('link', { name: /Acme – Globex/ });
    expect(link).toHaveAttribute('href', expect.stringContaining('MN-00001'));
    expect(within(link).getByText('Determination')).toBeInTheDocument();
  });

  it('renders a tribunal hearing event with its own label, ordered first in the day', () => {
    renderTimeline([
      makeEvent({
        date: '2026-06-30T12:00:00Z',
        merger_id: 'MN-D',
        merger_name: 'Zed – Determination',
        type: 'determination_due',
        stage: 'Phase 2 - in-depth review',
      }),
      makeEvent({
        date: '2026-06-30T12:00:00Z',
        merger_id: 'MN-H',
        merger_name: 'Coles – Kalgoorlie',
        type: 'tribunal_hearing',
        stage: 'Phase 2 - detailed assessment',
      }),
    ]);

    // Its own chip label is shown…
    const link = screen.getByRole('link', { name: /Coles – Kalgoorlie/ });
    expect(within(link).getByText('Tribunal hearing')).toBeInTheDocument();

    // …and a hearing outranks a determination within the same day.
    const links = screen.getAllByRole('link');
    const names = links.map((l) => within(l).getByText(/–/).textContent);
    expect(names).toEqual(['Coles – Kalgoorlie', 'Zed – Determination']);
  });

  it('collapses 3+ same-type events on a day into a summary, expandable on click', () => {
    renderTimeline([
      makeEvent({ date: '2026-06-30T12:00:00Z', merger_id: 'MN-1', merger_name: 'Alpha – One' }),
      makeEvent({ date: '2026-06-30T12:00:00Z', merger_id: 'MN-2', merger_name: 'Bravo – Two' }),
      makeEvent({ date: '2026-06-30T12:00:00Z', merger_id: 'MN-3', merger_name: 'Charlie – Three' }),
      makeEvent({ date: '2026-06-30T12:00:00Z', merger_id: 'MN-4', merger_name: 'Delta – Four' }),
    ]);

    const summary = screen.getByRole('button', { name: /4 consultations due/ });
    expect(summary).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText('Alpha – One')).not.toBeInTheDocument();

    fireEvent.click(summary);

    expect(summary).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('Alpha – One')).toBeInTheDocument();
    expect(screen.getByText('Delta – Four')).toBeInTheDocument();

    fireEvent.click(summary);
    expect(summary).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText('Alpha – One')).not.toBeInTheDocument();
  });

  it('points the summary button\'s aria-controls at the revealed events', () => {
    renderTimeline([
      makeEvent({ date: '2026-06-30T12:00:00Z', merger_id: 'MN-1', merger_name: 'Alpha – One' }),
      makeEvent({ date: '2026-06-30T12:00:00Z', merger_id: 'MN-2', merger_name: 'Bravo – Two' }),
      makeEvent({ date: '2026-06-30T12:00:00Z', merger_id: 'MN-3', merger_name: 'Charlie – Three' }),
    ]);

    const summary = screen.getByRole('button', { name: /3 consultations due/ });
    const controlsId = summary.getAttribute('aria-controls');
    expect(controlsId).toBeTruthy();

    fireEvent.click(summary);
    expect(document.getElementById(controlsId)).toContainElement(screen.getByText('Alpha – One'));
  });

  it('does not collapse a group of fewer than 3 same-type events', () => {
    renderTimeline([
      makeEvent({ date: '2026-06-30T12:00:00Z', merger_id: 'MN-1', merger_name: 'Alpha – One' }),
      makeEvent({ date: '2026-06-30T12:00:00Z', merger_id: 'MN-2', merger_name: 'Bravo – Two' }),
    ]);

    expect(screen.queryByRole('button', { name: /consultations due/ })).not.toBeInTheDocument();
    expect(screen.getByText('Alpha – One')).toBeInTheDocument();
    expect(screen.getByText('Bravo – Two')).toBeInTheDocument();
  });

  it('bundles events more than a week out into a single trailing "Later" entry', () => {
    renderTimeline([
      makeEvent({ date: '2026-06-29T12:00:00Z', merger_id: 'MN-1', merger_name: 'Alpha – Soon' }),
      // 8 and 12 days out: different calendar days, but both beyond the
      // 7-day cutoff, so both land under the same "Later" heading. Different
      // types so they don't fall into the 2+ collapse threshold.
      makeEvent({ date: '2026-07-06T12:00:00Z', merger_id: 'MN-2', merger_name: 'Bravo – Later', type: 'consultation_due' }),
      makeEvent({ date: '2026-07-10T12:00:00Z', merger_id: 'MN-3', merger_name: 'Charlie – Later', type: 'determination_due' }),
    ]);

    expect(screen.getByText('Tomorrow')).toBeInTheDocument();
    expect(screen.getByText('Alpha – Soon')).toBeInTheDocument();

    expect(screen.getAllByText('Later')).toHaveLength(1);
    expect(screen.getByText('Bravo – Later')).toBeInTheDocument();
    expect(screen.getByText('Charlie – Later')).toBeInTheDocument();
    // Date range spans the earliest to latest event in the bundle, not a
    // single weekday label.
    expect(screen.getByText('6 Jul – 10 Jul')).toBeInTheDocument();
  });

  it('collapses a group of just 2 same-type events within the combined "Later" entry', () => {
    // The Later entry already bundles a whole week, so it collapses a type
    // as soon as there's more than one, unlike the 3+ threshold used for an
    // individual day.
    renderTimeline([
      makeEvent({ date: '2026-07-06T12:00:00Z', merger_id: 'MN-1', merger_name: 'Alpha – One' }),
      makeEvent({ date: '2026-07-10T12:00:00Z', merger_id: 'MN-2', merger_name: 'Bravo – Two' }),
    ]);

    const summary = screen.getByRole('button', { name: /2 consultations due/ });
    expect(screen.queryByText('Alpha – One')).not.toBeInTheDocument();

    fireEvent.click(summary);
    expect(screen.getByText('Alpha – One')).toBeInTheDocument();
    expect(screen.getByText('Bravo – Two')).toBeInTheDocument();
  });

  it('does not collapse a single event within the combined "Later" entry', () => {
    renderTimeline([
      makeEvent({ date: '2026-07-06T12:00:00Z', merger_id: 'MN-1', merger_name: 'Alpha – One' }),
    ]);

    expect(screen.queryByRole('button', { name: /consultations due/ })).not.toBeInTheDocument();
    expect(screen.getByText('Alpha – One')).toBeInTheDocument();
  });

  it('shows only a chevron on a collapsed group, with no expand/collapse hint text', () => {
    renderTimeline([
      makeEvent({ date: '2026-06-30T12:00:00Z', merger_id: 'MN-1', merger_name: 'Alpha – One' }),
      makeEvent({ date: '2026-06-30T12:00:00Z', merger_id: 'MN-2', merger_name: 'Bravo – Two' }),
      makeEvent({ date: '2026-06-30T12:00:00Z', merger_id: 'MN-3', merger_name: 'Charlie – Three' }),
    ]);

    expect(screen.queryByText('Tap to expand')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /3 consultations due/ }));
    expect(screen.queryByText('Tap to collapse')).not.toBeInTheDocument();
  });
});
