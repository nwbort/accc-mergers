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
      />
    );

    expect(screen.getByText('Notified')).toBeInTheDocument();
    expect(screen.getByText('Decision due')).toBeInTheDocument();
    expect(screen.getByText('18/05/2026')).toBeInTheDocument();
    expect(screen.getByText('01/07/2026')).toBeInTheDocument();
    expect(screen.getByText('Today')).toBeInTheDocument();
    expect(screen.getByText(/days remaining/)).toBeInTheDocument();
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
      />
    );

    expect(screen.getByText('20/02/2026')).toBeInTheDocument();
    expect(screen.getByText(/originally 06\/02\/2026/i)).toBeInTheDocument();
  });

  it('ends on the decision deadline once complete, with the determination as a marker', () => {
    render(
      <MergerTimeline
        merger={{
          effective_notification_datetime: '2026-05-18T12:00:00Z',
          end_of_determination_period: '2026-07-01T12:00:00Z',
          determination_publication_date: '2026-06-10T12:00:00Z',
          accc_determination: 'Approved',
          status: 'Assessment completed',
        }}
      />
    );

    // Right-hand endpoint is the statutory deadline, not the actual date.
    expect(screen.getByText('Decision deadline')).toBeInTheDocument();
    expect(screen.getByText('01/07/2026')).toBeInTheDocument();
    // The actual determination is shown as a labelled marker on the axis.
    expect(screen.getByText('Determination')).toBeInTheDocument();
    expect(screen.getByText('10/06/2026')).toBeInTheDocument();
    // No live "today" marker once the assessment is finished.
    expect(screen.queryByText('Today')).not.toBeInTheDocument();
  });

  it('derives a 25-business-day deadline for a decided waiver', () => {
    render(
      <MergerTimeline
        merger={{
          is_waiver: true,
          effective_notification_datetime: '2026-01-08T12:00:00Z',
          end_of_determination_period: null,
          determination_publication_date: '2026-01-20T12:00:00Z',
          accc_determination: 'Approved',
          status: 'Assessment completed',
        }}
      />
    );

    expect(screen.getByText('Waiver application')).toBeInTheDocument();
    expect(screen.getByText('Decision deadline')).toBeInTheDocument();
    // 25 business days after 08/01/2026 (allowing for the 23 Dec - 10 Jan
    // non-business period, weekends and ACT public holidays) is 16/02/2026.
    expect(screen.getByText('16/02/2026')).toBeInTheDocument();
    expect(screen.getByText('Determination')).toBeInTheDocument();
    expect(screen.getByText('20/01/2026')).toBeInTheDocument();
  });

  it('derives a 25-business-day deadline for a pending waiver', () => {
    render(
      <MergerTimeline
        merger={{
          is_waiver: true,
          effective_notification_datetime: '2026-05-18T12:00:00Z',
          end_of_determination_period: null,
          status: 'Under assessment',
        }}
      />
    );

    expect(screen.getByText('Waiver application')).toBeInTheDocument();
    expect(screen.getByText('Decision due')).toBeInTheDocument();
    expect(screen.getByText('Today')).toBeInTheDocument();
  });

  it('falls back to a labelled view when no proportional axis is available', () => {
    render(
      <MergerTimeline
        merger={{
          effective_notification_datetime: null,
          original_notification_datetime: '2026-04-01T12:00:00Z',
          status: 'Assessment suspended',
        }}
      />
    );

    expect(screen.getByText(/None . assessment suspended/i)).toBeInTheDocument();
    expect(screen.getByText(/originally 01\/04\/2026/i)).toBeInTheDocument();
  });
});
