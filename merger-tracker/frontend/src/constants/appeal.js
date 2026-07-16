/**
 * Australian Competition Tribunal appeal constants.
 *
 * An ACCC merger decision can be taken to the Australian Competition Tribunal
 * for limited merits review by one of three routes (a third party challenging
 * a clearance, a party challenging a conditional clearance, or a party
 * challenging a refusal). These `appeal_type` values and their labels mirror
 * scripts/constants/tribunal.py and must stay in sync with it and with the
 * data in data/processed/tribunal_appeals.json.
 */

export const APPEAL_TYPES = {
  PARTY_DENIAL: 'party_denial',
  PARTY_CONDITIONAL_CLEARANCE: 'party_conditional_clearance',
  THIRD_PARTY_CLEARANCE: 'third_party_clearance',
};

// appeal_type → short human label shown on the tribunal link card.
export const APPEAL_TYPE_LABELS = {
  [APPEAL_TYPES.PARTY_DENIAL]: 'Appeal against refusal',
  [APPEAL_TYPES.PARTY_CONDITIONAL_CLEARANCE]: 'Appeal against conditional clearance',
  [APPEAL_TYPES.THIRD_PARTY_CLEARANCE]: 'Third party appeal against clearance',
};

// Fallback used when an appeal_type is missing or unrecognised.
export const DEFAULT_APPEAL_LABEL = 'Under review at the Competition Tribunal';
