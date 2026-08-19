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
  it('dates the start of pre-notification for a bracketed estimate', () => {
    render(<PreNotificationEstimate merger={merger()} />);

    expect(
      screen.getByText(/Our market intelligence suggests that this merger entered pre-notification around 7 May 2026/)
    ).toBeInTheDocument();
  });

  it('dates the start of pre-notification when only a lower bound is proven', () => {
    render(<PreNotificationEstimate merger={merger({
      pre_notification: {
        estimated_days: 7,
        min_days: 7,
        max_days: null,
        id_issued_estimated: '2026-05-20',
        basis: 'lower-bound-only',
      },
    })} />);

    expect(screen.getByText(/entered pre-notification around 20 May 2026/)).toBeInTheDocument();
  });

  it('gives the date as a floor when only an upper bound is known', () => {
    render(<PreNotificationEstimate merger={merger({
      pre_notification: {
        estimated_days: 40,
        min_days: null,
        max_days: 40,
        id_issued_estimated: '2026-04-17',
        basis: 'upper-bound-only',
      },
    })} />);

    expect(
      screen.getByText(/entered pre-notification sometime after 17 April 2026/)
    ).toBeInTheDocument();
    expect(screen.queryByText(/around/)).not.toBeInTheDocument();
  });

  it('reports little or no pre-notification for a nought-day estimate', () => {
    render(<PreNotificationEstimate merger={merger({
      pre_notification: {
        estimated_days: 0,
        min_days: 0,
        max_days: null,
        id_issued_estimated: '2026-05-27',
        basis: 'lower-bound-only',
      },
    })} />);

    expect(
      screen.getByText(/this merger had little or no pre-notification period/)
    ).toBeInTheDocument();
  });

  it('renders nothing for a merger notified in the voluntary period', () => {
    const { container } = render(<PreNotificationEstimate merger={merger({
      original_notification_datetime: '2025-11-03T12:00:00Z',
      effective_notification_datetime: '2025-11-03T12:00:00Z',
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
