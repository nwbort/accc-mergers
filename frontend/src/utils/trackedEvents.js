// What following a merger or an industry surfaces, worked out from the data
// files alone.
//
// Shared by TrackingContext (the notification panel) and the service worker
// behind browser notifications (src/push/sw.js), so the two agree on what an
// event is and what its key is. A key decides whether an event is news: one
// marked seen in the panel is never announced again, by either.
//
// Plain functions with no React and no DOM, since the service worker has
// neither.

import { MERGER_STATUS } from '../constants/mergerStatus.js';
import { JUDICIAL_REVIEW_STATUS } from '../constants/judicialReview.js';
import { isDatePast } from './dates.js';

// Relationship values (from the data pipeline, see scripts/generate/static_data/loaders.py)
// where the *tracked* merger is the earlier matter and its related merger is the
// newer re-filed one. Tracking a merger auto-tracks its related merger only in
// this forward direction: tracking a declined waiver / suspended matter also
// tracks the notification it was re-filed as, but tracking the re-filed matter
// must NOT pull in the historical one it superseded.
export const FORWARD_REFILE_RELATIONSHIPS = new Set([
  'refiled_as',
  'suspended_refiled_as',
]);

// Key an event by its merger, date and title.
const titleKey = (event, title) => {
  // Industry-follow events are scoped to the industry they were surfaced from,
  // so the same merger filed under two followed industries stays distinct (and
  // distinct from the merger's own tracked timeline events).
  const prefix = event.industry_code ? `ind_${event.industry_code}_` : '';
  return `${prefix}${event.merger_id}_${event.date}_${title}`;
};

// Generate a unique key for an event
// Use a consistent order and normalize the title field for stability
export const getEventKey = (event) => {
  // A tribunal appeal document is keyed by its document link, not its title:
  // the title carries a comment added by hand, often after followers have
  // already been notified, and a title-based key would announce the same
  // document again.
  const docUrl = event.is_appeal && (event.url || event.url_gh);
  if (docUrl) return `${event.merger_id}_${event.date}_appeal_${docUrl}`;
  // Normalize title: prefer display_title, then title, then event_type_display, finally type
  const title = event.display_title || event.title || event.event_type_display || event.type || '';
  return titleKey(event, title);
};

// Keys an appeal document may already have been marked seen under, from
// before appeal documents were keyed by link: its title with the comment (seen
// after the comment was added) and without it (seen before).
export const getLegacyEventKeys = (event) => {
  if (!event.is_appeal) return [];
  return [event.display_title, event.appeal_base_title]
    .filter(Boolean)
    .map((title) => titleKey(event, title));
};

