import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import Phase2CompletedCards from '../Phase2CompletedCards';

function renderCards(matters) {
  return render(
    <MemoryRouter>
      <Phase2CompletedCards matters={matters} />
    </MemoryRouter>
  );
}

const matter = {
  merger_id: 'MN-0001',
  merger_name: 'Alpha acquires Beta',
  determination: 'Approved',
  determination_date: '2026-08-01T12:00:00Z',
  referral_date: '2026-03-10T09:00:00Z',
  is_refiled: false,
  under_appeal: false,
  has_conditions: false,
};

describe('Phase2CompletedCards', () => {
  it('flags a conditional approval', () => {
    renderCards([{ ...matter, has_conditions: true }]);
    expect(screen.getByText('Approved')).toBeInTheDocument();
    expect(screen.getByText('With conditions')).toBeInTheDocument();
  });

  it('leaves an unconditional approval unflagged', () => {
    renderCards([matter]);
    expect(screen.getByText('Approved')).toBeInTheDocument();
    expect(screen.queryByText('With conditions')).not.toBeInTheDocument();
  });

  it('does not flag conditions on a determination that is not an approval', () => {
    // has_conditions is only meaningful alongside "Approved"; a stale flag on
    // any other outcome must not surface.
    renderCards([{ ...matter, determination: 'Not approved', has_conditions: true }]);
    expect(screen.queryByText('With conditions')).not.toBeInTheDocument();
  });

  it('shows the conditions chip alongside the other card chips', () => {
    renderCards([{ ...matter, has_conditions: true, is_refiled: true, under_appeal: true }]);
    expect(screen.getByText('With conditions')).toBeInTheDocument();
    expect(screen.getByText('Refiled')).toBeInTheDocument();
    expect(screen.getByText('Under appeal')).toBeInTheDocument();
  });
});

describe('Phase2CompletedCards collapse', () => {
  const many = (n) =>
    Array.from({ length: n }, (_, i) => ({
      ...matter,
      merger_id: `MN-${String(i).padStart(4, '0')}`,
      merger_name: `Matter ${i}`,
    }));

  it('shows nine cards from sm up before the toggle', () => {
    const { container } = renderCards(many(12));
    const items = [...container.querySelectorAll('li')];
    expect(items.slice(0, 9).every((li) => li.className.includes('sm:flex') || / flex /.test(li.className))).toBe(true);
    expect(items.slice(9).every((li) => /(^| )hidden( |$)/.test(li.className) && !li.className.includes('sm:flex'))).toBe(true);
    expect(screen.getByRole('button', { name: /show more/i })).toBeInTheDocument();
  });

  it('hides the toggle from sm up when there are nine or fewer', () => {
    renderCards(many(9));
    // Still present for mobile (three cards), but hidden from sm up.
    const toggle = screen.getByRole('button', { name: /show more/i });
    expect(toggle.closest('div.relative.my-5').className).toContain('sm:hidden');
  });
});
