import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import MergerTimeline from '../MergerTimeline';

describe('MergerTimeline', () => {
  beforeEach(() => {
    // Pin "now" so the today marker / progress fill is deterministic.
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-01T00:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders notification start and decision deadline while under assessment', () => {
    render(
      <MergerTimeline
        merger={{
          effective_notification_datetime: '2026-05-18T12:00:00Z',
          end_of_determination_period: '2026-07-01T12:00:00Z',
          status: 'Under assessment',
        }}
        duration={null}
        businessDuration={null}
        daysRemaining={30}
        businessDaysRemaining={21}
      />
    );

    expect(screen.getByText('Notified')).toBeInTheDocument();
    expect(screen.getByText('Decision due')).toBeInTheDocument();
    expect(screen.getByText('18/05/2026')).toBeInTheDocument();
    expect(screen.getByText('01/07/2026')).toBeInTheDocument();
    expect(screen.getByText('Today')).toBeInTheDocument();
    expect(screen.getByText('30 cal / 21 bus. days remaining')).toBeInTheDocument();
  });

  it('shows the original notification date when it differs from the effective one', () => {
    render(
      <MergerTimeline
        merger={{
          effective_notification_datetime: '2026-02-20T12:00:00Z',
          original_notification_datetime: '2026-02-06T12:00:00Z',
          end_of_determination_period: '2026-08-17T12:00:00Z',
          status: 'Under assessment',
        }}
        duration={null}
        businessDuration={null}
        daysRemaining={63}
        businessDaysRemaining={44}
      />
    );

    expect(screen.getByText('20/02/2026')).toBeInTheDocument();
    expect(screen.getByText(/originally 06\/02\/2026/i)).toBeInTheDocument();
  });

  it('ends at the published determination once complete', () => {
    render(
      <MergerTimeline
        merger={{
          effective_notification_datetime: '2026-05-18T12:00:00Z',
          end_of_determination_period: '2026-07-01T12:00:00Z',
          determination_publication_date: '2026-06-10T12:00:00Z',
          accc_determination: 'Approved',
          status: 'Assessment completed',
        }}
        duration={23}
        businessDuration={16}
        daysRemaining={0}
        businessDaysRemaining={0}
      />
    );

    expect(screen.getByText('Determination')).toBeInTheDocument();
    expect(screen.getByText('10/06/2026')).toBeInTheDocument();
    expect(screen.getByText('23 cal / 16 bus. days')).toBeInTheDocument();
    // No live "today" marker once the assessment is finished.
    expect(screen.queryByText('Today')).not.toBeInTheDocument();
  });

  it('falls back to a labelled view when no proportional axis is available', () => {
    render(
      <MergerTimeline
        merger={{
          effective_notification_datetime: null,
          original_notification_datetime: '2026-04-01T12:00:00Z',
          status: 'Assessment suspended',
        }}
        duration={null}
        businessDuration={null}
        daysRemaining={null}
        businessDaysRemaining={null}
      />
    );

    expect(screen.getByText(/None . assessment suspended/i)).toBeInTheDocument();
    expect(screen.getByText(/originally 01\/04\/2026/i)).toBeInTheDocument();
  });
});
