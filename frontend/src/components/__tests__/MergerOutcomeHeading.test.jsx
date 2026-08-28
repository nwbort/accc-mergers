import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import MergerOutcomeHeading from '../MergerOutcomeHeading';

const completed = {
  status: 'Assessment completed',
  accc_determination: 'Approved',
  stage: 'Phase 1 - initial assessment',
  effective_notification_datetime: '2026-06-01T12:00:00Z',
  determination_publication_date: '2026-07-01T12:00:00Z',
};

describe('MergerOutcomeHeading', () => {
  it('states the determination for a completed matter', () => {
    render(<MergerOutcomeHeading merger={completed} />);
    expect(screen.getByText('Approved')).toBeInTheDocument();
  });

  it('names the outcome, so it does not read as a bare adjective above the title', () => {
    render(<MergerOutcomeHeading merger={completed} />);
    expect(screen.getByText('Outcome:')).toBeInTheDocument();
  });

  it('renders nothing while the matter is still under assessment', () => {
    const { container } = render(
      <MergerOutcomeHeading merger={{ status: 'Under assessment', accc_determination: null }} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing for a suspended assessment', () => {
    const { container } = render(
      <MergerOutcomeHeading merger={{ status: 'Assessment suspended', accc_determination: null }} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('states a ceased assessment, which never gets a determination', () => {
    render(
      <MergerOutcomeHeading
        merger={{ status: 'Assessment ceased', accc_determination: null, ceased_date: '2026-07-16' }}
      />
    );
    expect(screen.getByText('Assessment ceased')).toBeInTheDocument();
  });

  it('flags a conditional clearance, which the register records as a plain approval', () => {
    render(<MergerOutcomeHeading merger={{ ...completed, has_conditions: true }} />);
    expect(screen.getByText('with conditions')).toBeInTheDocument();
  });

  it('ignores a conditions flag left on any other outcome', () => {
    render(
      <MergerOutcomeHeading
        merger={{ ...completed, accc_determination: 'Not approved', has_conditions: true }}
      />
    );
    expect(screen.queryByText('with conditions')).not.toBeInTheDocument();
  });

  it('leaves the ACCC outcome standing while an appeal is still current', () => {
    render(
      <MergerOutcomeHeading
        merger={{
          ...completed,
          accc_determination: 'Not approved',
          under_appeal: true,
          appeal: { status: 'current', outcome: null, effective_determination: null },
        }}
      />
    );
    expect(screen.getByText('Not approved')).toBeInTheDocument();
    expect(screen.queryByText(/on appeal/)).not.toBeInTheDocument();
  });

  it('shows the outcome the tribunal left standing, and why it changed', () => {
    render(
      <MergerOutcomeHeading
        merger={{
          ...completed,
          accc_determination: 'Not approved',
          appeal: {
            status: 'concluded',
            outcome: 'set_aside',
            effective_determination: 'Approved',
            concluded_date: '2026-11-20',
          },
        }}
      />
    );
    expect(screen.getByText('Approved')).toBeInTheDocument();
    expect(screen.getByText('on appeal')).toBeInTheDocument();
  });
});
