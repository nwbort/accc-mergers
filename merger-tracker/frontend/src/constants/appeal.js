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

// Appeal lifecycle status (mirrors scripts/constants/tribunal.py). Only a
// `current` appeal makes a merger "under appeal"; a `concluded` matter keeps
// its tribunal link and documents on the detail page but drops the badge.
export const APPEAL_STATUS = {
  CURRENT: 'current',
  CONCLUDED: 'concluded',
};

// Tribunal outcome once an appeal is concluded (mirrors constants/tribunal.py).
export const APPEAL_OUTCOME = {
  AFFIRMED: 'affirmed',
  SET_ASIDE: 'set_aside',
  VARIED: 'varied',
  WITHDRAWN: 'withdrawn',
  DISMISSED: 'dismissed',
};

// outcome → full human label shown on the tribunal link card.
export const APPEAL_OUTCOME_LABELS = {
  [APPEAL_OUTCOME.AFFIRMED]: 'ACCC decision affirmed',
  [APPEAL_OUTCOME.SET_ASIDE]: 'ACCC decision set aside',
  [APPEAL_OUTCOME.VARIED]: 'ACCC decision varied',
  [APPEAL_OUTCOME.WITHDRAWN]: 'Appeal withdrawn',
  [APPEAL_OUTCOME.DISMISSED]: 'Appeal dismissed',
};

// outcome → short suffix appended to the effective determination on the status
// badge, mirroring the "· with conditions" treatment (e.g. "Approved · on
// appeal", "Not approved · confirmed on appeal").
export const APPEAL_OUTCOME_BADGE_SUFFIX = {
  [APPEAL_OUTCOME.AFFIRMED]: 'confirmed on appeal',
  [APPEAL_OUTCOME.DISMISSED]: 'confirmed on appeal',
  [APPEAL_OUTCOME.WITHDRAWN]: 'appeal withdrawn',
  [APPEAL_OUTCOME.SET_ASIDE]: 'on appeal',
  [APPEAL_OUTCOME.VARIED]: 'varied on appeal',
};

// appeal_type → short human label shown on the tribunal link card.
export const APPEAL_TYPE_LABELS = {
  [APPEAL_TYPES.PARTY_DENIAL]: 'Appeal against refusal',
  [APPEAL_TYPES.PARTY_CONDITIONAL_CLEARANCE]: 'Appeal against conditional clearance',
  [APPEAL_TYPES.THIRD_PARTY_CLEARANCE]: 'Third party appeal against clearance',
};

// Fallback used when an appeal_type is missing or unrecognised.
export const DEFAULT_APPEAL_LABEL = 'Under review at the Competition Tribunal';
