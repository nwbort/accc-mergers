import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import NotificationPanel from '../NotificationPanel';

let mockTracking;
vi.mock('../../context/TrackingContext', () => ({
  useTracking: () => mockTracking,
}));

const hearing = {
  type: 'tribunal_hearing',
  event_type_display: 'Tribunal hearing',
  display_title: 'Tribunal hearing',
  title: 'Tribunal hearing',
  date: '2026-11-09',
  end_date: '2026-11-19',
  merger_id: 'MN-01068',
  merger_name: 'Coles – Kalgoorlie',
};

const renderPanel = (events) => {
  mockTracking = {
    trackedEvents: events,
    trackedMergerIds: ['MN-01068'],
    trackedIndustries: [],
    trackedIndustryEvents: [],
    markEventsAsSeen: () => {},
    isEventSeen: () => true,
    getEventKey: (e) => `${e.merger_id}_${e.date}_${e.title}`,
    loading: false,
  };
  render(
    <MemoryRouter>
      <NotificationPanel isOpen onClose={() => {}} />
    </MemoryRouter>
  );
};

describe('NotificationPanel multi-day hearings', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows a hearing part-way through its run as ongoing, not past', () => {
    // Tuesday 10 Nov 2026 in Sydney: day two.
    vi.setSystemTime(new Date('2026-11-10T01:00:00Z'));
    renderPanel([hearing]);
    expect(screen.getByText('Tribunal hearing')).toBeInTheDocument();
    expect(screen.getByText('09/11/2026 – 19/11/2026', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('(ongoing)')).toBeInTheDocument();
    expect(screen.queryByText(/past event/)).not.toBeInTheDocument();
  });

  it('counts down to a hearing that has not begun, showing its span', () => {
    vi.setSystemTime(new Date('2026-11-06T01:00:00Z'));
    renderPanel([hearing]);
    expect(screen.getByText('(3 days)')).toBeInTheDocument();
    expect(screen.queryByText('(ongoing)')).not.toBeInTheDocument();
  });

  it('files the hearing under past events once its last day has gone', () => {
    vi.setSystemTime(new Date('2026-11-20T01:00:00Z'));
    renderPanel([hearing]);
    expect(screen.getByText('Show 1 past event')).toBeInTheDocument();
  });
});
