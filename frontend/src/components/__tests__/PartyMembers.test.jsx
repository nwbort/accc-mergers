import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import PartyMembers from '../PartyMembers';

const CVC = [
  { name: 'CVC Capital Partners', identifier: null, identifier_type: null },
  { name: 'CVC Capital Partners plc', identifier: null, identifier_type: null },
  { name: 'CVC Capital Partners plc', identifier: '140080', identifier_type: null },
  { name: 'CVC Capital Partners plc', identifier: 'JFSC  140080', identifier_type: null },
  { name: 'CVC Capital Partners plc', identifier: 'JFSC – 140080', identifier_type: null },
  { name: 'CVC Capital Partners plc', identifier: 'Registration number (Jersey)  140080', identifier_type: null },
];

const member = (name, identifier = null, identifier_type = null) => ({
  name,
  identifier,
  identifier_type,
});

describe('PartyMembers', () => {
  it('shows one entity recorded six ways as a single line', () => {
    render(<PartyMembers members={CVC} partyName="CVC Capital Partners" />);

    expect(screen.queryByText('Related parties')).not.toBeInTheDocument();
    expect(screen.getByText('CVC Capital Partners plc')).toBeInTheDocument();
    expect(screen.getByText(/Registration number \(Jersey\) 140080/)).toBeInTheDocument();
    expect(screen.queryByText(/JFSC/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('lists genuinely different entities, previewing the first three', async () => {
    const user = userEvent.setup();
    render(
      <PartyMembers
        partyName="Zurich"
        members={[
          member('ZURICH ASSURE AUSTRALIA PTY LIMITED', '58 657 804 736', 'ABN'),
          member('ZURICH AUSTRALIA LIMITED', '92 000 010 195', 'ABN'),
          member('ZURICH AUSTRALIAN INSURANCE LIMITED', '13 000 296 640', 'ABN'),
          member('ZURICH INVESTMENT MANAGEMENT LIMITED', '56 063 278 400', 'ABN'),
        ]}
      />
    );

    expect(screen.getByText('Related parties')).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(3);

    await user.click(screen.getByRole('button', { name: 'Show 1 more' }));
    expect(screen.getAllByRole('listitem')).toHaveLength(4);
  });

  it('shows only the identifier when the sole member is the party itself', () => {
    render(
      <PartyMembers
        partyName="Woolworths Group Limited"
        members={[member('WOOLWORTHS GROUP LTD', '88 000 014 675', 'ABN')]}
      />
    );

    expect(screen.getByText('ABN: 88 000 014 675')).toBeInTheDocument();
    expect(screen.queryByText(/WOOLWORTHS GROUP LTD/)).not.toBeInTheDocument();
  });

  it('renders nothing for a party with no members', () => {
    const { container } = render(<PartyMembers members={[]} partyName="Anon" />);
    expect(container).toBeEmptyDOMElement();
  });
});
