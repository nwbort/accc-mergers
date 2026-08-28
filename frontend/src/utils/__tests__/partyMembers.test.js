import { describe, expect, it } from 'vitest';
import { collapsePartyMembers, identifierCore, splitPartyName } from '../partyMembers';

const member = (name, identifier = null, identifier_type = null) => ({
  name,
  identifier,
  identifier_type,
});

describe('splitPartyName', () => {
  it('separates the legal form from the base name', () => {
    expect(splitPartyName('Bain Capital Investors, LLC.')).toEqual({
      base: 'bain capital investors',
      form: 'llc',
    });
  });

  it('ignores case, punctuation and accents', () => {
    expect(splitPartyName("L'Oréal S.A.")).toEqual(splitPartyName("L'OREAL SA"));
  });

  it('canonicalises interchangeable spellings of a form', () => {
    expect(splitPartyName('Zurich Assure Australia Pty Limited'))
      .toEqual(splitPartyName('ZURICH ASSURE AUSTRALIA PTY LTD'));
  });
});

describe('identifierCore', () => {
  it('reduces an identifier to its digits, whatever the label around them', () => {
    expect(identifierCore('Registration number (Jersey)  140080')).toBe('140080');
    expect(identifierCore('JFSC – 140080')).toBe('140080');
  });

  it('ignores leading zeros', () => {
    expect(identifierCore('0001108524')).toBe(identifierCore('1108524'));
  });

  it('treats placeholders as no identifier at all', () => {
    expect(identifierCore('N/A')).toBe('');
    expect(identifierCore(null)).toBe('');
  });
});

describe('collapsePartyMembers', () => {
  it('groups one entity recorded with differently labelled identifiers', () => {
    const rows = collapsePartyMembers([
      member('CVC Capital Partners'),
      member('CVC Capital Partners plc'),
      member('CVC Capital Partners plc', '140080'),
      member('CVC Capital Partners plc', 'JFSC  140080'),
      member('CVC Capital Partners plc', 'JFSC – 140080'),
      member('CVC Capital Partners plc', 'Registration number (Jersey)  140080'),
    ]);

    expect(rows).toHaveLength(1);
    expect(rows[0].name).toBe('CVC Capital Partners plc');
    expect(rows[0].identifiers).toEqual([
      { type: null, value: 'Registration number (Jersey) 140080' },
    ]);
    expect(rows[0].members).toHaveLength(6);
  });

  it('keeps every distinct registration the entity holds', () => {
    const rows = collapsePartyMembers([
      member('Bain Capital Investors LLC', '3229725'),
      member('Bain Capital Investors, LLC', 'Delaware File Number  3229725'),
      member('Bain Capital Investors, LLC', 'IRS EIN  812878769'),
    ]);

    expect(rows).toHaveLength(1);
    expect(rows[0].identifiers.map((i) => i.value)).toEqual([
      'Delaware File Number 3229725',
      'IRS EIN 812878769',
    ]);
  });

  it('merges a shouted name with its title-case twin and prefers the title case', () => {
    const rows = collapsePartyMembers([
      member('ZURICH ASSURE AUSTRALIA PTY LIMITED', '58 657 804 736', 'ABN'),
      member('Zurich Assure Australia Pty Ltd'),
    ]);

    expect(rows).toHaveLength(1);
    expect(rows[0].name).toBe('Zurich Assure Australia Pty Ltd');
    expect(rows[0].identifiers).toEqual([{ type: 'ABN', value: '58 657 804 736' }]);
  });

  it('keeps entities that differ only by legal form apart', () => {
    const rows = collapsePartyMembers([
      member('Accenture Inc.', 'Delaware registered number  3387477'),
      member('Accenture plc', 'CRN  471706'),
    ]);

    expect(rows.map((row) => row.name)).toEqual(['Accenture Inc.', 'Accenture plc']);
  });

  it('groups an ABN with the ACN it contains', () => {
    const rows = collapsePartyMembers([
      member('AMPOL RETAIL HOLDING PTY LTD', '11 689 777 704', 'ABN'),
      member('AMPOL RETAIL HOLDING PTY LTD', '689 777 704', 'ACN'),
    ]);

    expect(rows).toHaveLength(1);
  });

  it('never groups distinct subsidiaries of the same parent', () => {
    const rows = collapsePartyMembers([
      member('NDC FINCO PTY LTD', '14 654 149 818', 'ABN'),
      member('NDC HOLDCO PTY LTD', '13 654 148 188', 'ABN'),
      member('NDC HoldCo Pty Ltd', '13 654 148 188', 'ABN'),
    ]);

    expect(rows).toHaveLength(2);
    expect(rows[1].members).toHaveLength(2);
  });

  it('does not treat placeholder identifiers as a shared identifier', () => {
    const rows = collapsePartyMembers([
      member('AMI Holding GmbH', 'N/A'),
      member('Metrotech Vertriebs GmbH', 'N/A'),
    ]);

    expect(rows).toHaveLength(2);
  });

  it('folds together clusters bridged by a later record', () => {
    const rows = collapsePartyMembers([
      member('Acclime Holdings HK Limited', 'BRN  70084973'),
      member('Acclime Holdings Limited'),
      member('Acclime Holdings Limited', 'BRN70084973'),
    ]);

    expect(rows).toHaveLength(1);
    expect(rows[0].members).toHaveLength(3);
  });

  it('drops empty records and tolerates a missing list', () => {
    expect(collapsePartyMembers([{ name: '', identifier: null }])).toEqual([]);
    expect(collapsePartyMembers(undefined)).toEqual([]);
  });
});
