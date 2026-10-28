/**
 * Federal Court judicial review constants.
 *
 * An ACCC merger decision can be challenged in the Federal Court by judicial
 * review as well as at the Tribunal. A review's status and outcome are read off
 * the Commonwealth Courts Portal by the pipeline; these values and labels
 * mirror scripts/constants/judicial_review.py and must stay in sync with it.
 */

import { APPEAL_STATUS } from './appeal';

// The same two lifecycle values as a tribunal appeal: current / concluded.
export const JUDICIAL_REVIEW_STATUS = APPEAL_STATUS;

export const JUDICIAL_REVIEW_OUTCOME = {
  WITHDRAWN: 'withdrawn',
  DISMISSED: 'dismissed',
  SET_ASIDE: 'set_aside',
};

export const JUDICIAL_REVIEW_OUTCOME_LABELS = {
  [JUDICIAL_REVIEW_OUTCOME.WITHDRAWN]: 'Review discontinued',
  [JUDICIAL_REVIEW_OUTCOME.DISMISSED]: 'Application dismissed',
  [JUDICIAL_REVIEW_OUTCOME.SET_ASIDE]: 'ACCC decision set aside',
};

// `review_forum` on a timeline event from a Federal Court file. Tribunal
// documents carry none, and both carry `is_appeal`.
export const REVIEW_FORUM_FEDERAL_COURT = 'federal_court';

export const UNDER_JUDICIAL_REVIEW_LABEL = 'Under judicial review';

/**
 * The Federal Court files filed against a merger. `judicial_review` is the
 * merger-level summary; a detail file from before `judicial_reviews` existed
 * has only that, and it stands for its one file.
 */
export function judicialReviewsOf(merger) {
  if (merger?.judicial_reviews?.length) return merger.judicial_reviews;
  return merger?.judicial_review ? [merger.judicial_review] : [];
}

/** How a review stands, in a few words: "Ongoing", or its outcome. */
export function judicialReviewState(review) {
  if (review?.status !== JUDICIAL_REVIEW_STATUS.CONCLUDED) return 'Ongoing';
  return JUDICIAL_REVIEW_OUTCOME_LABELS[review.outcome] || 'Concluded';
}

/**
 * The review's next hearing someone attends, or null. Listings are newest
 * first, so the next one is the last of those still to come. A date with no
 * time sorts as the start of the day, so a hearing listed today still shows.
 */
export function nextJudicialReviewHearing(review, now = new Date()) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const upcoming = (review?.listings || []).filter((listing) => {
    if (!listing.hearing || !listing.date) return false;
    const [y, m, d] = listing.date.split('-').map(Number);
    return new Date(y, m - 1, d) >= today;
  });
  return upcoming.length ? upcoming[upcoming.length - 1] : null;
}
