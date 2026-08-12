import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import RecentDeterminationsCards from '../RecentDeterminationsCards';

function renderCards(determinations) {
  return render(
    <MemoryRouter>
      <RecentDeterminationsCards determinations={determinations} />
    </MemoryRouter>
  );
}

const approval = {
  merger_id: 'MN-0001',
  merger_name: 'Alpha acquires Beta',
  determination: 'Approved',
  determination_date: '2026-08-11T12:00:00Z',
  determination_type: 'final',
  is_waiver: false,
  has_conditions: false,
};

describe('RecentDeterminationsCards', () => {
  it('flags a conditional approval', () => {
    renderCards([{ ...approval, has_conditions: true }]);
    expect(screen.getByText('Approved')).toBeInTheDocument();
    expect(screen.getByText('With conditions')).toBeInTheDocument();
  });

  it('leaves an unconditional approval unflagged', () => {
    renderCards([approval]);
    expect(screen.getByText('Approved')).toBeInTheDocument();
    expect(screen.queryByText('With conditions')).not.toBeInTheDocument();
  });

  it('does not flag conditions on a determination that is not an approval', () => {
    // has_conditions is only meaningful alongside "Approved"; a stale flag on
    // any other outcome must not surface.
    renderCards([{ ...approval, determination: 'Not approved', has_conditions: true }]);
    expect(screen.queryByText('With conditions')).not.toBeInTheDocument();
  });

  it('still shows the waiver chip alongside the conditions chip', () => {
    renderCards([{ ...approval, is_waiver: true, has_conditions: true }]);
    expect(screen.getByText('Waiver')).toBeInTheDocument();
    expect(screen.getByText('With conditions')).toBeInTheDocument();
  });
});