// Deduplicate events by their event key
export const dedupeEvents = (events) => {
  const seen = new Set();
  return events.filter((event) => {
    const key = getEventKey(event);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

/** A tracked merger's register events, from its detail file. */
export function timelineEventsFromMerger(merger) {
  if (!merger) return [];
  return (merger.events || []).map((event) => ({
    date: event.date,
    title: event.title,
    display_title: event.display_title,
    url: event.url,
    url_gh: event.url_gh,
    status: event.status,
    merger_id: merger.merger_id,
    merger_name: merger.merger_name,
    phase: event.phase,
    is_waiver: merger.is_waiver,
    is_appeal: event.is_appeal,
    appeal_base_title: event.appeal_base_title,
  }));
}

/**
 * A tracked merger's coming deadlines and hearings, from its detail file.
 *
 * Derived here rather than read from upcoming-events.json, which isn't subject
 * to that feed's 60-day window, so events whose deadline is months away (e.g.
 * Phase 2 determinations) still surface.
 */
export function upcomingEventsFromMerger(merger, now = new Date()) {
  if (!merger) return [];
  const events = [];
  const base = {
    merger_id: merger.merger_id,
    merger_name: merger.merger_name,
    status: merger.status,
    stage: merger.stage,
    effective_notification_datetime: merger.effective_notification_datetime,
    is_waiver: merger.is_waiver,
  };
  const labelled = (type, label, date) => ({
    type,
    event_type_display: label,
    display_title: label,
    title: label,
    date,
    ...base,
  });

  // Tribunal hearing for a matter under a *current* appeal.
  // Handled before the "already determined" guards below because an
  // appealed matter is, by definition, ACCC-determined — the hearing is
  // a future event layered on top of that outcome. Not subject to any
  // look-ahead window (mirrors scripts/generate/static_data/outputs/upcoming_events.py).
  // A hearing that sits over several days carries its last day as
  // `end_date`, and stays (as ongoing) until that day has passed on
  // the Australian calendar, rather than dropping off on day one.
  const appeal = merger.appeal;
  if (merger.under_appeal && appeal && appeal.hearing_date) {
    const endDate =
      appeal.hearing_end_date && appeal.hearing_end_date > appeal.hearing_date
        ? appeal.hearing_end_date
        : null;
    if (!isDatePast(endDate || appeal.hearing_date)) {
      events.push({
        ...labelled('tribunal_hearing', 'Tribunal hearing', appeal.hearing_date),
        ...(endDate && { end_date: endDate }),
        tribunal_number: appeal.tribunal_number,
      });
    }
  }

  // Federal Court hearings on a live judicial review, the same way and
  // for the same reason: read off the court's listings, only those
  // someone attends (`hearing`), with no look-ahead window (mirrors
  // upcoming_events.py).
  if (merger.under_judicial_review) {
    (merger.judicial_reviews || []).forEach((review) => {
      if (review.status === JUDICIAL_REVIEW_STATUS.CONCLUDED) return;
      (review.listings || []).forEach((listing) => {
        if (!listing.hearing || !listing.date) return;
        if (new Date(listing.date) <= now) return;
        events.push({
          ...labelled('federal_court_hearing', 'Federal Court hearing', listing.date),
          case_number: review.case_number,
          hearing_reason: listing.reason,
        });
      });
    });
  }

  // Skip if already determined, a waiver, or assessment is no longer active.
  // Check accc_determination as well as the date: the register sometimes
  // publishes the outcome before the publication-date field is scraped,
  // and relying on the date alone leaves stale "due" events in the panel
  // (mirrors the candidate filter in scripts/generate/static_data/outputs/upcoming_events.py).
  if (merger.determination_publication_date) return events;
  if (merger.accc_determination) return events;
  if (merger.is_waiver) return events;
  if (merger.status === MERGER_STATUS.ASSESSMENT_SUSPENDED) return events;
  if (merger.status === MERGER_STATUS.ASSESSMENT_CEASED) return events;

  const future = (date) => date && new Date(date) > now;

  if (future(merger.end_of_determination_period)) {
    const label = merger.public_benefit_in_progress
      ? 'Public benefit determination due'
      : 'Determination due';
    events.push(labelled('determination_due', label, merger.end_of_determination_period));
  }

  if (future(merger.consultation_response_due_date)) {
    events.push(labelled('consultation_due', 'Consultation responses due', merger.consultation_response_due_date));
  }

  // Public benefit phase milestones (mirrors upcoming_events.py): the
  // ACCC's public benefit assessment (BD 20) and the parties' last day
  // to respond to it or offer a remedy (BD 35).
  [
    ['public_benefit_assessment_date', 'public_benefit_assessment', 'Public benefit assessment'],
    ['public_benefit_response_date', 'public_benefit_response_due', 'Public benefit responses due'],
  ].forEach(([field, type, label]) => {
    if (future(merger[field])) events.push(labelled(type, label, merger[field]));
  });

  if (future(merger.competition_concerns_notice_date)) {
    events.push(labelled(
      'notice_of_competition_concerns',
      'Notice of competition concerns',
      merger.competition_concerns_notice_date,
    ));
  }

  return events;
}

/**
 * A followed industry's events: a new merger filed in it, and a new
 * determination published for one of its mergers. Read off the merger
 * summaries in the industry's node (see utils/industryNode.js), so no
 * per-merger fetch is needed.
 */
export function industryEventsFromNode(code, node) {
  if (!node) return [];
  const industryName = node.name || code;
  const events = [];
  (node.mergers || []).forEach((m) => {
    const base = {
      industry_code: code,
      industry_name: industryName,
      merger_id: m.merger_id,
      merger_name: m.merger_name,
      is_waiver: m.is_waiver,
      status: m.status,
    };
    if (m.notification_date) {
      events.push({
        ...base,
        type: 'industry_new_merger',
        event_type_display: 'New merger filed',
        display_title: 'New merger filed',
        title: 'New merger filed',
        date: m.notification_date,
      });
    }
    if (m.determination_date) {
      events.push({
        ...base,
        type: 'industry_determination',
        event_type_display: 'Determination published',
        display_title: 'Determination published',
        title: 'Determination published',
        date: m.determination_date,
      });
    }
  });
  return events;
}

/** Forward re-file links ("sourceId->relatedId") a tracked merger's file carries. */
export function forwardRefileLink(merger) {
  const related = merger && merger.related_merger;
  if (!related || !FORWARD_REFILE_RELATIONSHIPS.has(related.relationship)) return null;
  if (!related.merger_id) return null;
  return { key: `${merger.merger_id}->${related.merger_id}`, relatedId: related.merger_id };
}
