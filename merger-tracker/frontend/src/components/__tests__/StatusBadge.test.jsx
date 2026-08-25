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
