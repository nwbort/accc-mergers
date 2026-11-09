import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import RecentEventsTimeline from '../RecentEventsTimeline';

// Australian noon on Tue 10 Nov 2026.
const NOW = new Date('2026-11-10T01:00:00Z');

const event = (n, type, day) => ({
  type,
  title: `Event ${n}`,
  date: `${day}T12:00:00Z`,
  merger_id: `MN-${n}`,
  merger_name: `Matter ${n}`,
});

const renderTimeline = (events) =>
  render(
    <MemoryRouter>
      <RecentEventsTimeline events={events} />
    </MemoryRouter>
  );

describe('RecentEventsTimeline', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(NOW);
  });
  afterEach(() => vi.useRealTimers());

  it('lists days newest first and bundles anything over a week old as Earlier', () => {
    renderTimeline([
      event(1, 'remedy_offer', '2026-10-30'),
      event(2, 'timeline_extension', '2026-11-09'),
      event(3, 'remedy_offer', '2026-11-06'),
    ]);
    const headings = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent);
    expect(headings).toEqual(['Yesterday', '4 days ago', 'Earlier']);
  });

  it('leaves out hidden types: notifications, phase 1 and waiver determinations, routine consultations', () => {
    renderTimeline([
      event(1, 'notified', '2026-11-09'),
      event(2, 'phase_1_determination', '2026-11-09'),
      event(3, 'waiver_determination', '2026-11-09'),
      event(4, 'questionnaire', '2026-11-09'),
      event(5, 'remedy_questionnaire', '2026-11-09'),
      event(6, 'phase_2_consultation', '2026-11-09'),
    ]);
    expect(screen.queryByText('Matter 1')).toBeNull();
    expect(screen.queryByText('Matter 2')).toBeNull();
    expect(screen.queryByText('Matter 3')).toBeNull();
    expect(screen.queryByText('Matter 4')).toBeNull();
    expect(screen.getByText('Matter 5')).toBeTruthy();
    expect(screen.getByText('Matter 6')).toBeTruthy();
  });

  it('renders nothing when every event is hidden', () => {
    const { container } = renderTimeline([event(1, 'notified', '2026-11-09')]);
    expect(container).toBeEmptyDOMElement();
  });

  it('collapses a busy day of one type into an expandable row', async () => {
    const user = userEvent.setup();
    renderTimeline([1, 2, 3].map((n) => event(n, 'timeline_extension', '2026-11-09')));
    const toggle = screen.getByRole('button', { name: '3 timeline extensions' });
    expect(screen.queryByText('Matter 1')).toBeNull();
    await user.click(toggle);
    const panel = document.getElementById(toggle.getAttribute('aria-controls'));
    expect(within(panel).getByText('Matter 1')).toBeTruthy();
  });

  it('lists the most significant type first within a day', () => {
    renderTimeline([
      event(1, 'timeline_extension', '2026-11-09'),
      event(2, 'phase_2_determination', '2026-11-09'),
    ]);
    const links = screen.getAllByRole('link').map((l) => l.textContent);
    expect(links[0]).toMatch(/Matter 2/);
  });
});
