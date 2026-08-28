import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import MergerOutcomeBanner from '../MergerOutcomeBanner';

const completed = {
  status: 'Assessment completed',
  accc_determination: 'Approved',
  stage: 'Phase 1 - initial assessment',
  effective_notification_datetime: '2026-06-01T12:00:00Z',
  determination_publication_date: '2026-07-01T12:00:00Z',
  events: [],
};

// The banner's whole job is to make the outcome unmissable, so what it says and
// what colour it says it in are both worth pinning.
const outcomeHeading = () => screen.getByRole('heading', { level: 2 });
const banner = (container) => container.querySelector('section');

describe('MergerOutcomeBanner', () => {
  it('leads with the determination for a completed matter', () => {
    const { container } = render(<MergerOutcomeBanner merger={completed} />);
    expect(outcomeHeading()).toHaveTextContent('Approved');
    expect(banner(container)).toHaveClass('bg-emerald-700');
    expect(
      screen.getByText('The ACCC cleared this acquisition in Phase 1 on 1 July 2026.')
    ).toBeInTheDocument();
  });

  it('names the outcome for a screen reader rather than leaving a bare adjective', () => {
    render(<MergerOutcomeBanner merger={completed} />);
    expect(outcomeHeading()).toHaveAccessibleName('Outcome: Approved');
  });

  it('renders nothing while the matter is still under assessment', () => {
    const { container } = render(
      <MergerOutcomeBanner
        merger={{ status: 'Under assessment', accc_determination: null }}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('turns red for a refusal', () => {
    const { container } = render(
      <MergerOutcomeBanner
        merger={{ ...completed, accc_determination: 'Not approved', stage: 'Phase 2 - detailed assessment' }}
      />
    );
    expect(outcomeHeading()).toHaveTextContent('Not approved');
    expect(banner(container)).toHaveClass('bg-red-700');
  });

  it('turns purple for a ceased assessment', () => {
    const { container } = render(
      <MergerOutcomeBanner
        merger={{
          status: 'Assessment ceased',
          accc_determination: null,
          ceased_date: '2026-07-16T12:00:00Z',
          effective_notification_datetime: '2026-06-22T12:00:00Z',
          events: [],
        }}
      />
    );
    expect(outcomeHeading()).toHaveTextContent('Assessment ceased');
    expect(banner(container)).toHaveClass('bg-purple-700');
    expect(
      screen.getByText('The ACCC ceased its assessment of this acquisition on 16 July 2026.')
    ).toBeInTheDocument();
  });

  it('flags a conditional clearance, which the register records as a plain approval', () => {
    render(<MergerOutcomeBanner merger={{ ...completed, has_conditions: true }} />);
    expect(screen.getByText('with conditions')).toBeInTheDocument();
  });

  it('ignores a conditions flag left on any other outcome', () => {
    render(
      <MergerOutcomeBanner
        merger={{ ...completed, accc_determination: 'Not approved', has_conditions: true }}
      />
    );
    expect(screen.queryByText('with conditions')).not.toBeInTheDocument();
  });

  it('shows how long the assessment ran', () => {
    render(<MergerOutcomeBanner merger={completed} />);
    expect(
      screen.getByText('30 calendar days (21 business days) from notification.')
    ).toBeInTheDocument();
  });

  it('leaves the ACCC outcome standing while an appeal is still current', () => {
    const { container } = render(
      <MergerOutcomeBanner
        merger={{
          ...completed,
          accc_determination: 'Not approved',
          under_appeal: true,
          appeal: { status: 'current', outcome: null, effective_determination: null },
        }}
      />
    );
    expect(outcomeHeading()).toHaveTextContent('Not approved');
    expect(banner(container)).toHaveClass('bg-red-700');
    expect(screen.queryByText(/Australian Competition Tribunal/)).not.toBeInTheDocument();
  });

  it('flips to the outcome the tribunal left standing, and says who changed it', () => {
    const { container } = render(
      <MergerOutcomeBanner
        merger={{
          ...completed,
          accc_determination: 'Not approved',
          stage: 'Phase 2 - detailed assessment',
          appeal: {
            status: 'concluded',
            outcome: 'set_aside',
            effective_determination: 'Approved',
            concluded_date: '2026-11-20',
          },
        }}
      />
    );
    expect(outcomeHeading()).toHaveTextContent('Approved');
    expect(banner(container)).toHaveClass('bg-emerald-700');
    expect(screen.getByText('on appeal')).toBeInTheDocument();
    // The sentence still reports what the ACCC itself decided.
    expect(
      screen.getByText('The ACCC refused to approve this acquisition in Phase 2 on 1 July 2026.')
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'Australian Competition Tribunal: ACCC decision set aside on 20 November 2026.'
      )
    ).toBeInTheDocument();
  });

  it('links the determination document when one is attached', () => {
    render(
      <MergerOutcomeBanner
        merger={{
          ...completed,
          events: [{ title: 'Determination', is_determination_event: true, url_gh: '/d.pdf' }],
        }}
      />
    );
    const link = screen.getByRole('link', { name: /Read the reasons/ });
    expect(link).toHaveAttribute('href', '/d.pdf');
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('omits the link when the register published no document', () => {
    render(<MergerOutcomeBanner merger={completed} />);
    expect(screen.queryByRole('link', { name: /Read the reasons/ })).not.toBeInTheDocument();
  });
});
