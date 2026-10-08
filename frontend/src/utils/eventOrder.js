// The title extract_mergers.py gives the notification event it synthesises.
const NOTIFICATION_EVENT_TITLE = 'Merger notified to ACCC';

const isNotificationEvent = (event) => event.title === NOTIFICATION_EVENT_TITLE;

/**
 * A merger's events, newest first.
 *
 * Events share a date often (the questionnaire is usually published the day
 * the merger is notified), and the stored order can't settle those ties: it
 * follows whatever order the ACCC's page listed them in, which differs between
 * its old and new consultation formats. The notification is what starts the
 * matter, so on its date it always sorts as the oldest event. Other ties keep
 * their stored order.
 */
export function sortEventsNewestFirst(events) {
  if (!events) return [];
  return [...events].sort((a, b) => (
    new Date(b.date) - new Date(a.date)
    || isNotificationEvent(a) - isNotificationEvent(b)
  ));
}
