import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import PreNotificationEstimate from '../PreNotificationEstimate';

const merger = (overrides = {}) => ({
  merger_id: 'MN-01050',
  original_notification_datetime: '2026-05-27T12:00:00Z',
  effective_notification_datetime: '2026-05-27T12:00:00Z',
  pre_notification: {
    estimated_days: 20,
    min_days: 12,
    max_days: 34,
    id_issued_estimated: '2026-05-07',
    id_issued_before: '2026-05-15',
    id_issued_after: '2026-04-23',
    basis: 'bracketed',
    method_version: 1,
  },
  ...overrides,
});

describe('PreNotificationEstimate', () => {
  it('states the estimated date pre-notification began', () => {
    render(<PreNotificationEstimate merger={merger()} />);

    expect(screen.getByText(/entered pre-notification around 7 May 2026/)).toBeInTheDocument();
  });

  it('shows both bounds for a bracketed estimate', () => {
    render(<PreNotificationEstimate merger={merger()} />);

    expect(
      screen.getByText(/Between 12 and 34 days before it was notified on 27 May 2026/)
    ).toBeInTheDocument();
  });

  it('states a floor when only a lower bound is proven', () => {
    render(<PreNotificationEstimate merger={merger({
      pre_notification: {
        estimated_days: 7,
        min_days: 7,
        max_days: null,
        id_issued_estimated: '2026-05-20',
        basis: 'lower-bound-only',
      },
    })} />);

    expect(screen.getByText(/At least 7 days before/)).toBeInTheDocument();
  });

  it('states a ceiling when only an upper bound is known', () => {
    render(<PreNotificationEstimate merger={merger({
      pre_notification: {
        estimated_days: 40,
        min_days: null,
        max_days: 40,
        id_issued_estimated: '2026-04-17',
        basis: 'upper-bound-only',
      },
    })} />);

    expect(screen.getByText(/No more than 40 days before/)).toBeInTheDocument();
  });

  it('states the ceiling alone when the bracket rests on a nought-day floor', () => {
    render(<PreNotificationEstimate merger={merger({
      pre_notification: {
        estimated_days: 11,
        min_days: 0,
        max_days: 56,
        id_issued_estimated: '2026-05-16',
        basis: 'bracketed',
      },
    })} />);

    expect(screen.getByText(/No more than 56 days before/)).toBeInTheDocument();
    expect(screen.queryByText(/Between 0 and/)).not.toBeInTheDocument();
  });

  it('renders nothing for a merger notified in the voluntary period', () => {
    const { container } = render(<PreNotificationEstimate merger={merger({
      original_notification_datetime: '2025-11-03T12:00:00Z',
      effective_notification_datetime: '2025-11-03T12:00:00Z',
    })} />);

    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when the estimate collapses to the filing date', () => {
    const { container } = render(<PreNotificationEstimate merger={merger({
      pre_notification: {
        estimated_days: 0,
        min_days: 0,
        max_days: null,
        id_issued_estimated: '2026-05-27',
        basis: 'lower-bound-only',
      },
    })} />);

    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when the merger has no estimate', () => {
    const { container } = render(
      <PreNotificationEstimate merger={merger({ pre_notification: undefined })} />
    );

    expect(container).toBeEmptyDOMElement();
  });
});
