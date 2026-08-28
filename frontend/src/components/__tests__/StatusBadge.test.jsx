import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import StatusBadge from '../StatusBadge';

describe('StatusBadge', () => {
  it('shows the ACCC determination when there is no appeal', () => {
    render(<StatusBadge status="Assessment completed" determination="Not approved" />);
    expect(screen.getByText('Not approved')).toBeInTheDocument();
    expect(screen.queryByText(/on appeal/)).not.toBeInTheDocument();
  });

  it('appends "· with conditions" for a conditional approval', () => {
    render(<StatusBadge status="Assessment completed" determination="Approved" hasConditions />);
    expect(screen.getByText('· with conditions')).toBeInTheDocument();
  });

  it('leaves the ACCC determination untouched while an appeal is still current', () => {
    render(
      <StatusBadge
        status="Assessment completed"
        determination="Not approved"
        appeal={{ status: 'current', outcome: null, effective_determination: null }}
      />
    );
    expect(screen.getByText('Not approved')).toBeInTheDocument();
    expect(screen.queryByText(/on appeal/)).not.toBeInTheDocument();
  });

  it('shows "Not approved · confirmed on appeal" when a party loses at the tribunal', () => {
    render(
      <StatusBadge
        status="Assessment completed"
        determination="Not approved"
        appeal={{ status: 'concluded', outcome: 'affirmed', effective_determination: 'Not approved' }}
      />
    );
    expect(screen.getByText('Not approved')).toBeInTheDocument();
    expect(screen.getByText('· confirmed on appeal')).toBeInTheDocument();
  });

  it('flips to "Approved · on appeal" when a party wins its refusal appeal', () => {
    render(
      <StatusBadge
        status="Assessment completed"
        determination="Not approved"
        appeal={{ status: 'concluded', outcome: 'set_aside', effective_determination: 'Approved' }}
      />
    );
    // The effective outcome now stands ...
    expect(screen.getByText('Approved')).toBeInTheDocument();
    expect(screen.getByText('· on appeal')).toBeInTheDocument();
    // ... and the badge is colour-coded by that effective determination.
    expect(screen.getByRole('img').className).toMatch(/emerald/);
  });

  it('gives the few adverse outcomes a solid badge, not the tint the clearances get', () => {
    const { container: refused } = render(
      <StatusBadge status="Assessment completed" determination="Not approved" />
    );
    expect(refused.querySelector('[role="img"]').className).toMatch(/bg-red-700/);
    expect(refused.querySelector('[role="img"]').className).toMatch(/text-white/);

    const { container: ceased } = render(<StatusBadge status="Assessment ceased" />);
    expect(ceased.querySelector('[role="img"]').className).toMatch(/bg-purple-700/);
  });

  it('leaves a clearance on the tint, since nine in ten matters are one', () => {
    const { container } = render(
      <StatusBadge status="Assessment completed" determination="Approved" />
    );
    expect(container.querySelector('[role="img"]').className).toMatch(/bg-emerald-50/);
  });

  it('marks a decided outcome with a glyph, so colour is not the only signal', () => {
    const { container } = render(
      <StatusBadge status="Assessment completed" determination="Approved" />
    );
    const icon = container.querySelector('svg');
    expect(icon).not.toBeNull();
    // Decorative: the badge's own aria-label already reads the outcome out.
    expect(icon).toHaveAttribute('aria-hidden', 'true');
    expect(screen.getByRole('img')).toHaveAccessibleName('Determination: Approved');
  });

  it('gives a live matter no glyph, having no result to symbolise', () => {
    const { container } = render(<StatusBadge status="Under assessment" />);
    expect(container.querySelector('svg')).toBeNull();
  });

  it('flips a cleared merger to "Not approved · on appeal" on a third-party turnaround', () => {
    render(
      <StatusBadge
        status="Assessment completed"
        determination="Approved"
        appeal={{ status: 'concluded', outcome: 'set_aside', effective_determination: 'Not approved' }}
      />
    );
    expect(screen.getByText('Not approved')).toBeInTheDocument();
    expect(screen.getByText('· on appeal')).toBeInTheDocument();
    expect(screen.getByRole('img').className).toMatch(/red/);
  });
});
