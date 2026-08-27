import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import BusinessDayProgress from '../BusinessDayProgress';

describe('BusinessDayProgress', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-01T00:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows "Business day X of Y" partway through a non-waiver assessment', () => {
    render(
      <BusinessDayProgress
        merger={{
          effective_notification_datetime: '2026-05-18T12:00:00Z',
          end_of_determination_period: '2026-07-01T12:00:00Z',
          status: 'Under assessment',
        }}
      />
    );

    // 2026-05-18 -> 2026-06-01 is 9 business days (see businessDayProgress.test.js
    // for the underlying calculation, exercised directly there).
    expect(screen.getByText('Business day 9 of 30')).toBeInTheDocument();
  });

  it('shows "Business day 0 of Y" when notified today', () => {
    render(
      <BusinessDayProgress
        merger={{
          effective_notification_datetime: '2026-06-01T00:00:00Z',
          end_of_determination_period: '2026-07-15T12:00:00Z',
          status: 'Under assessment',
        }}
      />
    );

    expect(screen.getByText(/^Business day 0 of \d+$/)).toBeInTheDocument();
  });

  it('shows overdue text once past the end-of-determination date', () => {
    render(
      <BusinessDayProgress
        merger={{
          effective_notification_datetime: '2026-03-01T12:00:00Z',
          end_of_determination_period: '2026-05-01T12:00:00Z',
          status: 'Under assessment',
        }}
      />
    );

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
