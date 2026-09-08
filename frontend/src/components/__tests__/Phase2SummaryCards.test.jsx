import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import Phase2SummaryCards from '../Phase2SummaryCards';

function renderCards(current, completed) {
  return render(
    <MemoryRouter>
      <Phase2SummaryCards current={current} completed={completed} />
    </MemoryRouter>
  );
}

const completedMatter = (overrides) => ({
  merger_id: 'MN-0001',
  merger_name: 'Alpha acquires Beta',
  determination: 'Approved',
  referral_date: '2026-01-01T12:00:00Z',
  determination_date: '2026-01-11T12:00:00Z',
  has_conditions: false,
  ...overrides,
});

describe('Phase2SummaryCards', () => {
  it('counts every matter that has been in Phase 2, running and completed', () => {
    renderCards([{ merger_id: 'MN-1' }], [completedMatter()]);
    expect(screen.getByText('Referred to Phase 2')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('shows the outcome split with a legend entry per outcome', () => {
    renderCards([], [
      completedMatter({ merger_id: 'MN-1' }),
      completedMatter({ merger_id: 'MN-2', determination: 'Not approved' }),
      completedMatter({ merger_id: 'MN-3', determination: 'Assessment ceased' }),
      completedMatter({ merger_id: 'MN-4', determination: 'Assessment ceased' }),
    ]);
    const legend = screen.getAllByRole('listitem').map((li) => li.textContent);
    expect(legend).toEqual([
      'Approved1 · 25%',
      'Not approved1 · 25%',
      'Assessment ceased2 · 50%',
    ]);
  });

  it('averages Phase 2 duration without the ceased assessments', () => {
    renderCards([], [
      completedMatter({ merger_id: 'MN-1', determination_date: '2026-01-11T12:00:00Z' }),
      completedMatter({
        merger_id: 'MN-2',
        determination: 'Assessment ceased',
        determination_date: '2026-01-03T12:00:00Z',
      }),
    ]);
    // Both matters ran from 1 Jan; counting the 2-day ceased assessment would
    // pull the average down to 6 days.
    expect(screen.getByText('10 days')).toBeInTheDocument();
  });

  it('draws an outright clearance and a conditional one in distinct colours', () => {
    // No Phase 2 review has been cleared outright yet, so nothing on the live
    // page would show the two greens side by side and catch them collapsing
    // into each other.
    const { container } = renderCards([], [
      completedMatter({ merger_id: 'MN-1' }),
      completedMatter({ merger_id: 'MN-2', has_conditions: true }),
    ]);
    const swatches = [...container.querySelectorAll('[style*="background-color"]')]
      .map((el) => el.style.backgroundColor);
    expect(new Set(swatches).size).toBe(2);
  });

  it('says so when no review has concluded', () => {
    renderCards([{ merger_id: 'MN-1' }], []);
    expect(screen.getByText('N/A')).toBeInTheDocument();
    expect(screen.getByText('No Phase 2 review has concluded yet.')).toBeInTheDocument();
  });

  it('renders nothing before any matter has been referred', () => {
    const { container } = renderCards([], []);
    expect(container).toBeEmptyDOMElement();
  });
});
