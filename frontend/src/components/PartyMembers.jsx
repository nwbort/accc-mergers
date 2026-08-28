import { useMemo, useState } from 'react';
import { collapsePartyMembers, splitPartyName } from '../utils/partyMembers';
import { SECTION_HEADING } from '../utils/classNames';

const ROWS_PREVIEW_COUNT = 3;

const TOGGLE_CLASS = 'text-sm text-primary hover:text-primary-dark font-medium mt-2 transition-colors';

function identifierText({ type, value }) {
  return type ? `${type}: ${value}` : value;
}

/** True when a member's name says nothing the group's own name doesn't. */
function sameAsPartyName(name, partyName) {
  const member = splitPartyName(name);
  const party = splitPartyName(partyName);
  return member.base === party.base && member.form === party.form;
}

function MemberIdentifiers({ identifiers }) {
  return identifiers.map((identifier) => (
    <span key={identifier.value} className="text-gray-500">
      {' '}&middot; {identifierText(identifier)}
    </span>
  ));
}

/**
 * The "Related parties" block on a party page.
 *
 * A group's members are the raw (name, identifier) pairs read off filings, so
 * the same entity recurs under trivially different spellings. They are grouped
 * for display by utils/partyMembers.js — one row per entity, each carrying its
 * distinct registration numbers — with every raw record still reachable behind
 * the variants toggle.
 */
function PartyMembers({ members = [], partyName = '' }) {
  const rows = useMemo(() => collapsePartyMembers(members), [members]);
  const [showAllRows, setShowAllRows] = useState(false);
  const [showVariants, setShowVariants] = useState(false);

  if (rows.length === 0) return null;

  const collapsedCount = members.length - rows.length;
  const variantsToggle = collapsedCount > 0 && (
    <>
      <button
        type="button"
        onClick={() => setShowVariants((prev) => !prev)}
        className={TOGGLE_CLASS}
        aria-expanded={showVariants}
        aria-controls="party-member-variants"
      >
        {showVariants
          ? 'Hide recorded variants'
          : `Show all ${members.length} recorded variants`}
      </button>
      {showVariants && (
        <ul id="party-member-variants" className="mt-2 space-y-1">
          {members.map((member, index) => (
            <li key={`${member.name}-${member.identifier || ''}-${index}`} className="text-sm text-gray-500">
              {member.name}
              {member.identifier && (
                <>
                  {' '}&middot; {member.identifier_type ? `${member.identifier_type}: ` : ''}{member.identifier}
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </>
  );

  // A single entity needs no list: its name (when it adds anything to the
  // group's own) and registration numbers sit on one line under the heading.
  if (rows.length === 1) {
    const [row] = rows;
    const showName = row.name && !sameAsPartyName(row.name, partyName);
    if (!showName && row.identifiers.length === 0) return variantsToggle || null;
    return (
      <>
        <p className="text-sm mt-2">
          {showName && <span className="text-gray-700">{row.name}</span>}
          {showName
            ? <MemberIdentifiers identifiers={row.identifiers} />
            : (
              <span className="text-gray-500">
                {row.identifiers.map(identifierText).join(' · ')}
              </span>
            )}
        </p>
        {variantsToggle}
      </>
    );
  }

  const visibleRows = showAllRows ? rows : rows.slice(0, ROWS_PREVIEW_COUNT);

  return (
    <div className="mt-4 pt-4 border-t border-gray-100">
      <h2 className={`${SECTION_HEADING} mb-2`}>
        Related parties
      </h2>
      <ul className="space-y-1">
        {visibleRows.map((row) => (
          <li key={`${row.name}-${row.identifiers[0]?.value || ''}`} className="text-sm text-gray-700">
            {row.name}
            <MemberIdentifiers identifiers={row.identifiers} />
          </li>
        ))}
      </ul>
      {rows.length > ROWS_PREVIEW_COUNT && (
        <button
          type="button"
          onClick={() => setShowAllRows((prev) => !prev)}
          className={TOGGLE_CLASS}
          aria-expanded={showAllRows}
        >
          {showAllRows ? 'Show less' : `Show ${rows.length - ROWS_PREVIEW_COUNT} more`}
        </button>
      )}
      {variantsToggle && <div>{variantsToggle}</div>}
    </div>
  );
}

export default PartyMembers;
