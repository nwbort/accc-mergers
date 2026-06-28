import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
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

  it('labels events by type and links to the merger', () => {
    renderTimeline([
      makeEvent({ type: 'determination_due', merger_name: 'Acme – Globex' }),
    ]);

    const link = screen.getByRole('link', { name: /Acme – Globex/ });
    expect(link).toHaveAttribute('href', expect.stringContaining('MN-00001'));
    expect(within(link).getByText('Determination')).toBeInTheDocument();
  });
});
