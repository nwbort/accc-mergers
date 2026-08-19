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

  describe('expected determination band', () => {
    // Notified 18 May 2026, 30-BD statutory deadline 1 Jul 2026, "today" is
    // 1 Jun 2026. 15 business days from 18 May lands on 10 Jun 2026 (1 and 8
    // June are ACT public holidays) — still ahead of today, so the forecast
    // is live.
    const running = {
      effective_notification_datetime: '2026-05-18T12:00:00Z',
      end_of_determination_period: '2026-07-01T12:00:00Z',
      status: 'Under assessment',
    };

    it('shades the expected determination window while it is still ahead', () => {
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

      const band = screen.getByLabelText(/Expected determination/);
      expect(band).toHaveAttribute('title', expect.stringContaining('10 Jun 2026'));
      expect(band.getAttribute('title')).toBe(
        'Expected determination \u00b7 10 Jun 2026 \u00b7 15-17 business days'
      );
      // Shaded across a range, not pinned to a single point.
      expect(parseFloat(band.style.width)).toBeGreaterThan(0);
      expect(screen.getByText('Expected determination')).toBeInTheDocument();
    });

    it('holds the left edge at today so the band is never in the past', () => {
      render(
        <MergerTimeline
          merger={{
            ...running,
            // 5-20 BDs: the bottom of the range is already behind "today".
            phase_1_estimate: {
              expected_business_days: 18,
              range_business_days: [5, 20],
              basis: 'global',
              sample_size: 178,
            },
          }}
        />
      );

      const band = screen.getByLabelText(/Expected determination/);
      // Today (1 Jun) sits 14/44 calendar days along 18 May -> 1 Jul.
      expect(parseFloat(band.style.left)).toBeCloseTo((14 / 44) * 100, 1);
    });

    it('falls back to the point estimate when the range has no width', () => {
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

      const band = screen.getByLabelText(/Expected determination/);
      expect(band.getAttribute('title')).toBe(
        'Expected determination \u00b7 10 Jun 2026 \u00b7 15 business days'
      );
    });

    it('drops the band once the expected date has passed', () => {
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

    it('drops the band once phase 1 has actually concluded', () => {
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

    it('drops the band when the estimate runs past the statutory deadline', () => {
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
      expect(screen.queryByText('Expected determination')).not.toBeInTheDocument();
    });

    it('drops its label rather than colliding with the "Today" label', () => {
      // A narrow track: the two fixed-width label boxes cannot both fit, so the
      // forecast label gives way to the actual state of the matter.
      vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
        width: 200, height: 96, top: 0, left: 0, right: 200, bottom: 96, x: 0, y: 0,
        toJSON: () => ({}),
      });

      render(
        <MergerTimeline
          merger={{
            ...running,
            phase_1_estimate: {
              expected_business_days: 15,
              range_business_days: [15, 17],
              basis: 'global',
              sample_size: 178,
            },
          }}
        />
      );

      // The band itself stays — only its label stands down.
      expect(screen.getByLabelText(/Expected determination/)).toBeInTheDocument();
      expect(screen.queryByText('Expected determination')).not.toBeInTheDocument();
      expect(screen.getByText('Today')).toBeInTheDocument();
    });

    it('keeps its label when the track is wide enough to clear "Today"', () => {
      vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
        width: 1400, height: 96, top: 0, left: 0, right: 1400, bottom: 96, x: 0, y: 0,
        toJSON: () => ({}),
      });

      render(
        <MergerTimeline
          merger={{
            ...running,
            phase_1_estimate: {
              expected_business_days: 25,
              range_business_days: [24, 26],
              basis: 'global',
              sample_size: 178,
            },
          }}
        />
      );

      expect(screen.getByText('Expected determination')).toBeInTheDocument();
      expect(screen.getByText('Today')).toBeInTheDocument();
    });
  });
});
