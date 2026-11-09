/**
 * The promo banners the dashboard runs, in priority order.
 *
 * Everything that makes a campaign a campaign lives here; PromoStack stacks
 * every one the reader hasn't dismissed, top to bottom in this order, and the
 * rest move up when they dismiss one. Empty the list to run none.
 *
 * `campaign` keys the localStorage dismissal. To point a banner at something
 * new, give it a new id, so it comes back for everyone who dismissed the old
 * one; reusing an id keeps it hidden from them.
 *
 * A campaign links either inside the site (`to`) or out of it (`href`, opened
 * in a new tab). One whose wording changes with the clock carries
 * `resolve(now)`, returning the props to show at `now` (merged over the
 * campaign's own) or null to hide it; PromoStack re-reads it every minute.
 */

import { FaYoutube } from 'react-icons/fa6';
import { hearingPromoTitle } from '../utils/hearingPromo';

// Coles' Tribunal appeal over Kalgoorlie (MN-01068, ACT 1 of 2026). Sits
// Monday to Thursday for two weeks. Tuesday 10 November sat in closed court,
// so the public livestream skips it: the banner's headline stays on the
// hearing as a whole, and its subline follows the livestream day by day,
// until the last scheduled day rises. If the hearing finishes early, take it
// out of DASHBOARD_PROMOS.
export const COLES_KALGOORLIE_HEARING = {
  title: 'Coles Kalgoorlie Tribunal appeal hearing continues this week',
  sittingDays: [
    '2026-11-09', '2026-11-10', '2026-11-11', '2026-11-12',
    '2026-11-16', '2026-11-17', '2026-11-18', '2026-11-19',
  ],
  startTime: '10:15',
  endTime: '16:15',
  timeZone: 'Australia/Sydney',
};

// The days the public can watch: every sitting day bar those in closed court.
const CLOSED_COURT_DAYS = ['2026-11-10'];

export const COLES_KALGOORLIE_LIVESTREAM = {
  ...COLES_KALGOORLIE_HEARING,
  subject: 'The public livestream',
  sittingDays: COLES_KALGOORLIE_HEARING.sittingDays.filter(
    (day) => !CLOSED_COURT_DAYS.includes(day),
  ),
};

export const COLES_KALGOORLIE_HEARING_PROMO = {
  campaign: 'coles-kalgoorlie-hearing-v2',
  href: 'https://www.youtube.com/watch?v=AFSvBZfLu7g',
  icon: FaYoutube,
  title: COLES_KALGOORLIE_HEARING.title,
  resolve: (now) => {
    const line = hearingPromoTitle(COLES_KALGOORLIE_LIVESTREAM, now);
    return line && { description: `${line}.` };
  },
};

export const DASHBOARD_PROMOS = [COLES_KALGOORLIE_HEARING_PROMO];
