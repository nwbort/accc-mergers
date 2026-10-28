import { useState } from 'react';
import { FaBalanceScale } from 'react-icons/fa';
import ExternalLinkIcon from './ExternalLinkIcon';
import { formatDateLong, formatDateMedium } from '../utils/dates';
import {
  JUDICIAL_REVIEW_STATUS,
  judicialReviewState,
  nextJudicialReviewHearing,
} from '../constants/judicialReview';

// One listing's place, time and who presided, as one line: "10:15 · Justice
// O'Bryan · VIC - Remote". The reason and outcome sit on lines of their own.
function listingDetail(listing) {
  return [listing.time, listing.presiding, listing.location].filter(Boolean).join(' · ');
}

function ListingDocuments({ listing }) {
  const documents = [
    ...(listing.orders || []).map((order, i) => ({
      key: `order-${i}`, label: 'Orders', href: order.url_gh || order.url,
    })),
    ...(listing.judgments || []).map((judgment, i) => ({
      key: `judgment-${i}`,
      label: judgment.citation ? `Judgment ${judgment.citation}` : 'Judgment',
      href: judgment.url_gh || judgment.url,
    })),
  ].filter((doc) => doc.href);
  if (!documents.length) return null;
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1">
      {documents.map((doc) => (
        <a
          key={doc.key}
          href={doc.href}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-primary hover:text-primary-dark transition-colors"
          aria-label={`View ${doc.label} from the ${listing.reason || 'listing'} on ${formatDateLong(listing.date)} (opens in new tab)`}
        >
          {doc.label}
          <ExternalLinkIcon className="h-3 w-3" />
        </a>
      ))}
    </div>
  );
}

/**
 * A Federal Court judicial review of the ACCC's decision: who sought it and
 * when, where it stands, the judge it is docketed to, the next hearing, and
 * the court's listings with the orders and judgments made at them.
 *
 * Everything but the applicant is read off the Commonwealth Courts Portal by
 * the pipeline (scripts/scrape/scrape_federal_court.py). The documents filed
 * are on the timeline instead, alongside the Tribunal's, and the parties are
 * deliberately not shown. Styled as the Tribunal appeal cards beside it.
 */
function JudicialReviewCard({ review }) {
  const [showListings, setShowListings] = useState(false);
  const listings = review.listings || [];
  const concluded = review.status === JUDICIAL_REVIEW_STATUS.CONCLUDED;
  const nextHearing = concluded ? null : nextJudicialReviewHearing(review);
  const listingsId = `judicial-review-listings-${(review.case_number || 'review').replace(/\W+/g, '-')}`;

  return (
    <div className="bg-amber-50/80 rounded-2xl border border-amber-200/60 shadow-card p-4 mb-6">
      <div className="flex items-center gap-3">
        <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-amber-100 flex items-center justify-center">
          <FaBalanceScale className="h-4 w-4 text-amber-700" aria-hidden="true" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900">
            {review.applicant ? `Judicial review requested by ${review.applicant}` : 'Judicial review requested'}
            {review.filed_date ? ` on ${formatDateLong(review.filed_date)}` : ''}
            {concluded && (
              <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium bg-gray-100 text-gray-600 align-middle">
                Concluded
              </span>
            )}
          </p>
          <p className="text-xs text-gray-500 mt-0.5">
            {['Federal Court of Australia', review.case_number, concluded ? judicialReviewState(review) : null]
              .filter(Boolean)
              .join(' · ')}
            {concluded && review.concluded_date ? ` on ${formatDateLong(review.concluded_date)}` : ''}
          </p>
        </div>
        {review.case_url && (
          <a
            href={review.case_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 inline-flex items-center gap-1 text-xs font-medium text-amber-800 hover:text-amber-900 transition-colors"
            aria-label={`View ${review.case_number || 'this file'} on the Commonwealth Courts Portal (opens in new tab)`}
          >
            Courts Portal
            <ExternalLinkIcon className="h-3 w-3" />
          </a>
        )}
      </div>

      {(review.docket || nextHearing) && (
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4 pt-3 border-t border-amber-200/60">
          {nextHearing && (
            <div>
              <dt className="text-xs text-gray-500">Next hearing</dt>
              <dd className="text-sm font-medium text-gray-900">
                {formatDateLong(nextHearing.date)}
                {nextHearing.reason ? ` · ${nextHearing.reason}` : ''}
              </dd>
              {listingDetail(nextHearing) && (
                <dd className="text-xs text-gray-500 mt-0.5">{listingDetail(nextHearing)}</dd>
              )}
            </div>
          )}
          {review.docket && (
            <div>
              <dt className="text-xs text-gray-500">Docket judge</dt>
              <dd className="text-sm font-medium text-gray-900">{review.docket}</dd>
            </div>
          )}
        </dl>
      )}

      {listings.length > 0 && (
        <div className="mt-3 pt-3 border-t border-amber-200/60">
          <button
            type="button"
            onClick={() => setShowListings((shown) => !shown)}
            className="text-xs font-medium text-primary hover:text-primary-dark transition-colors"
            aria-expanded={showListings}
            aria-controls={listingsId}
          >
            {showListings ? 'Hide court listings' : `Show ${listings.length} court listing${listings.length === 1 ? '' : 's'}`}
          </button>
          {showListings && (
            <ul id={listingsId} className="mt-3 space-y-3">
              {listings.map((listing, i) => (
                <li key={`${listing.date}-${listing.time}-${i}`} className="text-sm">
                  <p className="font-medium text-gray-900">
                    {formatDateMedium(listing.date)}
                    {listing.reason ? ` · ${listing.reason}` : ''}
                  </p>
                  {listingDetail(listing) && (
                    <p className="text-xs text-gray-500 mt-0.5">{listingDetail(listing)}</p>
                  )}
                  {listing.outcome && (
                    <p className="text-xs text-gray-700 mt-0.5">{listing.outcome}</p>
                  )}
                  <ListingDocuments listing={listing} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export default JudicialReviewCard;
