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

  it('states the live status while the matter is still under assessment', () => {
    render(
      <MergerOutcomeHeading merger={{ status: 'Under assessment', accc_determination: null }} />
    );
    expect(screen.getByText('Under assessment')).toBeInTheDocument();
  });

  it('introduces a live status as a status, not as an outcome', () => {
    render(
      <MergerOutcomeHeading merger={{ status: 'Under assessment', accc_determination: null }} />
    );
    expect(screen.getByText('Status:')).toBeInTheDocument();
    expect(screen.queryByText('Outcome:')).not.toBeInTheDocument();
  });

  it('states a suspended assessment', () => {
    render(
      <MergerOutcomeHeading merger={{ status: 'Assessment suspended', accc_determination: null }} />
    );
    expect(screen.getByText('Assessment suspended')).toBeInTheDocument();
  });

  it('renders nothing for a record carrying neither a status nor a determination', () => {
    const { container } = render(<MergerOutcomeHeading merger={{}} />);
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
    // Part of the outcome's own name, not an annotation beside it.
    render(<MergerOutcomeHeading merger={{ ...completed, has_conditions: true }} />);
    expect(screen.getByText('Approved with conditions')).toBeInTheDocument();
  });

  it('ignores a conditions flag left on any other outcome', () => {
    render(
      <MergerOutcomeHeading
        merger={{ ...completed, accc_determination: 'Not approved', has_conditions: true }}
      />
    );
    expect(screen.getByText('Not approved')).toBeInTheDocument();
    expect(screen.queryByText(/with conditions/)).not.toBeInTheDocument();
  });

  it('leaves the ACCC outcome standing while an appeal is still current, and says so', () => {
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
    expect(screen.getByText('Under appeal')).toBeInTheDocument();
    // No concluded-appeal suffix: the Tribunal hasn't changed anything yet.
    expect(screen.queryByText('confirmed on appeal')).not.toBeInTheDocument();
  });

  it('flags a live matter under appeal the same way as a decided one', () => {
    // An appeal is an additional status, not a different one, so it reads
    // identically whether or not the matter underneath has finished.
    render(
      <MergerOutcomeHeading
        merger={{
          status: 'Under assessment',
          accc_determination: null,
          under_appeal: true,
          appeal: { status: 'current', outcome: null, effective_determination: null },
        }}
      />
    );
    expect(screen.getByText('Under assessment')).toBeInTheDocument();
    expect(screen.getByText('Under appeal')).toBeInTheDocument();
  });

  it('says nothing about an appeal that has finished and left no mark', () => {
    render(<MergerOutcomeHeading merger={completed} />);
    expect(screen.queryByText('Under appeal')).not.toBeInTheDocument();
  });

  it('gives a live appeal its gavel beside a decided outcome, which has a glyph too', () => {
    const { container } = render(
      <MergerOutcomeHeading
        merger={{
          ...completed,
          accc_determination: 'Not approved',
          under_appeal: true,
          appeal: { status: 'current', outcome: null, effective_determination: null },
        }}
      />
    );
    expect(container.querySelectorAll('svg')).toHaveLength(2);
  });

  it('gives a live appeal its gavel beside a live status, which has none', () => {
    // The gavel belongs to the appeal rather than to the pairing, so it does
    // not come and go with whatever the status beside it happens to carry.
    const { container } = render(
      <MergerOutcomeHeading
        merger={{
          status: 'Under assessment',
          accc_determination: null,
          under_appeal: true,
          appeal: { status: 'current', outcome: null, effective_determination: null },
        }}
      />
    );
    expect(container.querySelectorAll('svg')).toHaveLength(1);
    expect(screen.queryByText('·')).not.toBeInTheDocument();
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
    // The suffix rides in the outcome's own run of text, dotted off so it does
    // not read as one phrase with it.
    expect(screen.getByText('Approved · on appeal')).toBeInTheDocument();
  });

  it('flags a waiver application as a chip beside the status', () => {
    render(<MergerOutcomeHeading merger={{ ...completed, is_waiver: true }} />);
    expect(screen.getByText('Waiver')).toBeInTheDocument();
  });

  it('says nothing about the waiver flag for an ordinary notification', () => {
    render(<MergerOutcomeHeading merger={completed} />);
    expect(screen.queryByText('Waiver')).not.toBeInTheDocument();
  });

  it('says a live matter is in the public benefit phase', () => {
    render(
      <MergerOutcomeHeading
        merger={{
          status: 'Under assessment',
          accc_determination: null,
          stage: 'Public benefit phase',
          public_benefit_in_progress: true,
          phase_2_determination: 'Not approved',
        }}
      />
    );
    expect(screen.getByText('Under assessment · public benefit phase')).toBeInTheDocument();
  });
});
