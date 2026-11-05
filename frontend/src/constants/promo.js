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

import { FaGaugeHigh, FaYoutube } from 'react-icons/fa6';
import { hearingPromoTitle } from '../utils/hearingPromo';

// Coles' Tribunal appeal over Kalgoorlie (MN-01068, ACT 1 of 2026). Sits
// Monday to Thursday for two weeks; the banner counts down to the start,
// follows each day, and disappears once the last scheduled day rises. If the
// hearing finishes early, take it out of DASHBOARD_PROMOS.
//
// Not running yet: to turn it on, add it to the top of DASHBOARD_PROMOS.
export const COLES_KALGOORLIE_HEARING = {
  subject: 'Coles Kalgoorlie tribunal appeal hearing',
  sittingDays: [
    '2026-11-09', '2026-11-10', '2026-11-11', '2026-11-12',
    '2026-11-16', '2026-11-17', '2026-11-18', '2026-11-19',
  ],
  startTime: '10:15',
  endTime: '16:15',
  timeZone: 'Australia/Sydney',
};

export const COLES_KALGOORLIE_HEARING_PROMO = {
  campaign: 'coles-kalgoorlie-hearing-v1',
  href: 'https://www.youtube.com/watch?v=m_0-xU3uyyQ',
  icon: FaYoutube,
  description: 'Watch the livestream on YouTube.',
  resolve: (now) => {
    const title = hearingPromoTitle(COLES_KALGOORLIE_HEARING, now);
    return title && { title };
  },
};

export const DASHBOARD_PROMOS = [
  {
    campaign: 'current-status-v1',
    to: '/current-status',
    icon: FaGaugeHigh,
    title: 'How fast is the ACCC deciding mergers right now?',
    description: 'See recent waiver and phase 1 decision times against the all-time baseline.',
  },
];
