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

  it('renders notification start and deadline while under assessment', () => {
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
    expect(screen.getByText('Deadline')).toBeInTheDocument();
    expect(screen.getByText('18 May 2026')).toBeInTheDocument();
    expect(screen.getByText('01 Jul 2026')).toBeInTheDocument();
    expect(screen.getByText('Today')).toBeInTheDocument();
    expect(screen.getByText(/days left/)).toBeInTheDocument();
  });

  it('ends on the deadline once complete, with the determination as a marker', () => {
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
    expect(screen.getByText('Deadline')).toBeInTheDocument();
    expect(screen.getByText('01 Jul 2026')).toBeInTheDocument();
    // The actual determination is shown as a labelled marker on the axis.
    expect(screen.getByText('Determination')).toBeInTheDocument();
    expect(screen.getByText('10 Jun 2026')).toBeInTheDocument();
    // No live "today" marker once the assessment is finished.
    expect(screen.queryByText('Today')).not.toBeInTheDocument();
  });

  it('marks the Phase 1 determination date with a hover-only dot when referred to Phase 2', () => {
    render(
      <MergerTimeline
        merger={{
          effective_notification_datetime: '2025-10-10T12:00:00Z',
          end_of_determination_period: '2026-06-05T12:00:00Z',
          stage: 'Phase 2 - detailed assessment',
          phase_1_determination: 'Referred to phase 2',
          phase_1_determination_date: '2026-01-20T12:00:00Z',
          phase_2_determination: 'Approved',
          phase_2_determination_date: '2026-06-02T12:00:00Z',
          determination_publication_date: '2026-06-02T12:00:00Z',
          accc_determination: 'Approved',
          status: 'Assessment completed',
        }}
      />
    );

    // The Phase 1 date is not shown as visible text...
    expect(screen.queryByText('20 Jan 2026')).not.toBeInTheDocument();
    // ...but is exposed via the marker's hover/accessible label.
    expect(
      screen.getByLabelText('Referred to Phase 2 on 20 Jan 2026')
    ).toBeInTheDocument();
  });

  it('does not add a Phase 1 marker for a single-phase merger', () => {
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

    expect(screen.queryByLabelText(/Referred to Phase 2/)).not.toBeInTheDocument();
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
    expect(screen.getByText('Deadline')).toBeInTheDocument();
    // 25 business days after 08/01/2026 (allowing for the 23 Dec - 10 Jan
    // non-business period, weekends and ACT public holidays) is 16/02/2026.
    expect(screen.getByText('16 Feb 2026')).toBeInTheDocument();
    expect(screen.getByText('Determination')).toBeInTheDocument();
    expect(screen.getByText('20 Jan 2026')).toBeInTheDocument();
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
    expect(screen.getByText('Deadline')).toBeInTheDocument();
    expect(screen.getByText('Today')).toBeInTheDocument();
  });

  it('shows "Due today" rather than "Overdue" on the deadline\'s own calendar day', () => {
    // "Now" is pinned to 2026-06-01T00:00:00Z in beforeEach, which is after
    // local midnight on the deadline day everywhere behind UTC (including
    // Australia/Sydney) — so a naive instant comparison would already read
    // as overdue even though the deadline day hasn't finished yet.
    render(
      <MergerTimeline
        merger={{
          effective_notification_datetime: '2026-04-01T12:00:00Z',
          end_of_determination_period: '2026-06-01T12:00:00Z',
          status: 'Under assessment',
        }}
      />
    );

    expect(screen.getByText('Due today')).toBeInTheDocument();
    expect(screen.queryByText('Overdue')).not.toBeInTheDocument();
  });

  it('shows "Overdue" once the deadline day has fully passed', () => {
    render(
      <MergerTimeline
        merger={{
          effective_notification_datetime: '2026-04-01T12:00:00Z',
          end_of_determination_period: '2026-05-20T12:00:00Z',
          status: 'Under assessment',
        }}
      />
    );

    expect(screen.getByText('Overdue')).toBeInTheDocument();
    expect(screen.queryByText('Due today')).not.toBeInTheDocument();
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
    expect(screen.getByText(/originally 01 Apr 2026/i)).toBeInTheDocument();
  });

  describe('expected determination tick', () => {
    // Notified 18 May 2026, 30-BD statutory deadline 1 Jul 2026, "today" is
    // 1 Jun 2026. 15 business days from 18 May lands on 10 Jun 2026 (1 and 8
    // June are ACT public holidays) — still ahead of today, so the forecast
    // is live.
    const running = {
      effective_notification_datetime: '2026-05-18T12:00:00Z',
      end_of_determination_period: '2026-07-01T12:00:00Z',
      status: 'Under assessment',
    };

    it('marks the expected determination date while it is still ahead', () => {
      render(
        <MergerTimeline
          merger={{
            ...running,
            phase_1_estimate: {
              expected_business_days: 15,
              range_business_days: [15, 17],
              basis: 'industry',
              sample_size: 9,
            },
          }}
        />
      );

      const tick = screen.getByLabelText(/Expected determination/);
      expect(tick).toHaveAttribute('title', expect.stringContaining('10 Jun 2026'));
      expect(tick.getAttribute('title')).toContain('15-17 business days');
      expect(tick.getAttribute('title')).toContain('9 comparable reviews');
    });

    it('describes a global-basis estimate by the whole-of-market pool', () => {
      render(
        <MergerTimeline
          merger={{
            ...running,
            phase_1_estimate: {
              expected_business_days: 15,
              range_business_days: [15, 15],
              basis: 'global',
              sample_size: 178,
            },
          }}
        />
      );

      const tick = screen.getByLabelText(/Expected determination/);
      expect(tick.getAttribute('title')).toContain('median of all 178 completed phase 1 reviews');
      expect(tick.getAttribute('title')).toContain('15 business days');
    });

    it('drops the tick once the expected date has passed', () => {
      render(
        <MergerTimeline
          merger={{
            ...running,
            // 5 BDs from 18 May is 25 May — already behind "today" (1 Jun).
            phase_1_estimate: { expected_business_days: 5, basis: 'global', sample_size: 178 },
          }}
        />
      );

      expect(screen.queryByLabelText(/Expected determination/)).not.toBeInTheDocument();
    });

    it('drops the tick once phase 1 has actually concluded', () => {
      render(
        <MergerTimeline
          merger={{
            ...running,
            phase_1_determination: 'Approved',
            phase_1_determination_date: '2026-05-29T12:00:00Z',
            determination_publication_date: '2026-05-29T12:00:00Z',
            phase_1_estimate: { expected_business_days: 15, basis: 'global', sample_size: 178 },
          }}
        />
      );

      expect(screen.queryByLabelText(/Expected determination/)).not.toBeInTheDocument();
    });

    it('drops the tick when the estimate runs past the statutory deadline', () => {
      render(
        <MergerTimeline
          merger={{
            ...running,
            phase_1_estimate: { expected_business_days: 40, basis: 'global', sample_size: 178 },
          }}
        />
      );

      expect(screen.queryByLabelText(/Expected determination/)).not.toBeInTheDocument();
    });

    it('renders nothing extra when the merger carries no estimate', () => {
      render(<MergerTimeline merger={running} />);

      expect(screen.queryByLabelText(/Expected determination/)).not.toBeInTheDocument();
    });
  });
});
