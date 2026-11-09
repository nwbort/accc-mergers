import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router';
import RecentEventsTable from '../RecentEventsTable';
import { RECENT_EVENT_TYPES } from '../../constants/recentEventTypes';

const event = (n, type = 'questionnaire') => ({
  type,
  title: `Event ${n}`,
  date: '2026-11-02T12:00:00Z',
  merger_id: `MN-${n}`,
  merger_name: `Matter ${n}`,
});

const renderTable = (events) =>
  render(
    <MemoryRouter>
      <RecentEventsTable events={events} />
    </MemoryRouter>
  );

describe('RecentEventsTable', () => {
  const original = RECENT_EVENT_TYPES.questionnaire.shown;
  afterEach(() => {
    RECENT_EVENT_TYPES.questionnaire.shown = original;
  });

  it('opens on ten rows and expands to the rest', async () => {
    renderTable(Array.from({ length: 12 }, (_, i) => event(i)));
    expect(screen.getAllByRole('row')).toHaveLength(11); // + header
    await userEvent.click(screen.getByRole('button', { name: /show more/i }));
    expect(screen.getAllByRole('row')).toHaveLength(13);
  });

  it('leaves out types the dashboard does not show', () => {
    RECENT_EVENT_TYPES.questionnaire.shown = false;
    renderTable([event(1), event(2, 'remedy_offer')]);
    expect(screen.queryByText('Matter 1')).toBeNull();
    expect(screen.getByText('Matter 2')).toBeTruthy();
  });

  it('reads an unknown type as Other rather than dropping it', () => {
    renderTable([event(1, 'something_new')]);
    expect(screen.getAllByText('Other').length).toBeGreaterThan(0);
  });
});
