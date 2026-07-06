import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import BusinessDayProgress from '../BusinessDayProgress';
import { BusinessDayChip } from '../BusinessDayProgress';
import { calculateBusinessDays } from '../../utils/dates';

describe('BusinessDayProgress', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-01T00:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows "Business day X of Y" partway through a non-waiver assessment', () => {
    const merger = {
      effective_notification_datetime: '2026-05-18T12:00:00Z',
      end_of_determination_period: '2026-07-01T12:00:00Z',
      status: 'Under assessment',
    };
    const elapsed = calculateBusinessDays(merger.effective_notification_datetime, new Date());
    const total = calculateBusinessDays(
      merger.effective_notification_datetime,
      merger.end_of_determination_period
    );

    render(<BusinessDayProgress merger={merger} />);

    expect(screen.getByText(`Business day ${elapsed} of ${total}`)).toBeInTheDocument();
  });

  it('shows "Business day 0 of Y" when notified today', () => {
    const merger = {
      effective_notification_datetime: '2026-06-01T00:00:00Z',
      end_of_determination_period: '2026-07-15T12:00:00Z',
      status: 'Under assessment',
    };
    const total = calculateBusinessDays(
      merger.effective_notification_datetime,
      merger.end_of_determination_period
    );

    render(<BusinessDayProgress merger={merger} />);

    expect(screen.getByText(`Business day 0 of ${total}`)).toBeInTheDocument();
  });

  it('shows overdue styling once past the end-of-determination date', () => {
    const merger = {
      effective_notification_datetime: '2026-03-01T12:00:00Z',
      end_of_determination_period: '2026-05-01T12:00:00Z',
      status: 'Under assessment',
    };

    render(<BusinessDayProgress merger={merger} />);

    expect(screen.getByText('Determination overdue')).toBeInTheDocument();
    expect(screen.queryByText(/Business day \d+ of \d+/)).not.toBeInTheDocument();
  });

  it('renders nothing for a waiver', () => {
    const { container } = render(
      <BusinessDayProgress
        merger={{
          is_waiver: true,
          effective_notification_datetime: '2026-05-18T12:00:00Z',
          end_of_determination_period: '2026-07-01T12:00:00Z',
          status: 'Under assessment',
        }}
      />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing once the assessment is complete', () => {
    const { container } = render(
      <BusinessDayProgress
        merger={{
          effective_notification_datetime: '2026-05-18T12:00:00Z',
          end_of_determination_period: '2026-07-01T12:00:00Z',
          determination_publication_date: '2026-06-10T12:00:00Z',
          status: 'Assessment completed',
        }}
      />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when the end-of-determination period is missing', () => {
    const { container } = render(
      <BusinessDayProgress
        merger={{
          effective_notification_datetime: '2026-05-18T12:00:00Z',
          end_of_determination_period: null,
          status: 'Under assessment',
        }}
      />
    );

    expect(container).toBeEmptyDOMElement();
  });
});

describe('BusinessDayChip', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-01T00:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows a compact "BD X/Y" chip partway through a non-waiver assessment', () => {
    const merger = {
      effective_notification_datetime: '2026-05-18T12:00:00Z',
      end_of_determination_period: '2026-07-01T12:00:00Z',
      status: 'Under assessment',
    };
    const elapsed = calculateBusinessDays(merger.effective_notification_datetime, new Date());
    const total = calculateBusinessDays(
      merger.effective_notification_datetime,
      merger.end_of_determination_period
    );

    render(<BusinessDayChip merger={merger} />);

    expect(screen.getByText(`BD ${elapsed}/${total}`)).toBeInTheDocument();
  });

  it('shows "Overdue" once past the end-of-determination date', () => {
    render(
      <BusinessDayChip
        merger={{
          effective_notification_datetime: '2026-03-01T12:00:00Z',
          end_of_determination_period: '2026-05-01T12:00:00Z',
          status: 'Under assessment',
        }}
      />
    );

    expect(screen.getByText('Overdue')).toBeInTheDocument();
  });

  it('renders nothing for a waiver', () => {
    const { container } = render(
      <BusinessDayChip
        merger={{
          is_waiver: true,
          effective_notification_datetime: '2026-05-18T12:00:00Z',
          end_of_determination_period: '2026-07-01T12:00:00Z',
          status: 'Under assessment',
        }}
      />
    );

    expect(container).toBeEmptyDOMElement();
  });
});
