import { describe, expect, it } from 'vitest';
import {
  judicialReviewsOf,
  judicialReviewState,
  nextJudicialReviewHearing,
} from '../judicialReview';

describe('judicialReviewsOf', () => {
  it('prefers the per-file list', () => {
    const files = [{ case_number: 'NSD1/2026' }, { case_number: 'NSD2/2026' }];
    expect(judicialReviewsOf({ judicial_reviews: files, judicial_review: {} })).toBe(files);
  });

  it('reads an older detail file\'s summary as its one file', () => {
    const summary = { case_number: 'NSD1310/2026' };
    expect(judicialReviewsOf({ judicial_review: summary })).toEqual([summary]);
    expect(judicialReviewsOf({})).toEqual([]);
  });
});

describe('judicialReviewState', () => {
  it('names the outcome once concluded', () => {
    expect(judicialReviewState({ status: 'concluded', outcome: 'withdrawn' })).toBe('Review discontinued');
    expect(judicialReviewState({ status: 'concluded', outcome: null })).toBe('Concluded');
    expect(judicialReviewState({ status: 'current' })).toBe('Ongoing');
    // A summary from before status was published is a live review.
    expect(judicialReviewState({})).toBe('Ongoing');
  });
});

describe('nextJudicialReviewHearing', () => {
  const now = new Date(2026, 9, 28, 15, 0);
  const review = {
    listings: [
      { date: '2026-12-01', reason: 'Hearing', hearing: true },
      { date: '2026-11-10', reason: 'Administrative Listing', hearing: false },
      { date: '2026-11-03', reason: 'Case Management Hearing', hearing: true },
      { date: '2026-10-28', reason: 'Directions Hearing', hearing: true },
      { date: '2026-10-01', reason: 'First Case Management Hearing', hearing: true },
    ],
  };

  it('is the soonest hearing still to come, today included', () => {
    expect(nextJudicialReviewHearing(review, now).reason).toBe('Directions Hearing');
    expect(nextJudicialReviewHearing(review, new Date(2026, 9, 29)).reason).toBe('Case Management Hearing');
  });

  it('skips administrative listings and returns null when nothing is listed', () => {
    expect(nextJudicialReviewHearing(review, new Date(2026, 10, 4)).reason).toBe('Hearing');
    expect(nextJudicialReviewHearing(review, new Date(2026, 11, 2))).toBeNull();
    expect(nextJudicialReviewHearing({}, now)).toBeNull();
  });
});
