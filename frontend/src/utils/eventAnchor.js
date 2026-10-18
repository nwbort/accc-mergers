// In-page anchors for a merger's events, so the notification panel can link
// straight to an event on the detail page (`/mergers/{id}/{slug}#{anchor}`).
//
// Both sides derive the anchor from the event itself rather than its position,
// since the panel never sees the detail page's sorted list.
import { slugify } from './slug';

// The assessment timeline at the top of the detail page. Upcoming deadlines
// (determination due, consultation closing, ...) aren't rows in the event
// list, but they are milestones on this track, so their links land here.
export const ASSESSMENT_TIMELINE_ANCHOR = 'assessment-timeline';

/**
 * Anchor id for one of a merger's dated events: its calendar date plus a slug
 * of its title. Two events sharing both are rare; the detail page anchors the
 * first of them, which is the one a link would most plausibly mean.
 *
 * @param {{date?: string, display_title?: string, title?: string}} event
 * @returns {string}
 */
export function eventAnchorId(event) {
  const date = String(event?.date || '').slice(0, 10);
  const title = slugify(event?.display_title || event?.title);
  return `event-${date}-${title}`;
}
